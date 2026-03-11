from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, status

from viberecall_mcp.auth import AuthenticatedToken
from viberecall_mcp.canonical_memory import (
    delete_canonical_episode,
    explain_canonical_fact,
    find_canonical_paths,
    get_canonical_fact,
    get_canonical_neighbors,
    list_canonical_facts,
    merge_canonical_entities,
    pin_canonical_memory,
    resolve_reference as resolve_canonical_reference,
    save_canonical_episode,
    search_canonical_entities,
    search_canonical_memory,
    split_canonical_entity,
    update_canonical_fact,
)
from viberecall_mcp.code_index import (
    _normalize_full_snapshot_mode,
    attach_index_job_id,
    build_context_pack,
    index_status,
    mark_index_request_failed,
    normalize_repo_source,
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
    set_episode_job_id,
)
from viberecall_mcp.repositories.operations import (
    complete_operation,
    create_operation,
    create_outbox_event,
    get_operation as get_operation_record,
)
from viberecall_mcp.repositories.usage_events import get_monthly_vibe_tokens
from viberecall_mcp.repositories.working_memory import (
    get_working_memory,
    patch_working_memory,
)
from viberecall_mcp.runtime import (
    get_graph_dependency_failure_detail,
    get_graphiti_upstream_bridge,
    get_idempotency_store,
    get_memory_core,
    get_rate_limiter,
    get_task_queue,
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
        "viberecall_explain_fact",
        "viberecall_resolve_reference",
        "viberecall_get_neighbors",
        "viberecall_find_paths",
        "viberecall_working_memory_get",
    }
)
_HEAVY_RATE_LIMIT_TOOLS = frozenset(
    {
        "viberecall_save",
        "viberecall_save_episode",
        "viberecall_update_fact",
        "viberecall_pin_memory",
        "viberecall_merge_entities",
        "viberecall_split_entity",
        "viberecall_delete_episode",
        "viberecall_index_repo",
        "viberecall_working_memory_patch",
    }
)
_MEMORY_SCOPES = frozenset({"project", "linked", "org"})


def _seed_payload(arguments: dict) -> dict:
    return {
        key: value
        for key, value in arguments.items()
        if key not in {"cursor", "session", "snapshot_token"}
    }


def _normalize_entity_kinds(arguments: dict) -> list[str]:
    kinds = arguments.get("entity_kinds")
    if kinds is None:
        kinds = arguments.get("entity_types") or []
    return [str(item) for item in kinds]


def _normalize_salience_classes(values: list[str] | None) -> list[str]:
    return [str(item).upper() for item in (values or []) if str(item).strip()]


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


def _search_result_sort_key(item: dict) -> tuple[float, float, str, int, str]:
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
    salience_score = (
        item.get("fact", {}).get("salience_score")
        or item.get("episode", {}).get("salience_score")
        or 0.5
    )
    return (float(item.get("score") or 0.0), float(salience_score), timestamp, kind_rank, identifier)


def _salience_class_rank(value: str | None) -> int:
    normalized = str(value or "WARM").upper()
    if normalized == "PINNED":
        return 5
    if normalized == "HOT":
        return 4
    if normalized == "WARM":
        return 3
    if normalized == "COLD":
        return 2
    if normalized == "ARCHIVED":
        return 1
    return 0


def _episode_context_sort_key(item: dict) -> tuple[int, float, str, str]:
    timestamp = str(item.get("reference_time") or item.get("ingested_at") or "")
    episode_id = str(item.get("episode_id") or "")
    return (
        _salience_class_rank(item.get("salience_class")),
        float(item.get("salience_score") or 0.5),
        timestamp,
        episode_id,
    )


def _iso_or_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _operation_payload(row: dict) -> dict:
    status = str(row["status"])
    metadata = row.get("metadata_json") or None
    return {
        "operation_id": row["operation_id"],
        "request_id": row.get("request_id"),
        "kind": row["kind"],
        "operation_type": row["kind"],
        "status": status,
        "retryable": status == "FAILED_RETRYABLE",
        "current_step": (metadata or {}).get("current_step") if isinstance(metadata, dict) else None,
        "resource_type": row.get("resource_type"),
        "resource_id": row.get("resource_id"),
        "job_id": row.get("job_id"),
        "metadata": metadata,
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


def _match_query_in_episode(*, query: str, episode: dict) -> bool:
    if not query:
        return True
    q = query.lower()
    summary = str(episode.get("summary") or "").lower()
    metadata = json.dumps(episode.get("metadata") or {}, sort_keys=True, default=str).lower()
    return q in summary or q in metadata


from viberecall_mcp import _tool_handlers_graph as _graph_handlers
from viberecall_mcp import _tool_handlers_index as _index_handlers
from viberecall_mcp import _tool_handlers_memory as _memory_handlers
from viberecall_mcp import _tool_handlers_ops as _ops_handlers
from viberecall_mcp import _tool_handlers_resolution as _resolution_handlers


handle_save = _memory_handlers.handle_save
handle_search = _memory_handlers.handle_search
handle_get_facts = _memory_handlers.handle_get_facts
handle_update_fact = _memory_handlers.handle_update_fact
handle_timeline = _memory_handlers.handle_timeline
handle_get_fact = _memory_handlers.handle_get_fact
handle_pin_memory = _memory_handlers.handle_pin_memory
handle_delete_episode = _memory_handlers.handle_delete_episode

handle_index_repo = _index_handlers.handle_index_repo
handle_index_status = _index_handlers.handle_index_status
handle_get_context_pack = _index_handlers.handle_get_context_pack

handle_search_entities = _graph_handlers.handle_search_entities
handle_resolve_reference = _graph_handlers.handle_resolve_reference
handle_get_neighbors = _graph_handlers.handle_get_neighbors
handle_find_paths = _graph_handlers.handle_find_paths
handle_explain_fact = _graph_handlers.handle_explain_fact

handle_merge_entities = _resolution_handlers.handle_merge_entities
handle_split_entity = _resolution_handlers.handle_split_entity

handle_get_status = _ops_handlers.handle_get_status
handle_get_operation = _ops_handlers.handle_get_operation
handle_working_memory_get = _ops_handlers.handle_working_memory_get
handle_working_memory_patch = _ops_handlers.handle_working_memory_patch


__all__ = [
    "attach_index_job_id",
    "build_context_pack",
    "complete_operation",
    "create_episode",
    "create_operation",
    "create_outbox_event",
    "delete_canonical_episode",
    "delete_episode_for_project",
    "delete_object",
    "dispatch_outbox_events",
    "ensure_plan_access",
    "ensure_scope",
    "enforce_rate_limit",
    "explain_canonical_fact",
    "find_canonical_paths",
    "get_canonical_fact",
    "get_canonical_neighbors",
    "get_current_fact_by_version_or_group",
    "get_graph_dependency_failure_detail",
    "get_graphiti_upstream_bridge",
    "get_memory_core",
    "get_monthly_vibe_tokens",
    "get_operation_record",
    "get_task_queue",
    "get_working_memory",
    "handle_delete_episode",
    "handle_explain_fact",
    "handle_find_paths",
    "handle_get_context_pack",
    "handle_get_fact",
    "handle_get_facts",
    "handle_get_neighbors",
    "handle_get_operation",
    "handle_get_status",
    "handle_index_repo",
    "handle_index_status",
    "handle_merge_entities",
    "handle_pin_memory",
    "handle_resolve_reference",
    "handle_save",
    "handle_search",
    "handle_search_entities",
    "handle_split_entity",
    "handle_timeline",
    "handle_update_fact",
    "handle_working_memory_get",
    "handle_working_memory_patch",
    "index_status",
    "list_canonical_facts",
    "list_recent_raw_episodes",
    "list_timeline_episodes",
    "logger",
    "mark_index_request_failed",
    "patch_working_memory",
    "pin_canonical_memory",
    "put_text",
    "request_index_repo",
    "resolve_canonical_reference",
    "save_canonical_episode",
    "search_canonical_entities",
    "search_canonical_memory",
    "search_entities",
    "set_episode_job_id",
    "settings",
    "split_canonical_entity",
    "update_canonical_fact",
]
