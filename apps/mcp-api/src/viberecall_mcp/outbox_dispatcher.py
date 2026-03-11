from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.code_index import attach_index_job_id
from viberecall_mcp.config import get_settings
from viberecall_mcp.repositories.episodes import set_episode_job_id
from viberecall_mcp.repositories.operations import (
    complete_operation,
    fail_operation,
    list_dispatchable_outbox_events,
    mark_outbox_dispatched,
    mark_outbox_failed,
    mark_operation_running,
    set_operation_job_id,
)
from viberecall_mcp.runtime import get_task_queue


settings = get_settings()


def _payload(row: dict) -> dict:
    payload = row.get("payload_json")
    if isinstance(payload, str):
        return json.loads(payload)
    return payload or {}


async def dispatch_outbox_events(
    session: AsyncSession,
    *,
    operation_id: str | None = None,
    limit: int = 10,
) -> list[str]:
    rows = await list_dispatchable_outbox_events(
        session,
        operation_id=operation_id,
        limit=limit,
    )
    dispatched: list[str] = []
    for row in rows:
        payload = _payload(row)
        current_operation_id = str(row["operation_id"])
        try:
            if row["event_type"] == "save.ingest":
                job_id = await get_task_queue().enqueue_ingest(
                    episode_id=str(payload["episode_id"]),
                    project_id=str(row["project_id"]),
                    request_id=str(payload["request_id"]),
                    token_id=payload.get("token_id"),
                    operation_id=current_operation_id,
                )
                await set_episode_job_id(
                    session,
                    episode_id=str(payload["episode_id"]),
                    job_id=job_id,
                    commit=False,
                )
                await set_operation_job_id(session, operation_id=current_operation_id, job_id=job_id)
            elif row["event_type"] == "update_fact.apply":
                enqueue_result = await get_task_queue().enqueue_update_fact(
                    project_id=str(row["project_id"]),
                    request_id=str(payload["request_id"]),
                    token_id=payload.get("token_id"),
                    fact_id=str(payload["fact_id"]),
                    new_fact_id=str(payload["new_fact_id"]),
                    new_text=str(payload["new_text"]),
                    effective_time=str(payload["effective_time"]),
                    reason=payload.get("reason"),
                    operation_id=current_operation_id,
                )
                await set_operation_job_id(
                    session,
                    operation_id=current_operation_id,
                    job_id=enqueue_result.job_id,
                )
            elif row["event_type"] == "index_repo.run":
                job_id = await get_task_queue().enqueue_index_repo(
                    index_id=str(payload["index_id"]),
                    project_id=str(row["project_id"]),
                    request_id=str(payload["request_id"]),
                    token_id=payload.get("token_id"),
                    operation_id=current_operation_id,
                )
                await attach_index_job_id(
                    session=session,
                    index_id=str(payload["index_id"]),
                    job_id=job_id,
                    commit=False,
                )
                await set_operation_job_id(session, operation_id=current_operation_id, job_id=job_id)
            elif row["event_type"] == "entity_resolution.search_reproject":
                await mark_operation_running(session, operation_id=current_operation_id)
            elif row["event_type"] == "entity_resolution.graph_reproject":
                await mark_operation_running(session, operation_id=current_operation_id)
                await complete_operation(
                    session,
                    operation_id=current_operation_id,
                    result_payload=payload.get("result_payload") or {
                        "resolution_event_id": payload.get("resolution_event_id"),
                        "event_kind": payload.get("event_kind"),
                    },
                )
            else:
                raise RuntimeError(f"Unknown outbox event type: {row['event_type']}")

            await mark_outbox_dispatched(session, event_id=str(row["event_id"]))
            await session.commit()
            dispatched.append(str(row["event_id"]))
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            await mark_outbox_failed(session, event_id=str(row["event_id"]), error=str(exc))
            if int(row.get("attempts") or 0) + 1 >= settings.operation_dispatch_retry_limit:
                await fail_operation(
                    session,
                    operation_id=current_operation_id,
                    error_payload={"code": "DISPATCH_FAILED", "message": str(exc)},
                )
            await session.commit()
    return dispatched
