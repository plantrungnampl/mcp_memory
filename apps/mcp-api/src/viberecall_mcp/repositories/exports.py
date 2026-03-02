from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_export(
    session: AsyncSession,
    *,
    export_id: str,
    project_id: str,
    requested_by: str | None,
    export_format: str = "json_v1",
) -> dict:
    result = await session.execute(
        text(
            """
            insert into exports (
                export_id, project_id, status, format, requested_by
            ) values (
                :export_id, :project_id, 'pending', :format, :requested_by
            )
            returning export_id, project_id, status, format, object_key, object_url,
                      expires_at, error, requested_by, requested_at, completed_at, job_id
            """
        ),
        {
            "export_id": export_id,
            "project_id": project_id,
            "format": export_format,
            "requested_by": requested_by,
        },
    )
    row = result.mappings().first()
    await session.commit()
    return dict(row) if row else {}


async def get_export(
    session: AsyncSession,
    *,
    project_id: str,
    export_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select export_id, project_id, status, format, object_key, object_url,
                   expires_at, error, requested_by, requested_at, completed_at, job_id
            from exports
            where project_id = :project_id
              and export_id = :export_id
            """
        ),
        {
            "project_id": project_id,
            "export_id": export_id,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_exports(
    session: AsyncSession,
    *,
    project_id: str,
    limit: int = 20,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select export_id, project_id, status, format, object_key, object_url,
                   expires_at, error, requested_by, requested_at, completed_at, job_id
            from exports
            where project_id = :project_id
            order by requested_at desc, export_id desc
            limit :limit
            """
        ),
        {
            "project_id": project_id,
            "limit": limit,
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def set_export_job_id(
    session: AsyncSession,
    *,
    export_id: str,
    job_id: str,
) -> None:
    await session.execute(
        text(
            """
            update exports
            set job_id = :job_id
            where export_id = :export_id
            """
        ),
        {
            "export_id": export_id,
            "job_id": job_id,
        },
    )
    await session.commit()


async def mark_export_processing(
    session: AsyncSession,
    *,
    export_id: str,
) -> None:
    await session.execute(
        text(
            """
            update exports
            set status = 'processing',
                error = null
            where export_id = :export_id
            """
        ),
        {"export_id": export_id},
    )
    await session.commit()


async def mark_export_complete(
    session: AsyncSession,
    *,
    export_id: str,
    object_key: str,
    object_url: str,
    expires_at: datetime,
) -> None:
    await session.execute(
        text(
            """
            update exports
            set status = 'complete',
                object_key = :object_key,
                object_url = :object_url,
                expires_at = :expires_at,
                completed_at = now(),
                error = null
            where export_id = :export_id
            """
        ),
        {
            "export_id": export_id,
            "object_key": object_key,
            "object_url": object_url,
            "expires_at": expires_at,
        },
    )
    await session.commit()


async def mark_export_failed(
    session: AsyncSession,
    *,
    export_id: str,
    error: str,
) -> None:
    await session.execute(
        text(
            """
            update exports
            set status = 'failed',
                error = :error
            where export_id = :export_id
            """
        ),
        {
            "export_id": export_id,
            "error": error[:1000],
        },
    )
    await session.commit()


async def refresh_export_url(
    session: AsyncSession,
    *,
    export_id: str,
    object_url: str,
    expires_at: datetime,
) -> None:
    await session.execute(
        text(
            """
            update exports
            set object_url = :object_url,
                expires_at = :expires_at
            where export_id = :export_id
            """
        ),
        {
            "export_id": export_id,
            "object_url": object_url,
            "expires_at": expires_at,
        },
    )
    await session.commit()
