from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _list_or_empty(value) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value if item]


async def get_project_retention_days(
    session: AsyncSession,
    *,
    project_id: str,
) -> int | None:
    result = await session.execute(
        text(
            """
            select retention_days
            from projects
            where id = :project_id
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return int(row["retention_days"])


async def get_current_database_size_bytes(session: AsyncSession) -> int:
    result = await session.execute(
        text(
            """
            select pg_database_size(current_database())::bigint as size_bytes
            """
        )
    )
    row = result.mappings().first() or {}
    return int(row.get("size_bytes") or 0)


async def list_inline_episodes_for_migration(
    session: AsyncSession,
    *,
    project_id: str,
    min_bytes: int,
    limit: int = 100,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select episode_id, content
            from episodes
            where project_id = :project_id
              and content is not null
              and content_ref is null
              and octet_length(content) > :min_bytes
            order by ingested_at asc, episode_id asc
            limit :limit
            """
        ),
        {
            "project_id": project_id,
            "min_bytes": min_bytes,
            "limit": limit,
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def mark_episode_content_externalized(
    session: AsyncSession,
    *,
    episode_id: str,
    content_ref: str,
    summary: str | None,
) -> None:
    await session.execute(
        text(
            """
            update episodes
            set content_ref = :content_ref,
                content = null,
                summary = coalesce(summary, :summary)
            where episode_id = :episode_id
            """
        ),
        {
            "episode_id": episode_id,
            "content_ref": content_ref,
            "summary": summary,
        },
    )


async def delete_project_episodes_before(
    session: AsyncSession,
    *,
    project_id: str,
    cutoff: datetime,
) -> dict:
    result = await session.execute(
        text(
            """
            with deleted as (
              delete from episodes
              where project_id = :project_id
                and coalesce(reference_time, ingested_at) < :cutoff
              returning content_ref
            )
            select
              count(*)::int as deleted_count,
              coalesce(array_agg(content_ref) filter (where content_ref is not null), '{}') as content_refs
            from deleted
            """
        ),
        {
            "project_id": project_id,
            "cutoff": cutoff,
        },
    )
    row = result.mappings().first() or {}
    return {
        "deleted_count": int(row.get("deleted_count") or 0),
        "content_refs": _list_or_empty(row.get("content_refs")),
    }


async def delete_project_exports_before(
    session: AsyncSession,
    *,
    project_id: str,
    cutoff: datetime,
) -> dict:
    result = await session.execute(
        text(
            """
            with deleted as (
              delete from exports
              where project_id = :project_id
                and requested_at < :cutoff
              returning object_key
            )
            select
              count(*)::int as deleted_count,
              coalesce(array_agg(object_key) filter (where object_key is not null), '{}') as object_keys
            from deleted
            """
        ),
        {
            "project_id": project_id,
            "cutoff": cutoff,
        },
    )
    row = result.mappings().first() or {}
    return {
        "deleted_count": int(row.get("deleted_count") or 0),
        "object_keys": _list_or_empty(row.get("object_keys")),
    }


async def delete_all_project_episodes(
    session: AsyncSession,
    *,
    project_id: str,
) -> dict:
    result = await session.execute(
        text(
            """
            with deleted as (
              delete from episodes
              where project_id = :project_id
              returning content_ref
            )
            select
              count(*)::int as deleted_count,
              coalesce(array_agg(content_ref) filter (where content_ref is not null), '{}') as content_refs
            from deleted
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first() or {}
    return {
        "deleted_count": int(row.get("deleted_count") or 0),
        "content_refs": _list_or_empty(row.get("content_refs")),
    }


async def delete_all_project_exports(
    session: AsyncSession,
    *,
    project_id: str,
) -> dict:
    result = await session.execute(
        text(
            """
            with deleted as (
              delete from exports
              where project_id = :project_id
              returning object_key
            )
            select
              count(*)::int as deleted_count,
              coalesce(array_agg(object_key) filter (where object_key is not null), '{}') as object_keys
            from deleted
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first() or {}
    return {
        "deleted_count": int(row.get("deleted_count") or 0),
        "object_keys": _list_or_empty(row.get("object_keys")),
    }


async def delete_all_project_usage_events(
    session: AsyncSession,
    *,
    project_id: str,
) -> int:
    result = await session.execute(
        text(
            """
            delete from usage_events
            where project_id = :project_id
            """
        ),
        {"project_id": project_id},
    )
    return int(result.rowcount or 0)


async def delete_all_project_webhooks(
    session: AsyncSession,
    *,
    project_id: str,
) -> int:
    result = await session.execute(
        text(
            """
            delete from webhooks
            where project_id = :project_id
            """
        ),
        {"project_id": project_id},
    )
    return int(result.rowcount or 0)


async def scrub_project_audit_logs(
    session: AsyncSession,
    *,
    project_id: str,
) -> int:
    result = await session.execute(
        text(
            """
            update audit_logs
            set token_id = null,
                tool_name = null,
                action = 'redacted',
                args_hash = coalesce(args_hash, md5(coalesce(request_id, '') || ':' || coalesce(action, '')))
            where project_id = :project_id
            """
        ),
        {"project_id": project_id},
    )
    return int(result.rowcount or 0)
