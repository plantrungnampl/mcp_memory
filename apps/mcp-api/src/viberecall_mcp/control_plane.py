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

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.auth import hash_payload, hash_token
from viberecall_mcp.code_index import (
    build_code_topology_graph,
    get_code_topology_entity_detail,
    validate_workspace_bundle_archive,
)
from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane_auth import (
    AuthenticatedControlPlaneUser,
    authenticate_control_plane_request,
)
from viberecall_mcp.db import get_db_session
from viberecall_mcp.exports import build_signed_download, local_export_path, verify_download_signature
from viberecall_mcp.ids import new_id
from viberecall_mcp.pagination import decode_cursor, encode_cursor, make_seed
from viberecall_mcp.quota import monthly_quota_for_plan, next_month_reset_at
from viberecall_mcp.repositories.audit_logs import (
    count_api_logs_rows,
    get_api_logs_summary,
    insert_audit_log,
    list_api_logs_rows,
    list_api_logs_tools,
    list_audit_logs_for_project,
)
from viberecall_mcp.repositories.episodes import list_timeline_episodes
from viberecall_mcp.repositories.billing import (
    get_billing_contact,
    get_default_payment_method,
    list_recent_invoices,
)
from viberecall_mcp.repositories.exports import (
    create_export,
    get_export,
    list_exports,
    refresh_export_url,
    set_export_job_id,
)
from viberecall_mcp.repositories.projects import (
    claim_project_owner_if_unowned,
    create_project,
    get_project_for_owner,
    list_project_overview_for_owner,
    list_projects_for_owner,
    update_project_plan,
)
from viberecall_mcp.repositories.index_bundles import create_index_bundle
from viberecall_mcp.repositories.tokens import (
    create_token,
    get_latest_active_token_preview,
    get_token_for_project,
    list_tokens_for_project,
    set_token_revoked_at,
)
from viberecall_mcp.repositories.usage_events import (
    get_usage_analytics,
    get_billing_usage_snapshot,
    get_usage_rollup,
    get_usage_series,
)
from viberecall_mcp.repositories.webhooks import (
    begin_webhook_event,
    get_webhook_event,
    mark_webhook_event_status,
)
from viberecall_mcp.object_storage import bundle_storage_key, put_bytes
from viberecall_mcp.runtime import (
    build_graph_dependency_detail,
    get_memory_core,
    get_idempotency_store,
    get_task_queue,
    probe_runtime_dependencies,
)


settings = get_settings()
router = APIRouter(prefix="/api/control-plane", tags=["control-plane"])


class CreateProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    plan: Literal["free", "pro", "team"] = "free"


class CreateTokenInput(BaseModel):
    expires_at: datetime | None = None
    scopes: list[str] | None = None


class CreateExportInput(BaseModel):
    format: Literal["json_v1"] = "json_v1"


class MigrateInlineToObjectInput(BaseModel):
    force: bool = False


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
    revoked_at = token.get("revoked_at")
    now = datetime.now(timezone.utc)
    if revoked_at is None:
        return "active"
    if revoked_at > now:
        return "grace"
    return "revoked"


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


async def _collect_project_facts(*, project_id: str, max_rows: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    page_size = 200
    memory_core = get_memory_core()

    while len(rows) < max_rows:
        remaining = max_rows - len(rows)
        page = await memory_core.get_facts(
            project_id,
            filters={},
            limit=min(page_size, remaining),
            offset=offset,
        )
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        if len(page) < min(page_size, remaining):
            break

    return rows


async def _collect_project_facts_for_graph(*, project_id: str, max_rows: int) -> list[dict]:
    try:
        return await _collect_project_facts(project_id=project_id, max_rows=max_rows)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        dependency_state = await probe_runtime_dependencies()
        if dependency_state["status"] != "ok":
            fallback_detail = str(exc).strip() or None
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=build_graph_dependency_detail(
                    dependency_state,
                    fallback_detail=fallback_detail,
                ),
            ) from exc
        raise


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


@router.get("/projects")
async def list_projects_route(
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    projects = await list_projects_for_owner(
        session,
        owner_id=user.user_id,
        include_unowned=_include_unowned_projects(),
    )
    await _audit_control_plane(
        session,
        action="control-plane/projects.list",
        status_text="ok",
        user=user,
    )
    return {"projects": [_serialize_project(project) for project in projects]}


@router.get("/projects/overview")
async def projects_overview_route(
    window_days: int = 30,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if window_days < 1 or window_days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="window_days must be between 1 and 365",
        )
    rows = await list_project_overview_for_owner(
        session,
        owner_id=user.user_id,
        include_unowned=_include_unowned_projects(),
        window_days=window_days,
    )
    await _audit_control_plane(
        session,
        action="control-plane/projects.overview.read",
        status_text="ok",
        user=user,
    )
    return {
        "window_days": window_days,
        "projects": [_serialize_project_overview(row) for row in rows],
    }


@router.post("/projects")
async def create_project_route(
    payload: CreateProjectInput,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    project_name = payload.name.strip()
    if not project_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project name is required")

    project = await create_project(
        session,
        project_id=new_id("proj"),
        owner_id=user.user_id,
        name=project_name,
        plan=payload.plan,
    )

    token_id, plaintext, prefix, token_hash, scopes, project_id, expires_at = _build_token_create_payload(
        project_id=project["id"],
        plan=project["plan"],
        expires_at=None,
        scopes=None,
    )
    token = await create_token(
        session,
        token_id=token_id,
        prefix=prefix,
        token_hash=token_hash,
        project_id=project_id,
        scopes=scopes,
        plan=project["plan"],
        expires_at=expires_at,
    )
    await session.commit()
    await _audit_control_plane(
        session,
        action="control-plane/project.create",
        status_text="ok",
        user=user,
        project_id=project["id"],
    )

    return {
        "project": _serialize_project(project),
        "connection": _build_connection(project["id"], token["prefix"]),
        "token": _serialize_token(token, plaintext=plaintext),
    }


@router.get("/projects/{project_id}/token-preview")
async def token_preview_route(
    project_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    token = await get_latest_active_token_preview(session, project_id)
    await _audit_control_plane(
        session,
        action="control-plane/token.preview",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"token": _serialize_token(token) if token else None}


@router.get("/projects/{project_id}/connection")
async def connection_route(
    project_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    token = await get_latest_active_token_preview(session, project_id)
    await _audit_control_plane(
        session,
        action="control-plane/connection.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return _build_connection(project_id, token["prefix"] if token else None)


@router.post("/projects/{project_id}/index-bundles")
async def upload_index_bundle_route(
    project_id: str,
    file: UploadFile = File(...),
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Index bundle must be a .zip archive",
        )
    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Index bundle is empty",
        )
    if len(payload) > settings.index_bundle_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Index bundle exceeds size limit",
        )
    try:
        validate_workspace_bundle_archive(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    bundle_id = new_id("bundle")
    object_key = bundle_storage_key(project_id, bundle_id)
    await put_bytes(object_key=object_key, content=payload, content_type="application/zip")
    bundle = await create_index_bundle(
        session,
        bundle_id=bundle_id,
        project_id=project_id,
        object_key=object_key,
        filename=filename,
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        uploaded_by_user_id=user.user_id,
    )
    await session.commit()
    await _audit_control_plane(
        session,
        action="control-plane/index-bundle.create",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"bundle": _serialize_index_bundle(bundle)}


@router.get("/projects/{project_id}/tokens")
async def list_tokens_route(
    project_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    tokens = await list_tokens_for_project(session, project_id)
    await _audit_control_plane(
        session,
        action="control-plane/tokens.list",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"tokens": [_serialize_token(token) for token in tokens]}


@router.get("/projects/{project_id}/usage")
async def project_usage_route(
    project_id: str,
    period: Literal["daily", "monthly"] = "daily",
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    usage = await get_usage_rollup(
        session,
        project_id=project_id,
        period=period,
    )
    await _audit_control_plane(
        session,
        action="control-plane/usage.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"usage": usage}


@router.get("/projects/{project_id}/usage/series")
async def project_usage_series_route(
    project_id: str,
    window_days: int = 30,
    bucket: Literal["day"] = "day",
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    try:
        series = await get_usage_series(
            session,
            project_id=project_id,
            window_days=window_days,
            bucket=bucket,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await _audit_control_plane(
        session,
        action="control-plane/usage.series.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {
        "bucket": bucket,
        "window_days": window_days,
        "series": series,
    }


@router.get("/projects/{project_id}/usage/analytics")
async def project_usage_analytics_route(
    project_id: str,
    range: Literal["7d", "30d", "90d", "all"] = "7d",
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    analytics = await get_usage_analytics(
        session,
        project_id=project_id,
        range_key=range,
    )
    await _audit_control_plane(
        session,
        action="control-plane/usage.analytics.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return analytics


@router.get("/projects/{project_id}/graph")
async def project_graph_route(
    project_id: str,
    q: str | None = None,
    entity_types: str | None = None,
    last_days: int | None = None,
    mode: Literal["concepts", "code"] = "concepts",
    max_nodes: int = 1500,
    max_edges: int = 4000,
    max_facts: int = 5000,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    if max_nodes < 1 or max_nodes > 5000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_nodes must be between 1 and 5000",
        )
    if max_edges < 1 or max_edges > 20000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_edges must be between 1 and 20000",
        )
    if max_facts < 1 or max_facts > 20000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_facts must be between 1 and 20000",
        )
    if last_days is not None and (last_days < 1 or last_days > 3650):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="last_days must be between 1 and 3650",
        )

    await _ensure_graph_dependencies_ready()
    parsed_types = {item.strip() for item in (entity_types or "").split(",") if item.strip()}
    if mode == "code":
        payload = await build_code_topology_graph(
            session=session,
            project_id=project_id,
            query=q,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
    else:
        facts = await _collect_project_facts_for_graph(project_id=project_id, max_rows=max_facts)
        payload = _build_concept_graph_payload(
            facts=facts,
            query_text=q,
            entity_types=parsed_types,
            last_days=last_days,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
    await _audit_control_plane(
        session,
        action="control-plane/graph.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"graph": payload}


@router.get("/projects/{project_id}/graph/entities/{entity_id}")
async def project_graph_entity_detail_route(
    project_id: str,
    entity_id: str,
    mode: Literal["concepts", "code"] = "concepts",
    fact_limit: int = 120,
    episode_limit: int = 120,
    max_facts_scan: int = 5000,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    if fact_limit < 1 or fact_limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="fact_limit must be between 1 and 500",
        )
    if episode_limit < 1 or episode_limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="episode_limit must be between 1 and 500",
        )
    if max_facts_scan < 1 or max_facts_scan > 20000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_facts_scan must be between 1 and 20000",
        )

    await _ensure_graph_dependencies_ready()
    if mode == "code":
        try:
            payload = await get_code_topology_entity_detail(
                session=session,
                project_id=project_id,
                entity_id=entity_id,
            )
        except ValueError as exc:
            detail = str(exc).strip() or "Entity not found"
            status_code = status.HTTP_404_NOT_FOUND if detail == "Entity not found" else status.HTTP_422_UNPROCESSABLE_ENTITY
            raise HTTPException(status_code=status_code, detail=detail) from exc
        await _audit_control_plane(
            session,
            action="control-plane/graph.entity.read",
            status_text="ok",
            user=user,
            project_id=project_id,
        )
        return payload

    facts = await _collect_project_facts_for_graph(project_id=project_id, max_rows=max_facts_scan)
    matched_rows: list[dict] = []
    entity_profile: dict | None = None
    related_episode_ids: set[str] = set()

    for fact in facts:
        entities = fact.get("entities") or []
        target = next((item for item in entities if str(item.get("id") or "") == entity_id), None)
        if target is None:
            continue

        if entity_profile is None:
            entity_profile = {
                "entity_id": entity_id,
                "type": str(target.get("type") or "Unknown"),
                "name": str(target.get("name") or entity_id),
            }

        provenance = fact.get("provenance") or {}
        episode_ids = [str(value) for value in (provenance.get("episode_ids") or []) if value]
        related_episode_ids.update(episode_ids)
        matched_rows.append(
            {
                "fact_id": str(fact.get("id") or ""),
                "text": str(fact.get("text") or ""),
                "valid_at": fact.get("valid_at"),
                "invalid_at": fact.get("invalid_at"),
                "ingested_at": fact.get("ingested_at"),
                "provenance": {
                    "episode_ids": episode_ids,
                    "reference_time": provenance.get("reference_time"),
                    "ingested_at": provenance.get("ingested_at"),
                },
                "_event_time": _fact_event_time(fact),
            }
        )

    if entity_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    matched_rows.sort(
        key=lambda row: (
            row["_event_time"].isoformat() if row["_event_time"] is not None else "",
            row["fact_id"],
        ),
        reverse=True,
    )
    matched_rows = matched_rows[:fact_limit]
    facts_payload = [
        {
            "fact_id": row["fact_id"],
            "text": row["text"],
            "valid_at": row["valid_at"],
            "invalid_at": row["invalid_at"],
            "ingested_at": row["ingested_at"],
            "provenance": row["provenance"],
        }
        for row in matched_rows
    ]

    provenance_rows = await _collect_timeline_episodes_for_ids(
        session,
        project_id=project_id,
        episode_ids=related_episode_ids,
        max_rows=episode_limit,
    )

    await _audit_control_plane(
        session,
        action="control-plane/graph.entity.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {
        "mode": "concepts",
        "entity": {
            **entity_profile,
            "fact_count": len(matched_rows),
            "episode_count": len(related_episode_ids),
        },
        "facts": facts_payload,
        "provenance": provenance_rows,
        "related_entities": [],
        "citations": [],
        "symbols": [],
    }


@router.get("/projects/{project_id}/timeline")
async def project_timeline_route(
    project_id: str,
    from_time: str | None = None,
    to_time: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 200",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be greater than or equal to 0",
        )

    rows = await list_timeline_episodes(
        session,
        project_id=project_id,
        from_time=from_time,
        to_time=to_time,
        limit=limit + 1,
        offset=offset,
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    await _audit_control_plane(
        session,
        action="control-plane/timeline.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {
        "timeline": {
            "rows": page_rows,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": (offset + limit) if has_more else None,
        }
    }


@router.get("/projects/{project_id}/billing/overview")
async def project_billing_overview_route(
    project_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    project = await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    snapshot = await get_billing_usage_snapshot(
        session,
        project_id=project_id,
    )
    now = datetime.now(timezone.utc)
    quota = monthly_quota_for_plan(str(project["plan"]))
    current_month_vibe_tokens = int(snapshot["current_month_vibe_tokens"])
    remaining_vibe_tokens = None if quota is None else max(0, quota - current_month_vibe_tokens)
    utilization_pct = None if quota is None else round((current_month_vibe_tokens / max(quota, 1)) * 100, 2)
    projected_month_vibe_tokens = _projected_monthly_usage(
        current_month_vibe_tokens=current_month_vibe_tokens,
        now=now,
    )
    invoices = await list_recent_invoices(
        session,
        project_id=project_id,
        limit=20,
    )
    payment_method = await get_default_payment_method(
        session,
        project_id=project_id,
    )
    billing_contact = await get_billing_contact(
        session,
        project_id=project_id,
    )
    await _audit_control_plane(
        session,
        action="control-plane/billing.overview.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {
        "project_id": project_id,
        "plan": project["plan"],
        "monthly_quota_vibe_tokens": quota,
        "current_month_vibe_tokens": current_month_vibe_tokens,
        "current_month_events": int(snapshot["current_month_events"]),
        "remaining_vibe_tokens": remaining_vibe_tokens,
        "utilization_pct": utilization_pct,
        "reset_at": next_month_reset_at(now),
        "last_7d_vibe_tokens": int(snapshot["last_7d_vibe_tokens"]),
        "projected_month_vibe_tokens": projected_month_vibe_tokens,
        "plan_monthly_price_cents": _plan_monthly_price_cents(str(project["plan"])),
        "renews_at": next_month_reset_at(now),
        "invoices": [
            {
                "invoice_id": row["invoice_id"],
                "invoice_date": row["invoice_date"],
                "description": row["description"],
                "amount_cents": int(row["amount_cents"]),
                "currency": row["currency"],
                "status": row["status"],
                "pdf_url": row.get("pdf_url"),
            }
            for row in invoices
        ],
        "payment_method": (
            {
                "payment_method_id": payment_method["payment_method_id"],
                "brand": payment_method["brand"],
                "last4": payment_method["last4"],
                "exp_month": int(payment_method["exp_month"]),
                "exp_year": int(payment_method["exp_year"]),
                "is_default": bool(payment_method["is_default"]),
            }
            if payment_method
            else None
        ),
        "billing_contact": {
            "email": billing_contact.get("email") if billing_contact else None,
            "tax_id": billing_contact.get("tax_id") if billing_contact else None,
        },
    }


@router.get("/projects/{project_id}/api-logs")
async def project_api_logs_route(
    project_id: str,
    limit: int = 50,
    cursor: int | None = None,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 200",
        )
    if cursor is not None and cursor < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cursor must be greater than 0",
        )
    rows = await list_audit_logs_for_project(
        session,
        project_id=project_id,
        cursor=cursor,
        limit=limit + 1,
        action_name="tools/call",
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = int(page_rows[-1]["id"]) if has_more and page_rows else None
    await _audit_control_plane(
        session,
        action="control-plane/api-logs.list",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {
        "logs": [_serialize_api_log(row) for row in page_rows],
        "next_cursor": next_cursor,
    }


@router.get("/projects/{project_id}/api-logs/analytics")
async def project_api_logs_analytics_route(
    project_id: str,
    range: ApiLogsRange = "30d",
    status_filter: ApiLogsStatusFilter = "all",
    tool: str | None = None,
    q: str | None = None,
    limit: int = 5,
    cursor: str | None = None,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 200",
        )

    now = datetime.now(timezone.utc)
    start_at, end_at = _resolve_api_logs_window(range, now=now)
    tool_filter = tool.strip() if tool and tool.strip() else None
    search_filter = q.strip() if q and q.strip() else None
    seed = make_seed(
        {
            "project_id": project_id,
            "range": range,
            "status_filter": status_filter,
            "tool": tool_filter,
            "q": search_filter,
            "limit": limit,
        }
    )
    try:
        offset = decode_cursor(cursor, seed)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid cursor: {exc}",
        ) from exc

    summary = await get_api_logs_summary(
        session,
        project_id=project_id,
        status_filter="all",
        action_name="tools/call",
        tool_name=tool_filter,
        search_query=search_filter,
        start_at=start_at,
        end_at=end_at,
    )

    previous_summary: dict | None = None
    if start_at is not None and end_at is not None:
        window = end_at - start_at
        previous_summary = await get_api_logs_summary(
            session,
            project_id=project_id,
            status_filter="all",
            action_name="tools/call",
            tool_name=tool_filter,
            search_query=search_filter,
            start_at=start_at - window,
            end_at=start_at,
        )

    total_rows = await count_api_logs_rows(
        session,
        project_id=project_id,
        status_filter=status_filter,
        action_name="tools/call",
        tool_name=tool_filter,
        search_query=search_filter,
        start_at=start_at,
        end_at=end_at,
    )
    rows = await list_api_logs_rows(
        session,
        project_id=project_id,
        status_filter=status_filter,
        action_name="tools/call",
        tool_name=tool_filter,
        search_query=search_filter,
        start_at=start_at,
        end_at=end_at,
        offset=offset,
        limit=limit,
    )
    tool_options = await list_api_logs_tools(
        session,
        project_id=project_id,
        action_name="tools/call",
        start_at=start_at,
        end_at=end_at,
    )

    showing_from = offset + 1 if total_rows > 0 and rows else 0
    showing_to = offset + len(rows) if rows else 0
    next_cursor = encode_cursor(offset + limit, seed) if showing_to < total_rows else None
    prev_cursor = encode_cursor(max(0, offset - limit), seed) if offset > 0 else None

    total_requests_current = float(summary.get("total_requests", 0) or 0)
    total_requests_previous = float(previous_summary.get("total_requests", 0) or 0) if previous_summary else 0
    success_rate_current = float(summary.get("success_rate_pct", 0) or 0)
    success_rate_previous = float(previous_summary.get("success_rate_pct", 0) or 0) if previous_summary else 0
    error_count_current = float(summary.get("error_count", 0) or 0)
    error_count_previous = float(previous_summary.get("error_count", 0) or 0) if previous_summary else 0
    p95_latency_current_raw = summary.get("p95_latency_ms")
    p95_latency_previous_raw = previous_summary.get("p95_latency_ms") if previous_summary else None
    p95_latency_current = round(float(p95_latency_current_raw), 1) if p95_latency_current_raw is not None else None
    p95_latency_previous = round(float(p95_latency_previous_raw), 1) if p95_latency_previous_raw is not None else None

    await _audit_control_plane(
        session,
        action="control-plane/api-logs.analytics.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )

    return {
        "range": range,
        "filters": {
            "status_filter": status_filter,
            "tool": tool_filter,
            "q": search_filter,
        },
        "summary": {
            "total_requests": {
                "value": int(total_requests_current),
                "change_pct": _format_change_pct(total_requests_current, total_requests_previous),
            },
            "success_rate_pct": {
                "value": round(success_rate_current, 1),
                "change_pct": _format_change_pct(success_rate_current, success_rate_previous),
            },
            "error_count": {
                "value": int(error_count_current),
                "change_pct": _format_change_pct(error_count_current, error_count_previous),
            },
            "p95_latency_ms": {
                "value": p95_latency_current,
                "change_pct": (
                    _format_change_pct(p95_latency_current, p95_latency_previous)
                    if p95_latency_current is not None and p95_latency_previous is not None
                    else None
                ),
            },
        },
        "table": {
            "rows": [_serialize_api_log_analytics_row(row) for row in rows],
            "tool_options": tool_options,
            "pagination": {
                "total_rows": total_rows,
                "showing_from": showing_from,
                "showing_to": showing_to,
                "next_cursor": next_cursor,
                "prev_cursor": prev_cursor,
            },
        },
    }


@router.post("/projects/{project_id}/exports")
async def create_export_route(
    project_id: str,
    payload: CreateExportInput,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    payload_hash = hash_payload(
        json.dumps({"project_id": project_id, "format": payload.format}, sort_keys=True)
    )
    replay = await _replay_idempotent_control_plane_response(
        namespace="cp_export_create",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    await _ensure_export_dependencies_ready()

    export_id = new_id("exp")
    try:
        export_row = await create_export(
            session,
            export_id=export_id,
            project_id=project_id,
            requested_by=user.user_id,
            export_format=payload.format,
        )
        job_id = await get_task_queue().enqueue_export(
            export_id=export_id,
            project_id=project_id,
            request_id=new_id("req"),
            token_id=None,
        )
        await set_export_job_id(
            session,
            export_id=export_id,
            job_id=job_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    export_row = await get_export(session, project_id=project_id, export_id=export_id) or export_row
    response = {"export": _serialize_export(export_row)}
    await _persist_idempotent_control_plane_response(
        namespace="cp_export_create",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        response=response,
    )
    await _audit_control_plane(
        session,
        action="control-plane/export.create",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return response


@router.get("/projects/{project_id}/exports")
async def list_exports_route(
    project_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    rows = await list_exports(session, project_id=project_id, limit=50)
    await _audit_control_plane(
        session,
        action="control-plane/exports.list",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"exports": [_serialize_export(row) for row in rows]}


@router.get("/projects/{project_id}/exports/{export_id}")
async def get_export_route(
    project_id: str,
    export_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=False,
    )
    row = await get_export(session, project_id=project_id, export_id=export_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    if row["status"] == "complete" and row.get("object_key"):
        expires_at = row.get("expires_at")
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                expires_at = None
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            object_url, new_expires_at = build_signed_download(
                project_id=project_id,
                export_id=export_id,
            )
            await refresh_export_url(
                session,
                export_id=export_id,
                object_url=object_url,
                expires_at=new_expires_at,
            )
            row = await get_export(session, project_id=project_id, export_id=export_id) or row

    await _audit_control_plane(
        session,
        action="control-plane/export.read",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"export": _serialize_export(row)}


@router.get("/projects/{project_id}/exports/{export_id}/download")
async def download_export_route(
    project_id: str,
    export_id: str,
    expires: int,
    sig: str,
    session: AsyncSession = Depends(get_db_session),
):
    if not verify_download_signature(
        project_id=project_id,
        export_id=export_id,
        expires=expires,
        signature=sig,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired export signature")

    row = await get_export(session, project_id=project_id, export_id=export_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    if row["status"] != "complete" or not row.get("object_key"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export is not ready")

    path = local_export_path(str(row["object_key"]))
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export object not found")

    return FileResponse(path, media_type="application/json", filename=f"{export_id}.json")


@router.post("/projects/{project_id}/retention/run")
async def run_retention_route(
    project_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    project = await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    job_id = await get_task_queue().enqueue_retention(
        project_id=project_id,
        request_id=new_id("req"),
        token_id=None,
    )
    await _audit_control_plane(
        session,
        action="control-plane/retention.run",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {
        "job": {
            "job_id": job_id,
            "kind": "retention",
            "status": "queued",
            "retention_days": project.get("retention_days"),
        }
    }


@router.post("/projects/{project_id}/purge")
async def purge_project_route(
    project_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    payload_hash = hash_payload(
        json.dumps({"project_id": project_id, "action": "purge_project"}, sort_keys=True)
    )
    replay = await _replay_idempotent_control_plane_response(
        namespace="cp_project_purge",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    job_id = await get_task_queue().enqueue_purge_project(
        project_id=project_id,
        request_id=new_id("req"),
        token_id=None,
    )
    response = {
        "job": {
            "job_id": job_id,
            "kind": "purge_project",
            "status": "queued",
        }
    }
    await _persist_idempotent_control_plane_response(
        namespace="cp_project_purge",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        response=response,
    )
    await _audit_control_plane(
        session,
        action="control-plane/project.purge",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return response


@router.post("/projects/{project_id}/migrate-inline-to-object")
async def migrate_inline_to_object_route(
    project_id: str,
    payload: MigrateInlineToObjectInput | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    force = bool(payload.force) if payload is not None else False
    payload_hash = hash_payload(
        json.dumps(
            {"project_id": project_id, "action": "migrate_inline_to_object", "force": force},
            sort_keys=True,
        )
    )
    replay = await _replay_idempotent_control_plane_response(
        namespace="cp_migrate_inline_to_object",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    job_id = await get_task_queue().enqueue_migrate_inline_to_object(
        project_id=project_id,
        request_id=new_id("req"),
        token_id=None,
        force=force,
    )
    response = {
        "job": {
            "job_id": job_id,
            "kind": "migrate_inline_to_object",
            "status": "queued",
            "force": force,
        }
    }
    await _persist_idempotent_control_plane_response(
        namespace="cp_migrate_inline_to_object",
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        response=response,
    )
    await _audit_control_plane(
        session,
        action="control-plane/migrate-inline-to-object.run",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return response


@router.post("/projects/{project_id}/tokens")
async def create_token_route(
    project_id: str,
    payload: CreateTokenInput,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    project = await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    token_id, plaintext, prefix, token_hash, scopes, _, expires_at = _build_token_create_payload(
        project_id=project_id,
        plan=project["plan"],
        expires_at=payload.expires_at,
        scopes=payload.scopes,
    )
    token = await create_token(
        session,
        token_id=token_id,
        prefix=prefix,
        token_hash=token_hash,
        project_id=project_id,
        scopes=scopes,
        plan=project["plan"],
        expires_at=expires_at,
    )
    await session.commit()
    await _audit_control_plane(
        session,
        action="control-plane/token.create",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"token": _serialize_token(token, plaintext=plaintext)}


@router.post("/projects/{project_id}/tokens/{token_id}/rotate")
async def rotate_token_route(
    project_id: str,
    token_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    project = await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    old_token = await get_token_for_project(
        session,
        project_id=project_id,
        token_id=token_id,
    )
    if old_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")

    now = datetime.now(timezone.utc)
    old_revoked_at = old_token.get("revoked_at")
    if old_revoked_at is not None and old_revoked_at <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot rotate a revoked token",
        )

    old_token = await set_token_revoked_at(
        session,
        project_id=project_id,
        token_id=token_id,
        revoked_at=now + timedelta(minutes=15),
    )
    token_new_id, plaintext, prefix, token_hash, scopes, _, expires_at = _build_token_create_payload(
        project_id=project_id,
        plan=project["plan"],
        expires_at=None,
        scopes=list(old_token.get("scopes") or []) or None,
    )
    new_token = await create_token(
        session,
        token_id=token_new_id,
        prefix=prefix,
        token_hash=token_hash,
        project_id=project_id,
        scopes=scopes,
        plan=project["plan"],
        expires_at=expires_at,
    )
    await session.commit()
    await _audit_control_plane(
        session,
        action="control-plane/token.rotate",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {
        "old_token": _serialize_token(old_token) if old_token else None,
        "new_token": _serialize_token(new_token, plaintext=plaintext),
    }


@router.post("/projects/{project_id}/tokens/{token_id}/revoke")
async def revoke_token_route(
    project_id: str,
    token_id: str,
    user: AuthenticatedControlPlaneUser = Depends(authenticate_control_plane_request),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _ensure_project_access(
        session,
        project_id=project_id,
        user=user,
        claim_unowned_on_write=True,
    )
    token = await set_token_revoked_at(
        session,
        project_id=project_id,
        token_id=token_id,
        revoked_at=datetime.now(timezone.utc),
    )
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")

    await session.commit()
    await _audit_control_plane(
        session,
        action="control-plane/token.revoke",
        status_text="ok",
        user=user,
        project_id=project_id,
    )
    return {"token": _serialize_token(token)}


@router.post("/stripe/webhook")
async def stripe_webhook_route(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = await request.body()
    _verify_stripe_signature(payload, stripe_signature)
    try:
        event = json.loads(payload.decode("utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    event_id = str(event.get("id") or "").strip()
    if not event_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing Stripe event id")

    event_payload_hash = hashlib.sha256(payload).hexdigest()
    event_type = str(event.get("type") or "unknown")
    data_object = event.get("data", {}).get("object", {})
    metadata = data_object.get("metadata", {}) if isinstance(data_object, dict) else {}
    project_id = metadata.get("project_id") or event.get("project_id")
    plan = metadata.get("plan") or data_object.get("plan") or event.get("plan")

    created = await begin_webhook_event(
        session,
        provider="stripe",
        event_id=event_id,
        event_type=event_type,
        payload_hash=event_payload_hash,
        project_id=str(project_id) if project_id else None,
    )
    if not created:
        existing = await get_webhook_event(session, provider="stripe", event_id=event_id)
        existing_status = str(existing.get("status")) if existing else "unknown"
        existing_payload_hash = str(existing.get("payload_hash") or "") if existing else ""
        if existing_payload_hash and existing_payload_hash != event_payload_hash:
            await insert_audit_log(
                session,
                request_id=new_id("req"),
                action=f"stripe/{event_type}",
                status="duplicate:payload_hash_mismatch",
                project_id=str(project_id) if project_id else None,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate Stripe event id with different payload",
            )
        if existing_status == "failed":
            await mark_webhook_event_status(
                session,
                provider="stripe",
                event_id=event_id,
                status="processing",
                error=None,
            )
            await session.commit()
        else:
            processed = existing_status == "processed"
            await insert_audit_log(
                session,
                request_id=new_id("req"),
                action=f"stripe/{event_type}",
                status=f"duplicate:{existing_status}",
                project_id=str(project_id) if project_id else None,
            )
            return {"received": True, "processed": processed, "duplicate": True}

    await session.commit()

    processed = False
    status_text = "ignored"
    try:
        if event_type in {"checkout.session.completed", "customer.subscription.updated"} and project_id and plan in {
            "free",
            "pro",
            "team",
        }:
            updated = await update_project_plan(
                session,
                project_id=str(project_id),
                plan=str(plan),
            )
            processed = updated is not None

        status_text = "processed" if processed else "ignored"
        await mark_webhook_event_status(
            session,
            provider="stripe",
            event_id=event_id,
            status=status_text,
            error=None,
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await mark_webhook_event_status(
            session,
            provider="stripe",
            event_id=event_id,
            status="failed",
            error=str(exc)[:1000],
        )
        await session.commit()
        await insert_audit_log(
            session,
            request_id=new_id("req"),
            action=f"stripe/{event_type}",
            status="failed",
            project_id=str(project_id) if project_id else None,
        )
        raise

    await insert_audit_log(
        session,
        request_id=new_id("req"),
        action=f"stripe/{event_type}",
        status=status_text,
        project_id=str(project_id) if project_id else None,
    )
    return {"received": True, "processed": processed, "duplicate": False}
