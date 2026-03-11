from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _json(value: dict | None) -> str:
    return json.dumps(value or {}, default=str)


async def create_operation(
    session: AsyncSession,
    *,
    operation_id: str,
    project_id: str,
    token_id: str | None,
    request_id: str,
    kind: str,
    status: str = "PENDING",
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into operations (
                operation_id, project_id, token_id, request_id, kind, status,
                resource_type, resource_id, metadata_json
            ) values (
                :operation_id, :project_id, :token_id, :request_id, :kind, :status,
                :resource_type, :resource_id, cast(:metadata_json as jsonb)
            )
            """
        ),
        {
            "operation_id": operation_id,
            "project_id": project_id,
            "token_id": token_id,
            "request_id": request_id,
            "kind": kind,
            "status": status,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata_json": _json(metadata),
        },
    )


async def get_operation(
    session: AsyncSession,
    *,
    project_id: str,
    operation_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select operation_id, project_id, token_id, request_id, kind, status,
                   resource_type, resource_id, job_id, metadata_json, result_json,
                   error_json, created_at, updated_at, completed_at
            from operations
            where project_id = :project_id
              and operation_id = :operation_id
            """
        ),
        {"project_id": project_id, "operation_id": operation_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def set_operation_job_id(
    session: AsyncSession,
    *,
    operation_id: str,
    job_id: str,
) -> None:
    await session.execute(
        text(
            """
            update operations
            set job_id = :job_id,
                updated_at = now()
            where operation_id = :operation_id
            """
        ),
        {"operation_id": operation_id, "job_id": job_id},
    )


async def merge_operation_metadata(
    session: AsyncSession,
    *,
    operation_id: str,
    metadata_patch: dict | None,
) -> None:
    await session.execute(
        text(
            """
            update operations
            set metadata_json = coalesce(metadata_json, '{}'::jsonb) || cast(:metadata_json as jsonb),
                updated_at = now()
            where operation_id = :operation_id
            """
        ),
        {
            "operation_id": operation_id,
            "metadata_json": _json(metadata_patch),
        },
    )


async def mark_operation_running(
    session: AsyncSession,
    *,
    operation_id: str,
) -> None:
    await session.execute(
        text(
            """
            update operations
            set status = 'RUNNING',
                updated_at = now()
            where operation_id = :operation_id
              and status in ('PENDING', 'FAILED_RETRYABLE')
            """
        ),
        {"operation_id": operation_id},
    )


async def complete_operation(
    session: AsyncSession,
    *,
    operation_id: str,
    result_payload: dict | None = None,
) -> None:
    await session.execute(
        text(
            """
            update operations
            set status = 'SUCCEEDED',
                result_json = cast(:result_json as jsonb),
                error_json = null,
                updated_at = now(),
                completed_at = now()
            where operation_id = :operation_id
            """
        ),
        {
            "operation_id": operation_id,
            "result_json": _json(result_payload),
        },
    )


async def fail_operation(
    session: AsyncSession,
    *,
    operation_id: str,
    error_payload: dict,
    retryable: bool = False,
) -> None:
    next_status = "FAILED_RETRYABLE" if retryable else "FAILED_TERMINAL"
    await session.execute(
        text(
            """
            update operations
            set status = :status,
                error_json = cast(:error_json as jsonb),
                updated_at = now(),
                completed_at = now()
            where operation_id = :operation_id
            """
        ),
        {
            "operation_id": operation_id,
            "status": next_status,
            "error_json": _json(error_payload),
        },
    )


async def create_outbox_event(
    session: AsyncSession,
    *,
    event_id: str,
    operation_id: str,
    project_id: str,
    event_type: str,
    payload: dict,
) -> None:
    await session.execute(
        text(
            """
            insert into outbox_events (
                event_id, operation_id, project_id, event_type, payload_json
            ) values (
                :event_id, :operation_id, :project_id, :event_type, cast(:payload_json as jsonb)
            )
            """
        ),
        {
            "event_id": event_id,
            "operation_id": operation_id,
            "project_id": project_id,
            "event_type": event_type,
            "payload_json": _json(payload),
        },
    )


async def list_dispatchable_outbox_events(
    session: AsyncSession,
    *,
    limit: int = 10,
    operation_id: str | None = None,
) -> list[dict]:
    clauses = ["status in ('PENDING', 'FAILED')", "coalesce(available_at, now()) <= now()"]
    params: dict[str, object] = {"limit": limit}
    if operation_id is not None:
        clauses.append("operation_id = :operation_id")
        params["operation_id"] = operation_id

    result = await session.execute(
        text(
            f"""
            select event_id, operation_id, project_id, event_type, payload_json, attempts
            from outbox_events
            where {' and '.join(clauses)}
            order by created_at asc
            limit :limit
            for update skip locked
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


async def mark_outbox_dispatched(
    session: AsyncSession,
    *,
    event_id: str,
) -> None:
    await session.execute(
        text(
            """
            update outbox_events
            set status = 'DISPATCHED',
                dispatched_at = now(),
                attempts = attempts + 1,
                last_error = null
            where event_id = :event_id
            """
        ),
        {"event_id": event_id},
    )


async def mark_outbox_failed(
    session: AsyncSession,
    *,
    event_id: str,
    error: str,
) -> None:
    await session.execute(
        text(
            """
            update outbox_events
            set status = 'FAILED',
                attempts = attempts + 1,
                last_error = :error,
                available_at = now() + interval '10 seconds'
            where event_id = :event_id
            """
        ),
        {"event_id": event_id, "error": error[:4000]},
    )


async def list_recent_pending_operations(
    session: AsyncSession,
    *,
    project_id: str,
    limit: int = 50,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select operation_id, kind, status, resource_type, resource_id, created_at
            from operations
            where project_id = :project_id
              and status in ('PENDING', 'RUNNING', 'FAILED_RETRYABLE')
            order by created_at desc
            limit :limit
            """
        ),
        {"project_id": project_id, "limit": limit},
    )
    return [dict(row) for row in result.mappings().all()]
