from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_index_bundle(
    session: AsyncSession,
    *,
    bundle_id: str,
    project_id: str,
    object_key: str,
    filename: str,
    byte_size: int,
    sha256: str,
    uploaded_by_user_id: str | None,
    expires_at: datetime | None = None,
) -> dict:
    result = await session.execute(
        text(
            """
            insert into index_bundles (
                bundle_id, project_id, object_key, filename, byte_size, sha256,
                uploaded_by_user_id, expires_at
            ) values (
                :bundle_id, :project_id, :object_key, :filename, :byte_size, :sha256,
                :uploaded_by_user_id, :expires_at
            )
            returning bundle_id, project_id, object_key, filename, byte_size, sha256,
                      uploaded_by_user_id, created_at, expires_at
            """
        ),
        {
            "bundle_id": bundle_id,
            "project_id": project_id,
            "object_key": object_key,
            "filename": filename,
            "byte_size": byte_size,
            "sha256": sha256,
            "uploaded_by_user_id": uploaded_by_user_id,
            "expires_at": expires_at,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else {}


async def get_index_bundle(
    session: AsyncSession,
    *,
    project_id: str,
    bundle_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select bundle_id, project_id, object_key, filename, byte_size, sha256,
                   uploaded_by_user_id, created_at, expires_at
            from index_bundles
            where project_id = :project_id
              and bundle_id = :bundle_id
              and (expires_at is null or expires_at > :now)
            """
        ),
        {
            "project_id": project_id,
            "bundle_id": bundle_id,
            "now": datetime.now(timezone.utc),
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None
