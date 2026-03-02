from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _parse_metadata(metadata) -> dict:
    if isinstance(metadata, str):
        return json.loads(metadata)
    return metadata or {}


async def create_episode(
    session: AsyncSession,
    *,
    episode_id: str,
    project_id: str,
    content: str | None,
    reference_time: str | None,
    metadata_json: str,
    content_ref: str | None = None,
    summary: str | None = None,
    job_id: str | None = None,
    enrichment_status: str = "pending",
) -> None:
    await session.execute(
        text(
            """
            insert into episodes (
                episode_id, project_id, reference_time, content, content_ref, summary, metadata_json, job_id, enrichment_status
            ) values (
                :episode_id, :project_id, :reference_time, :content, :content_ref, :summary, cast(:metadata_json as jsonb), :job_id, :enrichment_status
            )
            """
        ),
        {
            "episode_id": episode_id,
            "project_id": project_id,
            "reference_time": reference_time,
            "content": content,
            "content_ref": content_ref,
            "summary": summary,
            "metadata_json": metadata_json,
            "job_id": job_id,
            "enrichment_status": enrichment_status,
        },
    )
    await session.commit()


async def get_episode(session: AsyncSession, episode_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select episode_id, project_id, reference_time, ingested_at, enrichment_status,
                   job_id, content_ref, summary, content, metadata_json
            from episodes
            where episode_id = :episode_id
            """
        ),
        {"episode_id": episode_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def mark_episode_enrichment_status(
    session: AsyncSession,
    *,
    episode_id: str,
    status: str,
    summary: str | None = None,
) -> None:
    await session.execute(
        text(
            """
            update episodes
            set enrichment_status = :status,
                summary = coalesce(:summary, summary)
            where episode_id = :episode_id
            """
        ),
        {"episode_id": episode_id, "status": status, "summary": summary},
    )
    await session.commit()


async def set_episode_job_id(
    session: AsyncSession,
    *,
    episode_id: str,
    job_id: str,
) -> None:
    await session.execute(
        text(
            """
            update episodes
            set job_id = :job_id
            where episode_id = :episode_id
            """
        ),
        {"episode_id": episode_id, "job_id": job_id},
    )
    await session.commit()


async def mark_episode_enrichment_failed(
    session: AsyncSession,
    *,
    episode_id: str,
    error: str,
) -> None:
    await session.execute(
        text(
            """
            update episodes
            set enrichment_status = 'failed',
                enrichment_error = :error
            where episode_id = :episode_id
            """
        ),
        {"episode_id": episode_id, "error": error},
    )
    await session.commit()


async def list_timeline_episodes(
    session: AsyncSession,
    *,
    project_id: str,
    from_time: str | None,
    to_time: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select episode_id, reference_time, ingested_at, summary, metadata_json
            from episodes
            where project_id = :project_id
              and (:from_time is null or coalesce(reference_time, ingested_at) >= cast(:from_time as timestamptz))
              and (:to_time is null or coalesce(reference_time, ingested_at) <= cast(:to_time as timestamptz))
            order by coalesce(reference_time, ingested_at) desc, episode_id desc
            limit :limit offset :offset
            """
        ),
        {
            "project_id": project_id,
            "from_time": from_time,
            "to_time": to_time,
            "limit": limit,
            "offset": offset,
        },
    )
    rows = []
    for row in result.mappings().all():
        rows.append(
            {
                "episode_id": row["episode_id"],
                "reference_time": row["reference_time"],
                "ingested_at": row["ingested_at"],
                "summary": row["summary"],
                "metadata": _parse_metadata(row["metadata_json"]),
            }
        )
    return rows


async def list_recent_raw_episodes(
    session: AsyncSession,
    *,
    project_id: str,
    query: str,
    window_seconds: int,
    limit: int,
) -> list[dict]:
    window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    result = await session.execute(
        text(
            """
            select episode_id, reference_time, ingested_at, content, metadata_json, summary, enrichment_status
            from episodes
            where project_id = :project_id
              and ingested_at >= :window_start
              and enrichment_status != 'complete'
              and (coalesce(content, '') ilike :query or coalesce(summary, '') ilike :query)
            order by ingested_at desc, episode_id desc
            limit :limit
            """
        ),
        {
            "project_id": project_id,
            "window_start": window_start,
            "query": f"%{query}%",
            "limit": limit,
        },
    )
    rows = []
    for row in result.mappings().all():
        rows.append(
            {
                "episode_id": row["episode_id"],
                "reference_time": row["reference_time"],
                "ingested_at": row["ingested_at"],
                "summary": row["summary"] or ((row["content"] or "")[:160]),
                "metadata": _parse_metadata(row["metadata_json"]),
            }
        )
    return rows


async def list_project_episodes_for_export(
    session: AsyncSession,
    *,
    project_id: str,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select episode_id, reference_time, ingested_at, summary, metadata_json
            from episodes
            where project_id = :project_id
            order by ingested_at asc, episode_id asc
            """
        ),
        {"project_id": project_id},
    )
    rows = []
    for row in result.mappings().all():
        rows.append(
            {
                "episode_id": row["episode_id"],
                "reference_time": row["reference_time"],
                "ingested_at": row["ingested_at"],
                "summary": row["summary"],
                "metadata": _parse_metadata(row["metadata_json"]),
            }
        )
    return rows
