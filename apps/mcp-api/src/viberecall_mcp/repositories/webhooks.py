from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def begin_webhook_event(
    session: AsyncSession,
    *,
    provider: str,
    event_id: str,
    event_type: str,
    payload_hash: str,
    project_id: str | None,
) -> bool:
    result = await session.execute(
        text(
            """
            insert into webhooks (
                provider, event_id, project_id, event_type, payload_hash, status
            ) values (
                :provider, :event_id, :project_id, :event_type, :payload_hash, 'processing'
            )
            on conflict (provider, event_id) do nothing
            returning id
            """
        ),
        {
            "provider": provider,
            "event_id": event_id,
            "project_id": project_id,
            "event_type": event_type,
            "payload_hash": payload_hash,
        },
    )
    row = result.first()
    return row is not None


async def get_webhook_event(
    session: AsyncSession,
    *,
    provider: str,
    event_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select provider, event_id, project_id, event_type, payload_hash, status, error, received_at, processed_at
            from webhooks
            where provider = :provider and event_id = :event_id
            limit 1
            """
        ),
        {
            "provider": provider,
            "event_id": event_id,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def mark_webhook_event_status(
    session: AsyncSession,
    *,
    provider: str,
    event_id: str,
    status: str,
    error: str | None = None,
) -> None:
    await session.execute(
        text(
            """
            update webhooks
            set status = :status,
                error = :error,
                processed_at = case
                  when :status = 'processing' then null
                  when :status in ('processed', 'ignored', 'failed') then now()
                  else processed_at
                end
            where provider = :provider and event_id = :event_id
            """
        ),
        {
            "provider": provider,
            "event_id": event_id,
            "status": status,
            "error": error,
        },
    )
