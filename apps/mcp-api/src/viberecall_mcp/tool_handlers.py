from __future__ import annotations

import json
from datetime import datetime, timezone

from viberecall_mcp.auth import AuthenticatedToken
from viberecall_mcp.config import get_settings
from viberecall_mcp.errors import ToolRuntimeError
from viberecall_mcp.ids import new_id
from viberecall_mcp.metrics import quota_exceeded_count, rate_limited_count
from viberecall_mcp.object_storage import ObjectStorageError, episode_storage_key, put_text
from viberecall_mcp.pagination import decode_cursor, encode_cursor, make_seed
from viberecall_mcp.quota import monthly_quota_for_plan, next_month_reset_at
from viberecall_mcp.repositories.episodes import (
    create_episode,
    list_recent_raw_episodes,
    list_timeline_episodes,
    set_episode_job_id,
)
from viberecall_mcp.repositories.usage_events import get_monthly_vibe_tokens
from viberecall_mcp.runtime import (
    get_idempotency_store,
    get_memory_core,
    get_rate_limiter,
    get_task_queue,
)
from viberecall_mcp.tool_access import is_tool_allowed_for_plan
from viberecall_mcp.tool_registry import build_output_envelope


settings = get_settings()


def _seed_payload(arguments: dict) -> dict:
    return {key: value for key, value in arguments.items() if key not in {"cursor", "session"}}


def ensure_scope(token: AuthenticatedToken, required_scope: str) -> None:
    if required_scope not in token.scopes:
        raise PermissionError(f"Missing required scope: {required_scope}")


def ensure_plan_access(token: AuthenticatedToken, tool_name: str) -> None:
    if not is_tool_allowed_for_plan(token.plan, tool_name):
        raise PermissionError(f"Tool {tool_name} is not available on plan {token.plan}")


async def enforce_rate_limit(token: AuthenticatedToken, project_id: str) -> None:
    limiter = get_rate_limiter()
    token_result = await limiter.check(
        f"token:{token.token_id}",
        capacity=settings.rate_limit_token_capacity,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not token_result.allowed:
        rate_limited_count.inc()
        raise RuntimeError(json.dumps({"code": "RATE_LIMITED", "reset_at": token_result.reset_at}))

    project_result = await limiter.check(
        f"project:{project_id}",
        capacity=settings.rate_limit_project_capacity,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not project_result.allowed:
        rate_limited_count.inc()
        raise RuntimeError(json.dumps({"code": "RATE_LIMITED", "reset_at": project_result.reset_at}))


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
    cap = monthly_quota_for_plan(token.plan)
    if cap is None:
        return
    current = await get_monthly_vibe_tokens(session, project_id=project_id)
    estimated = estimate_vibe_tokens(tool_name, arguments)
    if current + estimated > cap:
        quota_exceeded_count.inc()
        raise ToolRuntimeError(
            "QUOTA_EXCEEDED",
            "Monthly VibeTokens quota exceeded",
            {
                "limit": cap,
                "current": current,
                "estimated": estimated,
                "reset_at": next_month_reset_at(),
            },
        )


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
    await enforce_rate_limit(token, project_id)
    await enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name="viberecall_save",
        arguments=arguments,
    )

    replay = await maybe_replay_idempotent_response(
        tool_name="viberecall_save",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

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
    await enforce_rate_limit(token, project_id)

    seed = make_seed(_seed_payload(arguments))
    offset = decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 10)
    filters = arguments.get("filters") or {}

    fact_results = await get_memory_core().search(
        project_id,
        query=arguments["query"],
        filters=filters,
        sort=arguments.get("sort", "RELEVANCE"),
        limit=limit + 1,
        offset=offset,
    )
    episode_results = await list_recent_raw_episodes(
        arguments["session"],
        project_id=project_id,
        query=arguments["query"],
        window_seconds=settings.recent_episode_window_seconds,
        limit=5,
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
            "score": 0.41,
        }
        for episode in episode_results
    ]
    merged.sort(
        key=lambda item: (
            item["score"],
            (
                item.get("fact", {}).get("valid_at")
                or item.get("provenance", {}).get("ingested_at")
                or item.get("episode", {}).get("ingested_at")
                or ""
            ),
        ),
        reverse=True,
    )
    page = []
    for item in merged[:limit]:
        if item["kind"] == "fact":
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
            page.append(item)
    next_cursor = encode_cursor(offset + limit, seed) if len(merged) > limit else None
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
    await enforce_rate_limit(token, project_id)

    seed = make_seed(_seed_payload(arguments))
    offset = decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 50)
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
    await enforce_rate_limit(token, project_id)
    await enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name="viberecall_update_fact",
        arguments=arguments,
    )

    replay = await maybe_replay_idempotent_response(
        tool_name="viberecall_update_fact",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

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
    await enforce_rate_limit(token, project_id)

    seed = make_seed(_seed_payload(arguments))
    offset = decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 50)
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
