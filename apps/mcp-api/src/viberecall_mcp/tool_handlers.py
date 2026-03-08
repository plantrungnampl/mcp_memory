from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, status

from viberecall_mcp.auth import AuthenticatedToken
from viberecall_mcp.code_index import (
    attach_index_job_id,
    build_context_pack,
    index_status,
    mark_index_request_failed,
    request_index_repo,
    search_entities,
)
from viberecall_mcp.config import get_settings
from viberecall_mcp.errors import ToolRuntimeError
from viberecall_mcp.ids import new_id
from viberecall_mcp.metrics import rate_limited_count, tokens_burn_rate
from viberecall_mcp.object_storage import ObjectStorageError, delete_object, episode_storage_key, put_text
from viberecall_mcp.pagination import decode_cursor, encode_cursor, make_seed
from viberecall_mcp.repositories.episodes import (
    create_episode,
    get_episode_for_project,
    delete_episode_for_project,
    list_recent_raw_episodes,
    list_timeline_episodes,
    set_episode_job_id,
)
from viberecall_mcp.repositories.usage_events import get_monthly_vibe_tokens
from viberecall_mcp.runtime import (
    get_graph_dependency_failure_detail,
    get_graphiti_upstream_bridge,
    get_idempotency_store,
    get_memory_core,
    get_rate_limiter,
    get_task_queue,
)
from viberecall_mcp.tool_access import is_tool_allowed_for_plan
from viberecall_mcp.tool_registry import build_output_envelope


settings = get_settings()
logger = structlog.get_logger(__name__)
_SEARCH_EPISODE_SCORE = 0.41
_LIGHT_RATE_LIMIT_TOOLS = frozenset({"viberecall_get_status", "viberecall_index_status"})
_HEAVY_RATE_LIMIT_TOOLS = frozenset(
    {"viberecall_save", "viberecall_update_fact", "viberecall_delete_episode", "viberecall_index_repo"}
)


def _seed_payload(arguments: dict) -> dict:
    return {key: value for key, value in arguments.items() if key not in {"cursor", "session"}}


def ensure_scope(token: AuthenticatedToken, required_scope: str) -> None:
    if required_scope in set(token.scopes):
        return
    raise ToolRuntimeError(
        "FORBIDDEN",
        "Missing required scope",
        {"required_scope": required_scope},
    )


def ensure_plan_access(token: AuthenticatedToken, tool_name: str) -> None:
    if is_tool_allowed_for_plan(token.plan, tool_name):
        return
    raise ToolRuntimeError(
        "FORBIDDEN",
        "Tool is not available for this token",
        {"tool_name": tool_name, "plan": token.plan},
    )


def _use_upstream_graphiti_bridge() -> bool:
    if settings.graphiti_mcp_bridge_mode != "upstream_bridge":
        return False
    if settings.memory_backend != "graphiti":
        return False
    return bool((settings.graphiti_api_key or "").strip())


async def ensure_graph_memory_dependencies_ready() -> None:
    detail = await get_graph_dependency_failure_detail()
    if detail is None:
        return
    raise ToolRuntimeError("UPSTREAM_ERROR", detail)


def _rate_limit_capacities(tool_name: str) -> tuple[int, int]:
    token_capacity = settings.rate_limit_token_capacity
    project_capacity = settings.rate_limit_project_capacity
    if tool_name in _HEAVY_RATE_LIMIT_TOOLS:
        return (
            max(1, token_capacity // 6),
            max(1, project_capacity // 6),
        )
    if tool_name in _LIGHT_RATE_LIMIT_TOOLS:
        return (token_capacity, project_capacity)
    return (
        max(1, token_capacity // 3),
        max(1, project_capacity // 3),
    )


def _encode_search_cursor(*, fact_offset: int, episode_offset: int, seed: str) -> str:
    raw = json.dumps(
        {
            "fact_offset": fact_offset,
            "episode_offset": episode_offset,
            "seed": seed,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_search_cursor(cursor: str | None, expected_seed: str) -> tuple[int, int]:
    if cursor is None:
        return 0, 0

    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Malformed cursor") from exc

    if payload.get("seed") != expected_seed:
        raise ValueError("Cursor seed mismatch")

    if "fact_offset" in payload or "episode_offset" in payload:
        fact_offset = payload.get("fact_offset", 0)
        episode_offset = payload.get("episode_offset", 0)
    else:
        fact_offset = payload.get("offset", 0)
        episode_offset = 0

    if not isinstance(fact_offset, int) or fact_offset < 0:
        raise ValueError("Cursor offset invalid")
    if not isinstance(episode_offset, int) or episode_offset < 0:
        raise ValueError("Cursor offset invalid")
    return fact_offset, episode_offset


def _search_result_sort_key(item: dict) -> tuple[float, str, int, str]:
    timestamp = (
        item.get("fact", {}).get("valid_at")
        or item.get("provenance", {}).get("reference_time")
        or item.get("provenance", {}).get("ingested_at")
        or item.get("episode", {}).get("reference_time")
        or item.get("episode", {}).get("ingested_at")
        or ""
    )
    identifier = str(
        item.get("fact", {}).get("id")
        or item.get("episode", {}).get("episode_id")
        or ""
    )
    kind_rank = 1 if item.get("kind") == "fact" else 0
    return (float(item.get("score") or 0.0), timestamp, kind_rank, identifier)


async def enforce_rate_limit(token: AuthenticatedToken, project_id: str, tool_name: str) -> None:
    limiter = get_rate_limiter()
    token_capacity, project_capacity = _rate_limit_capacities(tool_name)
    window_seconds = settings.rate_limit_window_seconds

    token_result = await limiter.check(
        f"token:{token.token_id}:{tool_name}",
        capacity=token_capacity,
        window_seconds=window_seconds,
    )
    if not token_result.allowed:
        rate_limited_count.inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {tool_name}; retry after {token_result.reset_at}",
        )

    project_result = await limiter.check(
        f"project:{project_id}:{tool_name}",
        capacity=project_capacity,
        window_seconds=window_seconds,
    )
    if project_result.allowed:
        return
    rate_limited_count.inc()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Project rate limit exceeded for {tool_name}; retry after {project_result.reset_at}",
    )


def estimate_vibe_tokens(tool_name: str, arguments: dict) -> int:
    if tool_name == "viberecall_save":
        content = str(arguments.get("content") or "")
        approx_tokens = max(1, len(content) // 4)
        return max(1, int(approx_tokens * settings.vibe_in_mul * 1.2))
    if tool_name == "viberecall_update_fact":
        content = str(arguments.get("new_text") or "")
        approx_tokens = max(1, len(content) // 4)
        return max(1, int(approx_tokens * settings.vibe_out_mul * 1.2))
    return 1


async def enforce_quota(
    *,
    session,
    token: AuthenticatedToken,
    project_id: str,
    tool_name: str,
    arguments: dict,
) -> None:
    estimated = estimate_vibe_tokens(tool_name, arguments)
    if estimated <= 0:
        return
    try:
        current_usage = await get_monthly_vibe_tokens(session, project_id=project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "quota_usage_metric_failed",
            project_id=project_id,
            tool_name=tool_name,
            error=str(exc),
        )
        return
    tokens_burn_rate.labels(project=project_id).set(current_usage + estimated)
    _ = token


async def maybe_replay_idempotent_response(
    *,
    tool_name: str,
    project_id: str,
    idempotency_key: str | None,
    payload_hash: str,
) -> dict | None:
    if not idempotency_key:
        return None

    record = await get_idempotency_store().get(f"{project_id}:{tool_name}:{idempotency_key}")
    if record is None:
        return None
    if record.payload_hash != payload_hash:
        raise RuntimeError(json.dumps({"code": "CONFLICT"}))
    return record.response


async def persist_idempotent_response(
    *,
    tool_name: str,
    project_id: str,
    idempotency_key: str | None,
    payload_hash: str,
    response: dict,
) -> None:
    if not idempotency_key:
        return
    await get_idempotency_store().put(
        f"{project_id}:{tool_name}:{idempotency_key}",
        payload_hash,
        response,
        ttl_seconds=24 * 60 * 60,
    )


async def claim_idempotency_slot(
    *,
    tool_name: str,
    project_id: str,
    idempotency_key: str | None,
) -> None:
    if not idempotency_key:
        return
    store = get_idempotency_store()
    claim = getattr(store, "claim", None)
    if claim is None:
        return
    locked = await claim(f"{project_id}:{tool_name}:{idempotency_key}", ttl_seconds=30)
    if not locked:
        raise RuntimeError(json.dumps({"code": "CONFLICT"}))


async def release_idempotency_slot(
    *,
    tool_name: str,
    project_id: str,
    idempotency_key: str | None,
) -> None:
    if not idempotency_key:
        return
    store = get_idempotency_store()
    release = getattr(store, "release", None)
    if release is None:
        return
    await release(f"{project_id}:{tool_name}:{idempotency_key}")


async def handle_save(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
    payload_hash: str,
    idempotency_key: str | None,
) -> dict:
    ensure_plan_access(token, "viberecall_save")
    ensure_scope(token, "memory:write")
    replay = await maybe_replay_idempotent_response(
        tool_name="viberecall_save",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    await enforce_rate_limit(token, project_id, "viberecall_save")
    await enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name="viberecall_save",
        arguments=arguments,
    )

    await ensure_graph_memory_dependencies_ready()

    await claim_idempotency_slot(
        tool_name="viberecall_save",
        project_id=project_id,
        idempotency_key=idempotency_key,
    )

    episode_id = new_id("ep")
    content = str(arguments["content"])
    content_ref: str | None = None
    inline_content: str | None = content
    summary: str | None = None
    if len(content.encode("utf-8")) > settings.raw_episode_inline_max_bytes:
        content_ref = episode_storage_key(project_id, episode_id)
        try:
            await put_text(object_key=content_ref, content=content)
        except ObjectStorageError as exc:
            raise ToolRuntimeError(
                "UPSTREAM_ERROR",
                "Failed to store large episode content",
                {"reason": str(exc)},
            ) from exc
        inline_content = None
        summary = content[:160].strip() or None

    try:
        await create_episode(
            session=arguments["session"],
            episode_id=episode_id,
            project_id=project_id,
            content=inline_content,
            content_ref=content_ref,
            summary=summary,
            reference_time=arguments.get("reference_time"),
            metadata_json=json.dumps(arguments.get("metadata") or {}),
            job_id=None,
            enrichment_status="pending",
        )
        job_id = await get_task_queue().enqueue_ingest(
            episode_id=episode_id,
            project_id=project_id,
            request_id=request_id,
            token_id=token.token_id,
        )
        await set_episode_job_id(
            arguments["session"],
            episode_id=episode_id,
            job_id=job_id,
        )
        response = build_output_envelope(
            request_id=request_id,
            ok=True,
            result={
                "episode_id": episode_id,
                "status": "ACCEPTED",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "enrichment": {"mode": "ASYNC", "job_id": job_id},
            },
        )
        await persist_idempotent_response(
            tool_name="viberecall_save",
            project_id=project_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            response=response,
        )
        return response
    except Exception:
        await release_idempotency_slot(
            tool_name="viberecall_save",
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
        raise


async def handle_search(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_search")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_search")
    await ensure_graph_memory_dependencies_ready()

    seed = make_seed(_seed_payload(arguments))
    fact_offset, episode_offset = _decode_search_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 10)
    filters = arguments.get("filters") or {}

    if _use_upstream_graphiti_bridge():
        try:
            fact_results = await get_graphiti_upstream_bridge().search_facts(
                project_id,
                query=arguments["query"],
                filters=filters,
                sort=arguments.get("sort", "RELEVANCE"),
                limit=limit + 1,
                offset=fact_offset,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "graphiti_upstream_bridge_search_failed",
                project_id=project_id,
                error=str(exc),
            )
            fact_results = await get_memory_core().search(
                project_id,
                query=arguments["query"],
                filters=filters,
                sort=arguments.get("sort", "RELEVANCE"),
                limit=limit + 1,
                offset=fact_offset,
            )
    else:
        fact_results = await get_memory_core().search(
            project_id,
            query=arguments["query"],
            filters=filters,
            sort=arguments.get("sort", "RELEVANCE"),
            limit=limit + 1,
            offset=fact_offset,
        )
    episode_results = await list_recent_raw_episodes(
        arguments["session"],
        project_id=project_id,
        query=arguments["query"],
        window_seconds=settings.recent_episode_window_seconds,
        limit=limit + 1,
        offset=episode_offset,
    )
    merged = fact_results + [
        {
            "kind": "episode",
            "episode": {
                "episode_id": episode["episode_id"],
                "reference_time": episode["reference_time"],
                "ingested_at": episode["ingested_at"],
                "summary": episode["summary"],
                "metadata": episode["metadata"],
            },
            "score": _SEARCH_EPISODE_SCORE,
        }
        for episode in episode_results
    ]
    merged.sort(key=_search_result_sort_key, reverse=True)
    page = []
    fact_consumed = 0
    episode_consumed = 0
    for item in merged[:limit]:
        if item["kind"] == "fact":
            fact_consumed += 1
            page.append(
                {
                    "kind": "fact",
                    "fact": item["fact"],
                    "entities": item["entities"],
                    "provenance": item["provenance"],
                    "score": item["score"],
                }
            )
        else:
            episode_consumed += 1
            page.append(item)
    has_more = len(fact_results) > fact_consumed or len(episode_results) > episode_consumed
    next_cursor = None
    if has_more:
        next_cursor = _encode_search_cursor(
            fact_offset=fact_offset + fact_consumed,
            episode_offset=episode_offset + episode_consumed,
            seed=seed,
        )
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={"results": page, "next_cursor": next_cursor},
    )


async def handle_get_facts(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_get_facts")
    ensure_scope(token, "facts:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_facts")
    await ensure_graph_memory_dependencies_ready()

    seed = make_seed(_seed_payload(arguments))
    offset = decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 50)
    if _use_upstream_graphiti_bridge():
        try:
            facts = await get_graphiti_upstream_bridge().list_facts(
                project_id,
                filters=arguments.get("filters") or {},
                limit=limit + 1,
                offset=offset,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "graphiti_upstream_bridge_get_facts_failed",
                project_id=project_id,
                error=str(exc),
            )
            facts = await get_memory_core().get_facts(
                project_id,
                filters=arguments.get("filters") or {},
                limit=limit + 1,
                offset=offset,
            )
    else:
        facts = await get_memory_core().get_facts(
            project_id,
            filters=arguments.get("filters") or {},
            limit=limit + 1,
            offset=offset,
        )
    page = [
        {
            "id": fact["id"],
            "text": fact["text"],
            "valid_at": fact["valid_at"],
            "invalid_at": fact["invalid_at"],
            "entities": fact["entities"],
            "provenance": fact["provenance"],
        }
        for fact in facts[:limit]
    ]
    next_cursor = encode_cursor(offset + limit, seed) if len(facts) > limit else None
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={"facts": page, "next_cursor": next_cursor},
    )


async def handle_update_fact(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
    payload_hash: str,
    idempotency_key: str | None,
) -> dict:
    ensure_plan_access(token, "viberecall_update_fact")
    ensure_scope(token, "facts:write")
    replay = await maybe_replay_idempotent_response(
        tool_name="viberecall_update_fact",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    await enforce_rate_limit(token, project_id, "viberecall_update_fact")
    await enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name="viberecall_update_fact",
        arguments=arguments,
    )

    await ensure_graph_memory_dependencies_ready()

    await claim_idempotency_slot(
        tool_name="viberecall_update_fact",
        project_id=project_id,
        idempotency_key=idempotency_key,
    )

    try:
        new_fact_id = new_id("fact")
        enqueue_result = await get_task_queue().enqueue_update_fact(
            project_id=project_id,
            request_id=request_id,
            token_id=token.token_id,
            fact_id=arguments["fact_id"],
            new_fact_id=new_fact_id,
            new_text=arguments["new_text"],
            effective_time=arguments["effective_time"],
            reason=arguments.get("reason"),
        )
        result = enqueue_result.immediate_result
        response = build_output_envelope(
            request_id=request_id,
            ok=True,
            result={
                **(
                    result
                    or {
                        "old_fact": {"id": arguments["fact_id"], "invalid_at": arguments["effective_time"]},
                        "new_fact": {"id": new_fact_id, "valid_at": arguments["effective_time"]},
                    }
                ),
                "job_id": enqueue_result.job_id,
            },
        )
        await persist_idempotent_response(
            tool_name="viberecall_update_fact",
            project_id=project_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            response=response,
        )
        return response
    except Exception:
        await release_idempotency_slot(
            tool_name="viberecall_update_fact",
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
        raise


async def handle_timeline(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_timeline")
    ensure_scope(token, "timeline:read")
    await enforce_rate_limit(token, project_id, "viberecall_timeline")
    await ensure_graph_memory_dependencies_ready()

    seed = make_seed(_seed_payload(arguments))
    offset = decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 50)
    if _use_upstream_graphiti_bridge():
        try:
            episodes = await get_graphiti_upstream_bridge().list_timeline(
                project_id,
                from_time=arguments.get("from"),
                to_time=arguments.get("to"),
                limit=limit + 1,
                offset=offset,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "graphiti_upstream_bridge_timeline_failed",
                project_id=project_id,
                error=str(exc),
            )
            episodes = await list_timeline_episodes(
                arguments["session"],
                project_id=project_id,
                from_time=arguments.get("from"),
                to_time=arguments.get("to"),
                limit=limit + 1,
                offset=offset,
            )
    else:
        episodes = await list_timeline_episodes(
            arguments["session"],
            project_id=project_id,
            from_time=arguments.get("from"),
            to_time=arguments.get("to"),
            limit=limit + 1,
            offset=offset,
        )
    page = episodes[:limit]
    next_cursor = encode_cursor(offset + limit, seed) if len(episodes) > limit else None
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={"episodes": page, "next_cursor": next_cursor},
    )


async def handle_get_status(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    _ = arguments
    ensure_plan_access(token, "viberecall_get_status")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_status")

    graphiti_enabled = bool((settings.graphiti_api_key or "").strip())
    status = "ok"
    detail = "ready"
    dependency_detail = await get_graph_dependency_failure_detail()
    if dependency_detail is not None:
        status = "degraded"
        detail = dependency_detail
    elif settings.memory_backend == "graphiti":
        if settings.graphiti_mcp_bridge_mode == "upstream_bridge":
            status, detail = await get_graphiti_upstream_bridge().status(project_id)
        elif not graphiti_enabled:
            status = "degraded"
            detail = "GRAPHITI_API_KEY is empty"

    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "status": status,
            "service": "viberecall-mcp",
            "project_id": project_id,
            "backends": {
                "memory_backend": settings.memory_backend,
                "kv_backend": settings.kv_backend,
                "queue_backend": settings.queue_backend,
            },
            "graphiti": {
                "enabled": graphiti_enabled,
                "bridge_mode": settings.graphiti_mcp_bridge_mode,
                "detail": detail,
            },
        },
    )


async def handle_delete_episode(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_delete_episode")
    ensure_scope(token, "memory:write")
    await enforce_rate_limit(token, project_id, "viberecall_delete_episode")
    await ensure_graph_memory_dependencies_ready()

    episode_id = str(arguments["episode_id"])
    delete_context = await get_episode_for_project(
        arguments["session"],
        project_id=project_id,
        episode_id=episode_id,
    )

    try:
        delete_result = await get_memory_core().delete_episode(project_id, episode_id=episode_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "delete_episode_graph_cleanup_failed",
            project_id=project_id,
            episode_id=episode_id,
            error=str(exc),
        )
        raise ToolRuntimeError(
            "UPSTREAM_ERROR",
            "Episode delete cleanup failed before persistence cleanup",
            {"episode_id": episode_id},
        ) from exc

    if delete_result.remaining_fact_count > 0:
        raise ToolRuntimeError(
            "UPSTREAM_ERROR",
            "Episode delete cleanup incomplete",
            {
                "episode_id": episode_id,
                "deleted_episode_node": delete_result.deleted_episode_node,
                "remaining_fact_count": delete_result.remaining_fact_count,
            },
        )

    if not delete_result.found and delete_context is None:
        return build_output_envelope(
            request_id=request_id,
            ok=True,
            result={
                "episode_id": episode_id,
                "status": "NOT_FOUND",
                "deleted": {
                    "postgres": False,
                    "object_storage": False,
                    "graph": False,
                },
            },
        )

    deleted_row = await delete_episode_for_project(
        arguments["session"],
        project_id=project_id,
        episode_id=episode_id,
    )
    postgres_deleted = deleted_row is not None
    object_deleted = False
    graph_deleted = delete_result.remaining_fact_count == 0 and (
        delete_result.found or delete_context is not None
    )

    if delete_context is not None and delete_context.get("content_ref"):
        try:
            object_deleted = await delete_object(object_key=str(delete_context["content_ref"]))
        except ObjectStorageError as exc:
            logger.warning(
                "delete_episode_object_cleanup_failed",
                project_id=project_id,
                episode_id=episode_id,
                error=str(exc),
            )
    status = "DELETED" if graph_deleted else "NOT_FOUND"

    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "episode_id": episode_id,
            "status": status,
            "deleted": {
                "postgres": postgres_deleted,
                "object_storage": object_deleted,
                "graph": graph_deleted,
            },
        },
    )


async def handle_index_repo(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_index_repo")
    ensure_scope(token, "memory:write")
    await enforce_rate_limit(token, project_id, "viberecall_index_repo")

    mode = str(arguments.get("mode") or "snapshot")
    if mode not in {"snapshot", "diff"}:
        raise ValueError("mode must be either 'snapshot' or 'diff'")

    session = arguments["session"]
    request = await request_index_repo(
        session=session,
        project_id=project_id,
        repo_path=str(arguments["repo_path"]),
        mode=mode,
        base_ref=arguments.get("base_ref"),
        head_ref=arguments.get("head_ref"),
        max_files=int(arguments.get("max_files", 5000)),
        requested_by_token_id=token.token_id,
    )
    try:
        job_id = await get_task_queue().enqueue_index_repo(
            index_id=str(request["index_id"]),
            project_id=project_id,
            request_id=request_id,
            token_id=token.token_id,
        )
    except Exception as exc:
        await mark_index_request_failed(
            session=session,
            index_id=str(request["index_id"]),
            error=str(exc),
        )
        raise
    await attach_index_job_id(
        session=session,
        index_id=str(request["index_id"]),
        job_id=job_id,
    )
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "status": "ACCEPTED",
            "index_id": request["index_id"],
            "job_id": job_id,
            "project_id": request["project_id"],
            "repo_path": request["repo_path"],
            "mode": request["mode"],
            "base_ref": request["base_ref"],
            "head_ref": request["head_ref"],
            "queued_at": request["queued_at"],
        },
    )


async def handle_index_status(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    _ = arguments
    ensure_plan_access(token, "viberecall_index_status")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_index_status")

    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=await index_status(
            session=arguments["session"],
            project_id=project_id,
        ),
    )


async def handle_search_entities(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_search_entities")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_search_entities")

    result = await search_entities(
        session=arguments["session"],
        project_id=project_id,
        query=str(arguments["query"]),
        entity_types=[str(item) for item in (arguments.get("entity_types") or [])],
        limit=int(arguments.get("limit", 20)),
    )
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=result,
    )


def _match_query_in_episode(*, query: str, episode: dict) -> bool:
    if not query:
        return True
    q = query.lower()
    summary = str(episode.get("summary") or "").lower()
    metadata = json.dumps(episode.get("metadata") or {}, sort_keys=True, default=str).lower()
    return q in summary or q in metadata


async def handle_get_context_pack(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_get_context_pack")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_context_pack")

    query = str(arguments["query"])
    limit = int(arguments.get("limit", 12))
    context = await build_context_pack(
        session=arguments["session"],
        project_id=project_id,
        query=query,
        limit=limit,
    )

    timeline_rows = await list_timeline_episodes(
        arguments["session"],
        project_id=project_id,
        from_time=None,
        to_time=None,
        limit=max(limit * 5, 50),
        offset=0,
    )
    matched_timeline = [row for row in timeline_rows if _match_query_in_episode(query=query, episode=row)][:limit]
    facts_timeline = [
        {
            "episode_id": row["episode_id"],
            "reference_time": row.get("reference_time"),
            "ingested_at": row.get("ingested_at"),
            "summary": row.get("summary"),
            "metadata": row.get("metadata") or {},
            "citation_id": f"episode:{row['episode_id']}",
        }
        for row in matched_timeline
    ]

    citations = list(context.get("citations") or [])
    citations.extend(
        [
            {
                "citation_id": f"episode:{row['episode_id']}",
                "source_type": "timeline_episode",
                "episode_id": row["episode_id"],
                "reference_time": row.get("reference_time"),
                "summary": row.get("summary"),
            }
            for row in matched_timeline
        ]
    )
    context["citations"] = citations
    context["facts_timeline"] = facts_timeline

    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=context,
    )
