from __future__ import annotations

import calendar
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.auth import hash_payload, hash_token
from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane_auth import (
    AuthenticatedControlPlaneUser,
    authenticate_control_plane_request,
)
from viberecall_mcp.db import get_db_session
from viberecall_mcp.exports import build_signed_download, local_export_path, verify_download_signature
from viberecall_mcp.ids import new_id
from viberecall_mcp.quota import monthly_quota_for_plan, next_month_reset_at
from viberecall_mcp.repositories.audit_logs import insert_audit_log, list_audit_logs_for_project
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
from viberecall_mcp.repositories.tokens import (
    create_token,
    get_latest_active_token_preview,
    get_token_for_project,
    list_tokens_for_project,
    set_token_revoked_at,
)
from viberecall_mcp.repositories.usage_events import (
    get_billing_usage_snapshot,
    get_usage_rollup,
    get_usage_series,
)
from viberecall_mcp.repositories.webhooks import (
    begin_webhook_event,
    get_webhook_event,
    mark_webhook_event_status,
)
from viberecall_mcp.runtime import get_idempotency_store, get_task_queue


settings = get_settings()
router = APIRouter(prefix="/api/control-plane", tags=["control-plane"])


class CreateProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    plan: Literal["free", "pro", "team"] = "free"


class CreateTokenInput(BaseModel):
    expires_at: datetime | None = None


class CreateExportInput(BaseModel):
    format: Literal["json_v1"] = "json_v1"


class MigrateInlineToObjectInput(BaseModel):
    force: bool = False


def _include_unowned_projects() -> bool:
    return settings.app_env.lower() == "development"


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
    if plan == "free":
        return ["memory:read", "memory:write", "timeline:read"]
    return ["memory:read", "memory:write", "facts:read", "facts:write", "timeline:read"]


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
    }


def _projected_monthly_usage(*, current_month_vibe_tokens: int, now: datetime) -> int:
    days_elapsed = max(now.day, 1)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    return int(round((current_month_vibe_tokens / days_elapsed) * days_in_month))


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
) -> tuple[str, str, str, str, list[str], str, datetime | None]:
    token_id = new_id("tok")
    plaintext = _generate_pat()
    prefix = plaintext[:16]
    token_hash = hash_token(plaintext)
    scopes = _default_scopes_for_plan(plan)
    return token_id, plaintext, prefix, token_hash, scopes, project_id, expires_at


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
) -> None:
    await insert_audit_log(
        session,
        request_id=new_id("req"),
        action=action,
        status=status_text,
        project_id=project_id,
        token_id=user.user_id,
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

    export_id = new_id("exp")
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
        token_id=user.user_id,
    )
    await set_export_job_id(
        session,
        export_id=export_id,
        job_id=job_id,
    )
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
        token_id=user.user_id,
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
        token_id=user.user_id,
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
        token_id=user.user_id,
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
