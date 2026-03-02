from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.metrics import tokens_burn_rate

async def create_usage_event(
    session: AsyncSession,
    *,
    project_id: str,
    token_id: str | None,
    tool: str,
    vibe_tokens: int = 0,
    provider: str | None = None,
    model: str | None = None,
    in_tokens: int = 0,
    out_tokens: int = 0,
) -> None:
    await session.execute(
        text(
            """
            insert into usage_events (
                project_id, token_id, tool, provider, model, in_tokens, out_tokens, vibe_tokens
            ) values (
                :project_id, :token_id, :tool, :provider, :model, :in_tokens, :out_tokens, :vibe_tokens
            )
            """
        ),
        {
            "project_id": project_id,
            "token_id": token_id,
            "tool": tool,
            "provider": provider,
            "model": model,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "vibe_tokens": vibe_tokens,
        },
    )
    await session.commit()
    monthly_total = await get_monthly_vibe_tokens(session, project_id=project_id)
    tokens_burn_rate.labels(project=project_id).set(monthly_total)


async def get_usage_rollup(
    session: AsyncSession,
    *,
    project_id: str,
    period: str,
) -> dict:
    if period not in {"daily", "monthly"}:
        raise ValueError("period must be one of: daily, monthly")

    if period == "daily":
        result = await session.execute(
            text(
                """
                select
                  coalesce(sum(vibe_tokens), 0) as vibe_tokens,
                  coalesce(sum(in_tokens), 0) as in_tokens,
                  coalesce(sum(out_tokens), 0) as out_tokens,
                  count(*) as event_count
                from usage_events
                where project_id = :project_id
                  and ts >= now() - interval '1 day'
                """
            ),
            {"project_id": project_id},
        )
    else:
        result = await session.execute(
            text(
                """
                select
                  coalesce(sum(vibe_tokens), 0) as vibe_tokens,
                  coalesce(sum(in_tokens), 0) as in_tokens,
                  coalesce(sum(out_tokens), 0) as out_tokens,
                  count(*) as event_count
                from usage_events
                where project_id = :project_id
                  and ts >= now() - interval '30 day'
                """
            ),
            {"project_id": project_id},
        )

    row = result.mappings().first()
    payload = dict(row) if row else {}
    return {
        "period": period,
        "vibe_tokens": int(payload.get("vibe_tokens", 0) or 0),
        "in_tokens": int(payload.get("in_tokens", 0) or 0),
        "out_tokens": int(payload.get("out_tokens", 0) or 0),
        "event_count": int(payload.get("event_count", 0) or 0),
    }


async def get_usage_series(
    session: AsyncSession,
    *,
    project_id: str,
    window_days: int,
    bucket: str,
) -> list[dict]:
    if bucket != "day":
        raise ValueError("bucket must be one of: day")
    if window_days < 1 or window_days > 365:
        raise ValueError("window_days must be between 1 and 365")

    result = await session.execute(
        text(
            """
            with buckets as (
              select generate_series(
                date_trunc('day', now()) - (:window_days - 1) * interval '1 day',
                date_trunc('day', now()),
                interval '1 day'
              ) as bucket_start
            )
            select
              buckets.bucket_start,
              coalesce(sum(ue.vibe_tokens), 0) as vibe_tokens,
              coalesce(sum(ue.in_tokens), 0) as in_tokens,
              coalesce(sum(ue.out_tokens), 0) as out_tokens,
              count(ue.id) as event_count
            from buckets
            left join usage_events ue
              on ue.project_id = :project_id
             and ue.ts >= buckets.bucket_start
             and ue.ts < buckets.bucket_start + interval '1 day'
            group by buckets.bucket_start
            order by buckets.bucket_start asc
            """
        ),
        {
            "project_id": project_id,
            "window_days": window_days,
        },
    )
    rows = result.mappings().all()
    return [
        {
            "bucket_start": row["bucket_start"],
            "vibe_tokens": int(row.get("vibe_tokens", 0) or 0),
            "in_tokens": int(row.get("in_tokens", 0) or 0),
            "out_tokens": int(row.get("out_tokens", 0) or 0),
            "event_count": int(row.get("event_count", 0) or 0),
        }
        for row in rows
    ]


async def get_monthly_vibe_tokens(
    session: AsyncSession,
    *,
    project_id: str,
) -> int:
    result = await session.execute(
        text(
            """
            select coalesce(sum(vibe_tokens), 0) as vibe_tokens
            from usage_events
            where project_id = :project_id
              and ts >= date_trunc('month', now())
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    if row is None:
        return 0
    return int(row.get("vibe_tokens", 0) or 0)


async def get_billing_usage_snapshot(
    session: AsyncSession,
    *,
    project_id: str,
) -> dict:
    result = await session.execute(
        text(
            """
            select
              coalesce(sum(vibe_tokens) filter (where ts >= date_trunc('month', now())), 0) as current_month_vibe_tokens,
              coalesce(count(*) filter (where ts >= date_trunc('month', now())), 0) as current_month_events,
              coalesce(sum(vibe_tokens) filter (where ts >= now() - interval '7 day'), 0) as last_7d_vibe_tokens
            from usage_events
            where project_id = :project_id
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    payload = dict(row) if row else {}
    return {
        "current_month_vibe_tokens": int(payload.get("current_month_vibe_tokens", 0) or 0),
        "current_month_events": int(payload.get("current_month_events", 0) or 0),
        "last_7d_vibe_tokens": int(payload.get("last_7d_vibe_tokens", 0) or 0),
    }
