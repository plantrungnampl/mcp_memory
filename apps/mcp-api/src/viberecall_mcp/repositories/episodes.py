from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _parse_metadata(metadata) -> dict:
    if isinstance(metadata, str):
        return json.loads(metadata)
    return metadata or {}


def _as_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _coerce_timestamptz(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def create_episode(
    session: AsyncSession,
    *,
    episode_id: str,
    project_id: str,
    content: str | None,
    reference_time: str | datetime | None,
    metadata_json: str,
    content_ref: str | None = None,
    summary: str | None = None,
    job_id: str | None = None,
    enrichment_status: str = "pending",
    commit: bool = True,
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
            "reference_time": _coerce_timestamptz(reference_time),
            "content": content,
            "content_ref": content_ref,
            "summary": summary,
            "metadata_json": metadata_json,
            "job_id": job_id,
            "enrichment_status": enrichment_status,
        },
    )
    if commit:
        await session.commit()


async def get_episode(session: AsyncSession, episode_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select episode_id, project_id, reference_time, ingested_at, enrichment_status,
                   job_id, content_ref, summary, content, metadata_json,
                   salience_score, salience_class
            from episodes
            where episode_id = :episode_id
            """
        ),
        {"episode_id": episode_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_episode_for_project(
    session: AsyncSession,
    *,
    project_id: str,
    episode_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select episode_id, project_id, reference_time, ingested_at, content_ref,
                   summary, metadata_json, salience_score, salience_class
            from episodes
            where project_id = :project_id
              and episode_id = :episode_id
            """
        ),
        {
            "project_id": project_id,
            "episode_id": episode_id,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def update_episode_salience(
    session: AsyncSession,
    *,
    project_id: str,
    episode_id: str,
    salience_score: float,
    salience_class: str,
    metadata_json: dict,
) -> dict | None:
    result = await session.execute(
        text(
            """
            update episodes
            set salience_score = :salience_score,
                salience_class = :salience_class,
                metadata_json = cast(:metadata_json as jsonb)
            where project_id = :project_id
              and episode_id = :episode_id
            returning
              episode_id,
              project_id,
              reference_time,
              ingested_at,
              content_ref,
              summary,
              content,
              metadata_json,
              salience_score,
              salience_class
            """
        ),
        {
            "project_id": project_id,
            "episode_id": episode_id,
            "salience_score": salience_score,
            "salience_class": salience_class,
            "metadata_json": json.dumps(metadata_json),
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def delete_episode_for_project(
    session: AsyncSession,
    *,
    project_id: str,
    episode_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            delete from episodes
            where project_id = :project_id
              and episode_id = :episode_id
            returning episode_id, project_id, content_ref
            """
        ),
        {
            "project_id": project_id,
            "episode_id": episode_id,
        },
    )
    row = result.mappings().first()
    await session.commit()
    return dict(row) if row else None


async def mark_episode_enrichment_status(
    session: AsyncSession,
    *,
    episode_id: str,
    status: str,
    summary: str | None = None,
    commit: bool = True,
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
    if commit:
        await session.commit()


async def set_episode_job_id(
    session: AsyncSession,
    *,
    episode_id: str,
    job_id: str,
    commit: bool = True,
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
    if commit:
        await session.commit()


async def mark_episode_enrichment_failed(
    session: AsyncSession,
    *,
    episode_id: str,
    error: str,
    commit: bool = True,
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
    if commit:
        await session.commit()


async def list_timeline_episodes(
    session: AsyncSession,
    *,
    project_id: str,
    from_time: str | datetime | None,
    to_time: str | datetime | None,
    limit: int,
    offset: int,
) -> list[dict]:
    parsed_from_time = _coerce_timestamptz(from_time)
    parsed_to_time = _coerce_timestamptz(to_time)
    filters = ["project_id = :project_id"]
    params: dict[str, object] = {
        "project_id": project_id,
        "limit": limit,
        "offset": offset,
    }
    if parsed_from_time is not None:
        filters.append("coalesce(reference_time, ingested_at) >= cast(:from_time as timestamptz)")
        params["from_time"] = parsed_from_time
    if parsed_to_time is not None:
        filters.append("coalesce(reference_time, ingested_at) <= cast(:to_time as timestamptz)")
        params["to_time"] = parsed_to_time

    query = f"""
            select episode_id, reference_time, ingested_at, summary, metadata_json,
                   salience_score, salience_class
            from episodes
            where {" and ".join(filters)}
            order by coalesce(reference_time, ingested_at) desc, episode_id desc
            limit :limit offset :offset
            """
    result = await session.execute(
        text(query),
        params,
    )
    rows = []
    for row in result.mappings().all():
        rows.append(
            {
                "episode_id": row["episode_id"],
                "reference_time": _as_iso(row["reference_time"]),
                "ingested_at": _as_iso(row["ingested_at"]),
                "summary": row["summary"],
                "metadata": _parse_metadata(row["metadata_json"]),
                "salience_score": row.get("salience_score", 0.5),
                "salience_class": row.get("salience_class", "WARM"),
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
    offset: int,
) -> list[dict]:
    window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    result = await session.execute(
        text(
            """
            select episode_id, reference_time, ingested_at, content, metadata_json, summary, enrichment_status,
                   salience_score, salience_class
            from episodes
            where project_id = :project_id
              and ingested_at >= :window_start
              and enrichment_status != 'complete'
              and (coalesce(content, '') ilike :query or coalesce(summary, '') ilike :query)
            order by ingested_at desc, episode_id desc
            offset :offset
            limit :limit
            """
        ),
        {
            "project_id": project_id,
            "window_start": window_start,
            "query": f"%{query}%",
            "offset": offset,
            "limit": limit,
        },
    )
    rows = []
    for row in result.mappings().all():
        rows.append(
            {
                "episode_id": row["episode_id"],
                "reference_time": _as_iso(row["reference_time"]),
                "ingested_at": _as_iso(row["ingested_at"]),
                "summary": row["summary"] or ((row["content"] or "")[:160]),
                "metadata": _parse_metadata(row["metadata_json"]),
                "salience_score": row.get("salience_score", 0.5),
                "salience_class": row.get("salience_class", "WARM"),
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
            select episode_id, reference_time, ingested_at, summary, metadata_json,
                   salience_score, salience_class
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
                "reference_time": _as_iso(row["reference_time"]),
                "ingested_at": _as_iso(row["ingested_at"]),
                "summary": row["summary"],
                "metadata": _parse_metadata(row["metadata_json"]),
                "salience_score": row.get("salience_score", 0.5),
                "salience_class": row.get("salience_class", "WARM"),
            }
        )
    return rows
