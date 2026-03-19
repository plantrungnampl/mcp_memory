from __future__ import annotations

import calendar
import hashlib
import hmac
import json
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import PurePosixPath
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.auth import hash_token
from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane_auth import AuthenticatedControlPlaneUser
from viberecall_mcp.ids import new_id
from viberecall_mcp.repositories.audit_logs import insert_audit_log
from viberecall_mcp.repositories.projects import (
    claim_project_owner_if_unowned,
    get_project_for_owner,
)
from viberecall_mcp.runtime import (
    build_graph_dependency_detail,
    get_idempotency_store,
    probe_runtime_dependencies,
)


settings = get_settings()

ApiLogsRange = Literal["24h", "7d", "30d", "90d", "all"]
ApiLogsStatusFilter = Literal["all", "success", "error"]


def _include_unowned_projects() -> bool:
    return settings.app_env.lower() == "development"


async def _ensure_export_dependencies_ready() -> None:
    dependency_state = await probe_runtime_dependencies()
    if dependency_state["status"] == "ok":
        return

    failing_check = next(
        (
            (name, check)
            for name, check in (dependency_state.get("checks") or {}).items()
            if check.get("status") == "error"
        ),
        None,
    )
    backend = dependency_state.get("runtime", {}).get("memory_backend", "unknown")
    detail = None
    if failing_check is not None:
        check_name, check_payload = failing_check
        check_detail = check_payload.get("detail")
        detail = check_name if not check_detail else f"{check_name}: {check_detail}"
    detail_suffix = f": {detail}" if detail else ""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Export dependency check failed for memory backend '{backend}'{detail_suffix}",
    )


async def _ensure_graph_dependencies_ready() -> None:
    dependency_state = await probe_runtime_dependencies()
    if dependency_state["status"] == "ok":
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=build_graph_dependency_detail(dependency_state),
    )


def _serialize_project(project: dict) -> dict:
    return {
        "id": project["id"],
        "name": project["name"],
        "plan": project["plan"],
        "created_at": project["created_at"],
    }


def _serialize_project_overview(project: dict) -> dict:
    return {
        "id": project["id"],
        "name": project["name"],
        "plan": project["plan"],
        "created_at": project["created_at"],
        "last_activity_at": project.get("last_activity_at"),
        "vibe_tokens_window": int(project.get("vibe_tokens_window", 0) or 0),
        "token_preview": project.get("token_preview"),
        "token_status": project.get("token_status", "missing"),
        "health_status": project.get("health_status", "idle"),
    }


def _normalize_index_error_payload(error_payload: object | None) -> tuple[str | None, str | None]:
    if isinstance(error_payload, dict):
        code = error_payload.get("code")
        message = error_payload.get("message")
        return (
            str(code).strip() or None if code is not None else None,
            str(message).strip() or None if message is not None else None,
        )
    if error_payload is None:
        return None, None
    message = str(error_payload).strip()
    return None, message or None


def _build_project_index_summary(index_payload: dict, *, now: datetime | None = None) -> dict:
    current_now = now or datetime.now(timezone.utc)
    current_run = index_payload.get("current_run") or {}
    latest_ready = index_payload.get("latest_ready_snapshot") or {}
    raw_status = str(index_payload.get("status") or "EMPTY").upper()

    queued_at = current_run.get("queued_at")
    started_at = current_run.get("started_at")
    completed_at = current_run.get("completed_at")
    latest_ready_at = latest_ready.get("indexed_at")
    current_run_id = current_run.get("index_run_id")

    age_anchor = (
        _parse_iso_datetime(completed_at)
        or _parse_iso_datetime(started_at)
        or _parse_iso_datetime(queued_at)
        or _parse_iso_datetime(latest_ready_at)
    )
    age_seconds = None
    if age_anchor is not None:
        age_seconds = max(0, int((current_now - age_anchor).total_seconds()))

    status = "missing"
    recommended_action = "start_index"
    if raw_status == "READY":
        status = "ready"
        recommended_action = "none"
    elif raw_status == "FAILED":
        status = "failed"
        recommended_action = "retry"
    elif raw_status == "QUEUED":
        status = "stalled" if age_seconds is not None and age_seconds > 120 else "queued"
        recommended_action = "check_workers" if status == "stalled" else "wait"
    elif raw_status == "RUNNING":
        status = "stalled" if age_seconds is not None and age_seconds > 900 else "running"
        recommended_action = "check_workers" if status == "stalled" else "wait"

    error_code, error_message = _normalize_index_error_payload(current_run.get("error"))

    return {
        "status": status,
        "current_run_id": current_run_id,
        "latest_ready_at": latest_ready_at,
        "queued_at": queued_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "age_seconds": age_seconds,
        "error_code": error_code,
        "error_message": error_message,
        "recommended_action": recommended_action,
    }


def _serialize_token(token: dict, *, plaintext: str | None = None) -> dict:
    return {
        "token_id": token["token_id"],
        "prefix": token["prefix"],
        "plaintext": plaintext,
        "created_at": token["created_at"],
        "last_used_at": token.get("last_used_at"),
        "revoked_at": token.get("revoked_at"),
        "expires_at": token.get("expires_at"),
        "status": _token_status(token),
    }


def _serialize_index_bundle(bundle: dict) -> dict:
    return {
        "bundle_id": bundle["bundle_id"],
        "bundle_ref": f"bundle://{bundle['bundle_id']}",
        "filename": bundle["filename"],
        "byte_size": int(bundle["byte_size"]),
        "sha256": bundle["sha256"],
        "created_at": bundle["created_at"],
        "expires_at": bundle.get("expires_at"),
    }


def _token_status(token: dict) -> str:
    expires_at = _coerce_datetime(token.get("expires_at"))
    revoked_at = _coerce_datetime(token.get("revoked_at"))
    now = datetime.now(timezone.utc)
    if expires_at is not None and expires_at <= now:
        return "expired"
    if revoked_at is None:
        return "active"
    if revoked_at > now:
        return "grace"
    return "revoked"


def _coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


def _build_connection(project_id: str, token_prefix: str | None) -> dict:
    return {
        "endpoint": f"{settings.public_mcp_base_url.rstrip('/')}/p/{project_id}/mcp",
        "token_preview": token_prefix,
    }


def _default_scopes_for_plan(plan: str) -> list[str]:
    _ = plan
    return [
        "memory:read",
        "memory:write",
        "facts:write",
        "entities:read",
        "graph:read",
        "index:read",
        "index:run",
        "ops:read",
        "delete:write",
    ]


def _normalize_requested_scopes(scopes: list[str] | None, *, plan: str) -> list[str]:
    allowed = set(_default_scopes_for_plan(plan)) | {"facts:read", "timeline:read"}
    if scopes is None:
        return _default_scopes_for_plan(plan)

    normalized: list[str] = []
    seen: set[str] = set()
    for scope in scopes:
        value = scope.strip()
        if not value:
            continue
        if value not in allowed:
            supported = ", ".join(sorted(allowed))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported scope: {value}. Supported scopes: {supported}",
            )
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one scope is required",
        )
    return normalized


def _serialize_api_log(log: dict) -> dict:
    return {
        "id": int(log["id"]),
        "request_id": log.get("request_id"),
        "project_id": log.get("project_id"),
        "token_id": log.get("token_id"),
        "tool_name": log.get("tool_name"),
        "action": log.get("action"),
        "args_hash": log.get("args_hash"),
        "status": log.get("status"),
        "created_at": log.get("created_at"),
        "latency_ms": log.get("latency_ms"),
    }


def _resolve_api_logs_window(range_name: ApiLogsRange, *, now: datetime) -> tuple[datetime | None, datetime | None]:
    if range_name == "all":
        return None, None
    if range_name == "24h":
        return now - timedelta(hours=24), now
    if range_name == "7d":
        return now - timedelta(days=7), now
    if range_name == "30d":
        return now - timedelta(days=30), now
    return now - timedelta(days=90), now


def _format_change_pct(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round(((current - previous) / previous) * 100.0, 1)


def _format_api_log_token_prefix(log: dict) -> str | None:
    token_prefix = log.get("token_prefix")
    if token_prefix:
        return str(token_prefix)
    token_id = log.get("token_id")
    if not token_id:
        return None
    token_id_str = str(token_id)
    return token_id_str if len(token_id_str) <= 14 else f"{token_id_str[:14]}…"


def _serialize_api_log_analytics_row(log: dict) -> dict:
    latency_ms = log.get("latency_ms")
    return {
        "id": int(log["id"]),
        "time": log.get("created_at"),
        "tool": log.get("tool_name"),
        "status": log.get("status"),
        "latency_ms": float(latency_ms) if latency_ms is not None else None,
        "token_prefix": _format_api_log_token_prefix(log),
        "request_id": log.get("request_id"),
        "action": log.get("action"),
    }


def _projected_monthly_usage(*, current_month_vibe_tokens: int, now: datetime) -> int:
    days_elapsed = max(now.day, 1)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    return int(round((current_month_vibe_tokens / days_elapsed) * days_in_month))


def _plan_monthly_price_cents(plan: str) -> int:
    if plan == "pro":
        return 4900
    if plan == "team":
        return 19_900
    return 0


def _serialize_export(record: dict | None) -> dict | None:
    if record is None:
        return None
    return {
        "export_id": record["export_id"],
        "project_id": record["project_id"],
        "status": record["status"],
        "format": record["format"],
        "object_url": record.get("object_url"),
        "expires_at": record.get("expires_at"),
        "error": record.get("error"),
        "requested_by": record.get("requested_by"),
        "requested_at": record.get("requested_at"),
        "completed_at": record.get("completed_at"),
        "job_id": record.get("job_id"),
    }


def _parse_iso_datetime(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except ValueError:
        return None


def _fact_event_time(fact: dict) -> datetime | None:
    direct = _parse_iso_datetime(fact.get("valid_at")) or _parse_iso_datetime(fact.get("ingested_at"))
    if direct is not None:
        return direct

    provenance = fact.get("provenance") or {}
    return _parse_iso_datetime(provenance.get("reference_time")) or _parse_iso_datetime(provenance.get("ingested_at"))


def _looks_like_repo_path(value: str) -> bool:
    text = value.strip()
    if not text or "/" not in text:
        return False
    path = PurePosixPath(text)
    suffix = path.suffix.lower()
    return suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".sql", ".yaml", ".yml"}


def _is_code_like_entity(*, entity_id: str, entity_type: str, entity_name: str) -> bool:
    normalized_id = entity_id.strip().lower()
    normalized_type = entity_type.strip().lower()
    normalized_name = entity_name.strip()
    if normalized_type in {"file", "module", "symbol", "import"}:
        return True
    if any(normalized_id.startswith(prefix) for prefix in ("file:", "module:", "symbol:", "import:")):
        return True
    return _looks_like_repo_path(normalized_name) or _looks_like_repo_path(entity_id)


def _build_concept_graph_payload(
    *,
    facts: list[dict],
    query_text: str | None,
    entity_types: set[str],
    last_days: int | None,
    max_nodes: int,
    max_edges: int,
) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=last_days) if last_days is not None else None
    normalized_query = (query_text or "").strip().lower()
    type_filters = {item.strip() for item in entity_types if item.strip()}

    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str], dict] = {}
    neighbors: dict[str, set[str]] = defaultdict(set)
    code_like_nodes_seen = False

    for fact in facts:
        invalid_at = _parse_iso_datetime(fact.get("invalid_at"))
        if invalid_at is not None and invalid_at <= now:
            continue

        event_time = _fact_event_time(fact)
        if cutoff is not None and event_time is not None and event_time < cutoff:
            continue

        provenance = fact.get("provenance") or {}
        episode_ids = [str(value) for value in (provenance.get("episode_ids") or []) if value]
        reference_time = (event_time.isoformat() if event_time is not None else None) or (
            provenance.get("reference_time")
        )
        fact_text = str(fact.get("text") or "").strip()
        hover_text = fact_text[:180]

        unique_entity_ids: set[str] = set()
        for entity in fact.get("entities") or []:
            entity_id = str(entity.get("id") or "").strip()
            if not entity_id:
                continue

            entity_type = str(entity.get("type") or "Unknown").strip() or "Unknown"
            entity_name = str(entity.get("name") or entity_id).strip() or entity_id

            if _is_code_like_entity(entity_id=entity_id, entity_type=entity_type, entity_name=entity_name):
                code_like_nodes_seen = True
                continue
            if type_filters and entity_type not in type_filters:
                continue

            node = nodes.get(entity_id)
            if node is None:
                node = {
                    "entity_id": entity_id,
                    "type": entity_type,
                    "name": entity_name,
                    "fact_count": 0,
                    "episode_ids": set(),
                    "last_seen_at": reference_time,
                    "hover_items": [],
                }
                nodes[entity_id] = node

            node["fact_count"] += 1
            node["episode_ids"].update(episode_ids)
            node["last_seen_at"] = max(
                [value for value in [node["last_seen_at"], reference_time] if value is not None],
                default=node["last_seen_at"],
            )
            if hover_text and len(node["hover_items"]) < 3:
                node["hover_items"].append({"text": hover_text, "reference_time": reference_time})
            unique_entity_ids.add(entity_id)

        for source_id, target_id in combinations(sorted(unique_entity_ids), 2):
            key = (source_id, target_id)
            edge = edges.get(key)
            if edge is None:
                edge = {
                    "source_entity_id": source_id,
                    "target_entity_id": target_id,
                    "weight": 0,
                    "episode_ids": set(),
                }
                edges[key] = edge

            edge["weight"] += 1
            edge["episode_ids"].update(episode_ids)
            neighbors[source_id].add(target_id)
            neighbors[target_id].add(source_id)

    selected_ids = set(nodes.keys())
    if normalized_query:
        direct_matches = {
            entity_id
            for entity_id, node in nodes.items()
            if normalized_query in node["name"].lower()
            or normalized_query in node["type"].lower()
            or normalized_query in entity_id.lower()
        }
        contextual_matches = set(direct_matches)
        for entity_id in direct_matches:
            contextual_matches.update(neighbors.get(entity_id, set()))
        selected_ids &= contextual_matches

    truncated_nodes = False
    if len(selected_ids) > max_nodes:
        ordered_ids = sorted(
            selected_ids,
            key=lambda entity_id: (
                int(nodes[entity_id]["fact_count"]),
                len(nodes[entity_id]["episode_ids"]),
                str(nodes[entity_id]["last_seen_at"] or ""),
                nodes[entity_id]["entity_id"],
            ),
            reverse=True,
        )
        selected_ids = set(ordered_ids[:max_nodes])
        truncated_nodes = True

    edge_rows = [
        {
            "edge_id": f"edge:{source_id}:{target_id}",
            "type": "RELATED_IN_MEMORY",
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "weight": int(edge["weight"]),
            "episode_count": len(edge["episode_ids"]),
            "label": f"Related across {int(edge['weight'])} fact{'s' if int(edge['weight']) != 1 else ''}",
        }
        for (source_id, target_id), edge in edges.items()
        if source_id in selected_ids and target_id in selected_ids
    ]
    edge_rows_by_node: dict[str, list[dict]] = defaultdict(list)
    for row in edge_rows:
        edge_rows_by_node[row["source_entity_id"]].append(row)
        edge_rows_by_node[row["target_entity_id"]].append(row)
    kept_edge_ids: set[str] = set()
    for node_id, rows in edge_rows_by_node.items():
        _ = node_id
        rows.sort(
            key=lambda row: (row["weight"], row["episode_count"], row["edge_id"]),
            reverse=True,
        )
        for row in rows[:6]:
            kept_edge_ids.add(str(row["edge_id"]))
    edge_rows = [row for row in edge_rows if str(row["edge_id"]) in kept_edge_ids]
    edge_rows.sort(
        key=lambda row: (row["weight"], row["episode_count"], row["edge_id"]),
        reverse=True,
    )

    truncated_edges = False
    if len(edge_rows) > max_edges:
        edge_rows = edge_rows[:max_edges]
        truncated_edges = True

    node_rows = [
        {
            "entity_id": node["entity_id"],
            "type": node["type"],
            "name": node["name"],
            "fact_count": int(node["fact_count"]),
            "episode_count": len(node["episode_ids"]),
            "reference_time": node["last_seen_at"],
            "hover_text": node["hover_items"],
        }
        for entity_id, node in nodes.items()
        if entity_id in selected_ids
    ]
    node_rows.sort(
        key=lambda row: (row["fact_count"], row["episode_count"], str(row["reference_time"] or ""), row["entity_id"]),
        reverse=True,
    )

    return {
        "generated_at": now.isoformat(),
        "mode": "concepts",
        "empty_reason": "none" if node_rows else ("concepts_unavailable" if code_like_nodes_seen else "no_graph_data"),
        "available_modes": ["concepts", "code"],
        "node_primary_label": "Facts",
        "node_secondary_label": "Episodes",
        "edge_support_label": "Facts",
        "entity_count": len(node_rows),
        "relationship_count": len(edge_rows),
        "truncated": truncated_nodes or truncated_edges,
        "nodes": node_rows,
        "edges": edge_rows,
    }


async def _collect_timeline_episodes_for_ids(
    session: AsyncSession,
    *,
    project_id: str,
    episode_ids: set[str],
    max_rows: int,
) -> list[dict]:
    from viberecall_mcp.repositories.episodes import list_timeline_episodes

    if not episode_ids:
        return []

    rows: list[dict] = []
    scanned = 0
    offset = 0
    page_size = 200
    max_scan_rows = 5_000
    seen_ids: set[str] = set()

    while len(rows) < max_rows and scanned < max_scan_rows:
        page = await list_timeline_episodes(
            session,
            project_id=project_id,
            from_time=None,
            to_time=None,
            limit=page_size,
            offset=offset,
        )
        if not page:
            break
        scanned += len(page)
        for item in page:
            episode_id = str(item.get("episode_id") or "")
            if episode_id in episode_ids and episode_id not in seen_ids:
                seen_ids.add(episode_id)
                rows.append(item)
                if len(rows) >= max_rows:
                    break
        if len(seen_ids) >= len(episode_ids):
            break
        if len(page) < page_size:
            break
        offset += page_size

    rows.sort(
        key=lambda item: (
            str(item.get("reference_time") or item.get("ingested_at") or ""),
            str(item.get("episode_id") or ""),
        ),
        reverse=True,
    )
    return rows[:max_rows]


def _generate_pat() -> str:
    return f"vr_mcp_sk_{secrets.token_urlsafe(32)}"


def _verify_stripe_signature(payload: bytes, signature_header: str | None) -> None:
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Stripe-Signature")

    parts = {}
    for entry in signature_header.split(","):
        key, _, value = entry.partition("=")
        if key and value:
            parts.setdefault(key, []).append(value)

    timestamp_raw = (parts.get("t") or [None])[0]
    signatures = parts.get("v1") or []
    if timestamp_raw is None or not signatures:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed Stripe-Signature")

    try:
        timestamp = int(timestamp_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Stripe-Signature timestamp",
        ) from exc

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if abs(now_ts - timestamp) > settings.stripe_webhook_tolerance_seconds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Stripe signature timestamp expired")

    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    expected = hmac.new(
        settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Stripe signature")


def _build_token_create_payload(
    *,
    project_id: str,
    plan: str,
    expires_at: datetime | None = None,
    scopes: list[str] | None = None,
) -> tuple[str, str, str, str, list[str], str, datetime | None]:
    token_id = new_id("tok")
    plaintext = _generate_pat()
    prefix = plaintext[:16]
    token_hash = hash_token(plaintext)
    token_scopes = _normalize_requested_scopes(scopes, plan=plan)
    return token_id, plaintext, prefix, token_hash, token_scopes, project_id, expires_at


async def _ensure_project_access(
    session: AsyncSession,
    *,
    project_id: str,
    user: AuthenticatedControlPlaneUser,
    claim_unowned_on_write: bool,
) -> dict:
    project = await get_project_for_owner(
        session,
        project_id=project_id,
        owner_id=user.user_id,
        include_unowned=_include_unowned_projects(),
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if claim_unowned_on_write and project.get("owner_id") is None and _include_unowned_projects():
        claimed = await claim_project_owner_if_unowned(
            session,
            project_id=project_id,
            owner_id=user.user_id,
        )
        if claimed is not None:
            project = claimed

    return project


async def _audit_control_plane(
    session: AsyncSession,
    *,
    action: str,
    status_text: str,
    user: AuthenticatedControlPlaneUser,
    project_id: str | None = None,
    commit: bool = True,
) -> None:
    await insert_audit_log(
        session,
        request_id=new_id("req"),
        action=action,
        status=status_text,
        project_id=project_id,
        token_id=None,
        commit=commit,
    )


async def _replay_idempotent_control_plane_response(
    *,
    namespace: str,
    project_id: str,
    idempotency_key: str | None,
    payload_hash: str,
) -> dict | None:
    if not idempotency_key:
        return None
    store = get_idempotency_store()
    record = await store.get(f"{namespace}:{project_id}:{idempotency_key}")
    if record is None:
        return None
    if record.payload_hash != payload_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key payload mismatch")
    return record.response


async def _persist_idempotent_control_plane_response(
    *,
    namespace: str,
    project_id: str,
    idempotency_key: str | None,
    payload_hash: str,
    response: dict,
) -> None:
    if not idempotency_key:
        return
    store = get_idempotency_store()
    await store.put(
        f"{namespace}:{project_id}:{idempotency_key}",
        payload_hash,
        response,
        ttl_seconds=24 * 60 * 60,
    )


async def _claim_idempotent_control_plane_slot(
    *,
    namespace: str,
    project_id: str,
    idempotency_key: str | None,
) -> None:
    if not idempotency_key:
        return
    store = get_idempotency_store()
    claim = getattr(store, "claim", None)
    if claim is None:
        return
    locked = await claim(f"{namespace}:{project_id}:{idempotency_key}", ttl_seconds=30)
    if not locked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another request with this Idempotency-Key is in progress")


async def _release_idempotent_control_plane_slot(
    *,
    namespace: str,
    project_id: str,
    idempotency_key: str | None,
) -> None:
    if not idempotency_key:
        return
    store = get_idempotency_store()
    release = getattr(store, "release", None)
    if release is None:
        return
    await release(f"{namespace}:{project_id}:{idempotency_key}")
