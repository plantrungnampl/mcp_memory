from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, status

from viberecall_mcp.auth import AuthenticatedToken
from viberecall_mcp.canonical_memory import (
    delete_canonical_episode,
    get_canonical_fact,
    list_canonical_facts,
    save_canonical_episode,
    search_canonical_memory,
    update_canonical_fact,
)
from viberecall_mcp.code_index import (
    build_context_pack,
    index_status,
    normalize_repo_source,
    _normalize_full_snapshot_mode,
    request_index_repo,
    search_entities,
)
from viberecall_mcp.config import get_settings
from viberecall_mcp.errors import ToolRuntimeError
from viberecall_mcp.ids import new_id
from viberecall_mcp.metrics import rate_limited_count, tokens_burn_rate
from viberecall_mcp.object_storage import ObjectStorageError, delete_object, episode_storage_key, put_text
from viberecall_mcp.outbox_dispatcher import dispatch_outbox_events
from viberecall_mcp.pagination import decode_cursor, encode_cursor, make_seed
from viberecall_mcp.repositories.canonical_memory import get_current_fact_by_version_or_group
from viberecall_mcp.repositories.episodes import (
    create_episode,
    delete_episode_for_project,
    get_episode_for_project,
    list_recent_raw_episodes,
    list_timeline_episodes,
)
from viberecall_mcp.repositories.operations import (
    complete_operation,
    create_operation,
    create_outbox_event,
    get_operation as get_operation_record,
)
from viberecall_mcp.repositories.working_memory import (
    get_working_memory,
    patch_working_memory,
)
from viberecall_mcp.repositories.usage_events import get_monthly_vibe_tokens
from viberecall_mcp.runtime import (
    get_graph_dependency_failure_detail,
    get_graphiti_upstream_bridge,
    get_idempotency_store,
    get_memory_core,
    get_rate_limiter,
)
from viberecall_mcp.tool_access import is_tool_allowed_for_plan, token_has_scope
from viberecall_mcp.tool_registry import build_output_envelope


settings = get_settings()
logger = structlog.get_logger(__name__)
_SEARCH_EPISODE_SCORE = 0.41
_LIGHT_RATE_LIMIT_TOOLS = frozenset(
    {
        "viberecall_get_status",
        "viberecall_get_operation",
        "viberecall_index_status",
        "viberecall_get_index_status",
        "viberecall_get_fact",
        "viberecall_working_memory_get",
    }
)
_HEAVY_RATE_LIMIT_TOOLS = frozenset(
    {
        "viberecall_save",
        "viberecall_save_episode",
        "viberecall_update_fact",
        "viberecall_delete_episode",
        "viberecall_index_repo",
        "viberecall_working_memory_patch",
    }
)
_MEMORY_SCOPES = frozenset({"project", "linked", "org"})


def _seed_payload(arguments: dict) -> dict:
    return {key: value for key, value in arguments.items() if key not in {"cursor", "session"}}


def ensure_scope(token: AuthenticatedToken, required_scope: str) -> None:
    if token_has_scope(token.scopes, required_scope):
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


def _iso_or_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _operation_payload(row: dict) -> dict:
    return {
        "operation_id": row["operation_id"],
        "request_id": row.get("request_id"),
        "kind": row["kind"],
        "status": row["status"],
        "resource_type": row.get("resource_type"),
        "resource_id": row.get("resource_id"),
        "job_id": row.get("job_id"),
        "metadata": row.get("metadata_json") or None,
        "result": row.get("result_json") or None,
        "error": row.get("error_json") or None,
        "created_at": _iso_or_none(row.get("created_at")),
        "updated_at": _iso_or_none(row.get("updated_at")),
        "completed_at": _iso_or_none(row.get("completed_at")),
    }


def _resolve_memory_scope(arguments: dict) -> tuple[str, str]:
    requested = str(arguments.get("memory_scope") or "project").strip().lower() or "project"
    if requested not in _MEMORY_SCOPES:
        raise ValueError("memory_scope must be one of: project, linked, org")
    # Retrieval stays project-local in this slice; scope_applied is explicit so callers do not
    # mistake the current behavior for org-wide retrieval.
    return requested, "project"


def _entity_payload(entity: dict | str) -> dict:
    if isinstance(entity, dict):
        entity_id = str(entity.get("id") or entity.get("entity_id") or entity.get("name") or "")
        return {
            "entity_id": entity_id,
            "name": entity.get("name") or entity_id,
            "type": entity.get("type"),
        }
    text = str(entity)
    return {"entity_id": text, "name": text, "type": None}


def _expanded_entities_from_page(page: list[dict], *, limit: int) -> list[dict]:
    ranked: dict[str, dict] = {}
    for item in page:
        if item.get("kind") != "fact":
            continue
        for raw_entity in item.get("entities") or []:
            entity = _entity_payload(raw_entity)
            entity_id = entity["entity_id"]
            if not entity_id:
                continue
            current = ranked.setdefault(
                entity_id,
                {
                    **entity,
                    "support_count": 0,
                    "max_score": 0.0,
                },
            )
            current["support_count"] += 1
            current["max_score"] = max(current["max_score"], float(item.get("score") or 0.0))
    return sorted(
        ranked.values(),
        key=lambda item: (item["support_count"], item["max_score"], item["entity_id"]),
        reverse=True,
    )[:limit]


def _search_seed_entry(item: dict) -> dict:
    if item.get("kind") == "fact":
        fact = item.get("fact") or {}
        return {
            "kind": "fact",
            "id": fact.get("id"),
            "text": fact.get("text"),
            "score": item.get("score"),
        }
    episode = item.get("episode") or {}
    return {
        "kind": "episode",
        "id": episode.get("episode_id"),
        "text": episode.get("summary"),
        "score": item.get("score"),
    }


def _working_memory_patch_from_context(
    *,
    query: str,
    scope_applied: str,
    citations: list[dict],
    facts_timeline: list[dict],
    expanded_entities: list[dict],
) -> dict:
    return {
        "last_context_query": query,
        "last_scope_applied": scope_applied,
        "selected_anchor_ids": [str(item.get("citation_id") or "") for item in citations[:8] if item.get("citation_id")],
        "decision_episode_ids": [
            str(item.get("episode_id") or "")
            for item in facts_timeline[:8]
            if item.get("episode_id")
        ],
        "expanded_entity_ids": [
            str(item.get("entity_id") or "")
            for item in expanded_entities[:8]
            if item.get("entity_id")
        ],
    }


def _working_memory_response(row: dict | None, *, task_id: str, session_id: str) -> dict:
    if row is None:
        return {
            "status": "EMPTY",
            "task_id": task_id,
            "session_id": session_id,
            "state": {},
            "checkpoint_note": None,
            "updated_at": None,
            "expires_at": None,
        }
    return {
        "status": "READY",
        "task_id": row["task_id"],
        "session_id": row["session_id"],
        "state": row.get("state") or {},
        "checkpoint_note": row.get("checkpoint_note"),
        "updated_at": row.get("updated_at"),
        "expires_at": row.get("expires_at"),
    }


def _canonical_search_payload(
    *,
    page: list[dict],
    next_cursor: str | None,
    snapshot_token: str,
    requested_scope: str,
    scope_applied: str,
) -> dict:
    facts = [item for item in page if item.get("kind") == "fact"]
    episodes = [item.get("episode") for item in page if item.get("kind") == "episode"]
    summaries = [
        {
            "kind": item.get("kind"),
            "id": (
                (item.get("fact") or {}).get("fact_group_id")
                or (item.get("fact") or {}).get("fact_version_id")
                or (item.get("episode") or {}).get("episode_id")
            ),
            "text": (
                (item.get("fact") or {}).get("statement")
                or (item.get("fact") or {}).get("text")
                or (item.get("episode") or {}).get("summary")
            ),
            "score": item.get("score"),
        }
        for item in page
    ]
    entities = _expanded_entities_from_page(facts, limit=max(len(page), 1))
    return {
        "results": page,
        "facts": [item.get("fact") for item in facts],
        "entities": entities,
        "episodes": episodes,
        "summaries": summaries,
        "next_cursor": next_cursor,
        "snapshot_token": snapshot_token,
        "scope_requested": requested_scope,
        "scope_applied": scope_applied,
        "seeds": [_search_seed_entry(item) for item in page],
        "recent_episodes": episodes,
        "expanded_entities": entities,
    }


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
    if tool_name in {"viberecall_save", "viberecall_save_episode"}:
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
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
    payload_hash: str,
    idempotency_key: str | None,
) -> dict:
    ensure_plan_access(token, tool_name)
    ensure_scope(token, "memory:write")
    replay = await maybe_replay_idempotent_response(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    await enforce_rate_limit(token, project_id, tool_name)
    await enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name=tool_name,
        arguments=arguments,
    )

    await claim_idempotency_slot(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
    )

    episode_id = new_id("ep")
    operation_id = new_id("op")
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
            commit=False,
        )
        canonical_result = await save_canonical_episode(
            arguments["session"],
            project_id=project_id,
            episode_id=episode_id,
            content=content,
            reference_time=arguments.get("reference_time"),
            metadata=arguments.get("metadata") or {},
        )
        await create_operation(
            arguments["session"],
            operation_id=operation_id,
            project_id=project_id,
            token_id=token.token_id,
            request_id=request_id,
            kind="save",
            resource_type="episode",
            resource_id=episode_id,
            metadata={"reference_time": arguments.get("reference_time")},
        )
        await create_outbox_event(
            arguments["session"],
            event_id=new_id("evt"),
            operation_id=operation_id,
            project_id=project_id,
            event_type="save.ingest",
            payload={
                "episode_id": episode_id,
                "request_id": request_id,
                "token_id": token.token_id,
            },
        )
        await arguments["session"].commit()
        job_id = None
        try:
            await dispatch_outbox_events(arguments["session"], operation_id=operation_id, limit=1)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "save_outbox_dispatch_failed_after_commit",
                project_id=project_id,
                operation_id=operation_id,
                error=str(exc),
            )
        operation = await get_operation_record(arguments["session"], project_id=project_id, operation_id=operation_id)
        job_id = operation.get("job_id") if operation else job_id
        response = build_output_envelope(
            request_id=request_id,
            ok=True,
            result={
                "accepted": True,
                "episode_id": episode_id,
                "operation_id": operation_id,
                "observation_doc_id": canonical_result.observation_doc_id,
                "fact_group_id": canonical_result.fact_group_id,
                "fact_version_id": canonical_result.fact_version_id,
                "ingest_state": "PENDING",
                "status": "ACCEPTED",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "enrichment": {"mode": "ASYNC", "job_id": job_id},
            },
        )
        await persist_idempotent_response(
            tool_name=tool_name,
            project_id=project_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            response=response,
        )
        return response
    except Exception:
        await release_idempotency_slot(
            tool_name=tool_name,
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
        raise


async def handle_search(
    *,
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, tool_name)
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, tool_name)

    requested_scope, scope_applied = _resolve_memory_scope(arguments)
    seed = make_seed(_seed_payload(arguments))
    fact_offset, episode_offset = _decode_search_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 10)
    filters = arguments.get("filters") or {}
    canonical_results: list[dict] = []
    if episode_offset == 0:
        canonical_results = await search_canonical_memory(
            arguments["session"],
            project_id=project_id,
            query=str(arguments["query"]),
            limit=limit + 1,
            offset=fact_offset,
        )
    if canonical_results:
        page = canonical_results[:limit]
        next_cursor = None
        if len(canonical_results) > limit:
            next_cursor = _encode_search_cursor(
                fact_offset=fact_offset + len(page),
                episode_offset=0,
                seed=seed,
            )
        return build_output_envelope(
            request_id=request_id,
            ok=True,
            result=_canonical_search_payload(
                page=page,
                next_cursor=next_cursor,
                snapshot_token=seed,
                requested_scope=requested_scope,
                scope_applied=scope_applied,
            ),
        )

    dependency_detail = await get_graph_dependency_failure_detail()
    if dependency_detail is not None and tool_name == "viberecall_search_memory":
        return build_output_envelope(
            request_id=request_id,
            ok=True,
            result=_canonical_search_payload(
                page=[],
                next_cursor=None,
                snapshot_token=seed,
                requested_scope=requested_scope,
                scope_applied=scope_applied,
            ),
        )

    await ensure_graph_memory_dependencies_ready()

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
    fact_page = [item for item in page if item.get("kind") == "fact"]
    recent_episode_page = [item["episode"] for item in page if item.get("kind") == "episode"]
    expanded_entities = _expanded_entities_from_page(fact_page, limit=max(limit, 1))
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "results": page,
            "next_cursor": next_cursor,
            "snapshot_token": seed,
            "scope_requested": requested_scope,
            "scope_applied": scope_applied,
            "seeds": [_search_seed_entry(item) for item in page],
            "recent_episodes": recent_episode_page,
            "expanded_entities": expanded_entities,
        },
    )


async def handle_get_facts(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_get_facts")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_facts")

    seed = make_seed(_seed_payload(arguments))
    offset = decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 50)
    canonical_facts = await list_canonical_facts(
        arguments["session"],
        project_id=project_id,
        filters=arguments.get("filters") or {},
        limit=limit + 1,
        offset=offset,
    )
    if canonical_facts:
        page = [
            {
                "id": fact["fact_version_id"],
                "fact_group_id": fact["fact_group_id"],
                "text": fact["statement"],
                "statement": fact["statement"],
                "valid_at": fact["valid_from"],
                "invalid_at": fact["valid_to"],
                "entities": [
                    entity_id
                    for entity_id in [fact["subject_entity_id"], fact.get("object_entity_id")]
                    if entity_id
                ],
                "provenance": {"episode_id": fact.get("created_from_episode_id")},
            }
            for fact in canonical_facts[:limit]
        ]
        next_cursor = encode_cursor(offset + limit, seed) if len(canonical_facts) > limit else None
        return build_output_envelope(
            request_id=request_id,
            ok=True,
            result={"facts": page, "next_cursor": next_cursor},
        )

    await ensure_graph_memory_dependencies_ready()

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
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
    payload_hash: str,
    idempotency_key: str | None,
) -> dict:
    ensure_plan_access(token, tool_name)
    ensure_scope(token, "facts:write")
    replay = await maybe_replay_idempotent_response(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    await enforce_rate_limit(token, project_id, tool_name)
    await enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name=tool_name,
        arguments=arguments,
    )

    await claim_idempotency_slot(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
    )

    try:
        fact_group_id = arguments.get("fact_group_id")
        expected_current_version_id = arguments.get("expected_current_version_id")
        if fact_group_id is None and arguments.get("fact_id"):
            current = await get_current_fact_by_version_or_group(
                arguments["session"],
                project_id=project_id,
                fact_version_id=str(arguments["fact_id"]),
            )
            if current is not None:
                fact_group_id = current["fact_group_id"]
                expected_current_version_id = current["fact_version_id"]
        statement = str(arguments.get("statement") or arguments.get("new_text") or "").strip()
        effective_time = str(arguments.get("effective_time") or arguments.get("valid_from") or "").strip()
        if fact_group_id and expected_current_version_id and statement and effective_time:
            operation_id = new_id("op")
            await create_operation(
                arguments["session"],
                operation_id=operation_id,
                project_id=project_id,
                token_id=token.token_id,
                request_id=request_id,
                kind="update_fact",
                resource_type="fact_group",
                resource_id=str(fact_group_id),
                metadata={"mode": "canonical"},
            )
            result = await update_canonical_fact(
                arguments["session"],
                project_id=project_id,
                fact_group_id=str(fact_group_id),
                expected_current_version_id=str(expected_current_version_id),
                statement=statement,
                effective_time=effective_time,
                reason=arguments.get("reason"),
                metadata=dict(arguments.get("metadata") or {}),
            )
            await complete_operation(
                arguments["session"],
                operation_id=operation_id,
                result_payload=result,
            )
            await arguments["session"].commit()
            response = build_output_envelope(
                request_id=request_id,
                ok=True,
                result={**result, "operation_id": operation_id},
            )
            await persist_idempotent_response(
                tool_name=tool_name,
                project_id=project_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                response=response,
            )
            return response

        await ensure_graph_memory_dependencies_ready()
        new_fact_id = new_id("fact")
        operation_id = new_id("op")
        await create_operation(
            arguments["session"],
            operation_id=operation_id,
            project_id=project_id,
            token_id=token.token_id,
            request_id=request_id,
            kind="update_fact",
            resource_type="fact",
            resource_id=arguments["fact_id"],
            metadata={"new_fact_id": new_fact_id},
        )
        await create_outbox_event(
            arguments["session"],
            event_id=new_id("evt"),
            operation_id=operation_id,
            project_id=project_id,
            event_type="update_fact.apply",
            payload={
                "request_id": request_id,
                "token_id": token.token_id,
                "fact_id": arguments["fact_id"],
                "new_fact_id": new_fact_id,
                "new_text": arguments["new_text"],
                "effective_time": arguments["effective_time"],
                "reason": arguments.get("reason"),
            },
        )
        await arguments["session"].commit()
        await dispatch_outbox_events(arguments["session"], operation_id=operation_id, limit=1)
        operation = await get_operation_record(arguments["session"], project_id=project_id, operation_id=operation_id)
        result = (operation or {}).get("result_json")
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
                "job_id": (operation or {}).get("job_id"),
                "operation_id": operation_id,
            },
        )
        await persist_idempotent_response(
            tool_name=tool_name,
            project_id=project_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            response=response,
        )
        return response
    except Exception:
        await release_idempotency_slot(
            tool_name=tool_name,
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
    ensure_scope(token, "memory:read")
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
    ensure_scope(token, "ops:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_operation")

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
                "queue_backend": settings.queue_backend,
            },
            "graphiti": {
                "enabled": graphiti_enabled,
                "detail": detail,
            },
        },
    )


async def handle_get_operation(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_get_operation")
    ensure_scope(token, "ops:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_status")
    await dispatch_outbox_events(arguments["session"], operation_id=str(arguments["operation_id"]), limit=1)
    operation = await get_operation_record(
        arguments["session"],
        project_id=project_id,
        operation_id=str(arguments["operation_id"]),
    )
    if operation is None:
        raise ToolRuntimeError("NOT_FOUND", "Operation not found", {"operation_id": arguments["operation_id"]})
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={"operation": _operation_payload(operation)},
    )


async def handle_get_fact(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_get_fact")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_fact")
    fact = await get_canonical_fact(
        arguments["session"],
        project_id=project_id,
        fact_version_id=arguments.get("fact_version_id"),
        fact_group_id=arguments.get("fact_group_id"),
    )
    if fact is None:
        raise ToolRuntimeError(
            "NOT_FOUND",
            "Fact not found",
            {
                "fact_version_id": arguments.get("fact_version_id"),
                "fact_group_id": arguments.get("fact_group_id"),
            },
        )
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=fact,
    )


async def handle_delete_episode(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_delete_episode")
    ensure_scope(token, "delete:write")
    await enforce_rate_limit(token, project_id, "viberecall_delete_episode")

    episode_id = str(arguments["episode_id"])
    delete_context = await get_episode_for_project(
        arguments["session"],
        project_id=project_id,
        episode_id=episode_id,
    )

    dependency_detail = await get_graph_dependency_failure_detail()
    delete_result = None
    graph_deleted = False
    graph_skipped = dependency_detail is not None

    if dependency_detail is None:
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
        graph_deleted = delete_result.remaining_fact_count == 0 and (
            delete_result.found or delete_context is not None
        )
    else:
        logger.warning(
            "delete_episode_graph_cleanup_skipped",
            project_id=project_id,
            episode_id=episode_id,
            detail=dependency_detail,
        )

    canonical_deleted = await delete_canonical_episode(
        arguments["session"],
        project_id=project_id,
        episode_id=episode_id,
    )
    canonical_found = bool(canonical_deleted["fact_group_ids"] or canonical_deleted["fact_version_ids"])

    if not graph_deleted and not canonical_found and delete_context is None:
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
                    "canonical": False,
                    "graph_skipped": graph_skipped,
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
    status = "DELETED" if (graph_deleted or canonical_found or postgres_deleted) else "NOT_FOUND"

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
                "canonical": canonical_found,
                "graph_skipped": graph_skipped,
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
    ensure_scope(token, "index:run")
    await enforce_rate_limit(token, project_id, "viberecall_index_repo")

    mode = _normalize_full_snapshot_mode(arguments.get("mode"))
    repo_source = normalize_repo_source(arguments.get("repo_source") or {})

    session = arguments["session"]
    request = await request_index_repo(
        session=session,
        project_id=project_id,
        repo_source=repo_source,
        mode=mode,
        max_files=int(arguments.get("max_files", 5000)),
        requested_by_token_id=token.token_id,
        commit=False,
    )
    operation_id = new_id("op")
    await create_operation(
        session,
        operation_id=operation_id,
        project_id=project_id,
        token_id=token.token_id,
        request_id=request_id,
        kind="index_repo",
        resource_type="index",
        resource_id=str(request["index_run_id"]),
        metadata={"repo_source": request["repo_source"]},
    )
    await create_outbox_event(
        session,
        event_id=new_id("evt"),
        operation_id=operation_id,
        project_id=project_id,
        event_type="index_repo.run",
        payload={
            "index_id": str(request["index_run_id"]),
            "request_id": request_id,
            "token_id": token.token_id,
        },
    )
    await session.commit()
    await dispatch_outbox_events(session, operation_id=operation_id, limit=1)
    operation = await get_operation_record(session, project_id=project_id, operation_id=operation_id)
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "accepted": True,
            "index_run_id": request["index_run_id"],
            "operation_id": operation_id,
            "job_id": (operation or {}).get("job_id"),
            "project_id": request["project_id"],
            "repo_source": request["repo_source"],
            "mode": request["mode"],
            "queued_at": request["queued_at"],
        },
    )


async def handle_index_status(
    *,
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, tool_name)
    ensure_scope(token, "index:read")
    await enforce_rate_limit(token, project_id, tool_name)

    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=await index_status(
            session=arguments["session"],
            project_id=project_id,
            index_run_id=str(arguments.get("index_run_id") or "").strip() or None,
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
    ensure_scope(token, "index:read")
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
    ensure_scope(token, "index:read")
    await enforce_rate_limit(token, project_id, "viberecall_get_context_pack")

    query = str(arguments["query"])
    limit = int(arguments.get("limit", 12))
    requested_scope, scope_applied = _resolve_memory_scope(arguments)
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
    code_anchors = [item for item in citations if item.get("source_type") == "code_chunk"]
    expanded_entities = [
        _entity_payload(item)
        for item in (context.get("relevant_symbols") or [])[:limit]
    ]
    working_memory = None
    task_id = arguments.get("task_id")
    session_id = arguments.get("session_id")
    if task_id and session_id:
        working_memory = _working_memory_response(
            await get_working_memory(
                arguments["session"],
                project_id=project_id,
                task_id=str(task_id),
                session_id=str(session_id),
            ),
            task_id=str(task_id),
            session_id=str(session_id),
        )
    context["scope_requested"] = requested_scope
    context["scope_applied"] = scope_applied
    context["code_anchors"] = code_anchors
    context["decision_history"] = facts_timeline
    context["reasoning_graph"] = {
        "query": query,
        "expanded_entities": expanded_entities,
        "anchor_count": len(code_anchors),
    }
    context["working_memory_patch"] = _working_memory_patch_from_context(
        query=query,
        scope_applied=scope_applied,
        citations=code_anchors,
        facts_timeline=facts_timeline,
        expanded_entities=expanded_entities,
    )
    if working_memory is not None:
        context["working_memory"] = working_memory

    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=context,
    )


async def handle_working_memory_get(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_working_memory_get")
    ensure_scope(token, "memory:read")
    await enforce_rate_limit(token, project_id, "viberecall_working_memory_get")

    task_id = str(arguments["task_id"])
    session_id = str(arguments["session_id"])
    row = await get_working_memory(
        arguments["session"],
        project_id=project_id,
        task_id=task_id,
        session_id=session_id,
    )
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=_working_memory_response(row, task_id=task_id, session_id=session_id),
    )


async def handle_working_memory_patch(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    ensure_plan_access(token, "viberecall_working_memory_patch")
    ensure_scope(token, "memory:write")
    await enforce_rate_limit(token, project_id, "viberecall_working_memory_patch")

    task_id = str(arguments["task_id"])
    session_id = str(arguments["session_id"])
    row = await patch_working_memory(
        arguments["session"],
        project_id=project_id,
        task_id=task_id,
        session_id=session_id,
        patch=dict(arguments.get("patch") or {}),
        checkpoint_note=arguments.get("checkpoint_note"),
        expires_at=arguments.get("expires_at"),
        commit=True,
    )
    return build_output_envelope(
        request_id=request_id,
        ok=True,
        result=_working_memory_response(row, task_id=task_id, session_id=session_id),
    )
