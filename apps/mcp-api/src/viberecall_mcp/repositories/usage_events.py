from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

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


UsageRange = Literal["7d", "30d", "90d", "all"]

_RANGE_TO_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}


@dataclass(slots=True)
class _WindowBounds:
    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime
    window_days: int


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _token_status(*, revoked_at: datetime | None, now: datetime) -> str:
    if revoked_at is None:
        return "active"
    revoked_at_utc = _to_utc(revoked_at)
    if revoked_at_utc > now:
        return "grace"
    return "revoked"


def _format_short_date(value: datetime) -> str:
    return f"{value.strftime('%b')} {value.day}"


def _format_date_range_label(*, start: datetime, end: datetime) -> str:
    end_inclusive = end - timedelta(seconds=1)
    if start.year == end_inclusive.year:
        return f"{_format_short_date(start)} – {_format_short_date(end_inclusive)}, {end_inclusive.year}"
    return (
        f"{_format_short_date(start)}, {start.year} – "
        f"{_format_short_date(end_inclusive)}, {end_inclusive.year}"
    )


def _compute_change_pct(*, current: float, previous: float) -> float:
    if previous <= 0:
        if current <= 0:
            return 0.0
        return 100.0
    return round(((current - previous) / previous) * 100, 1)


def _format_peak_hour_label(bucket: datetime | None) -> str:
    if bucket is None:
        return "—"
    start = _to_utc(bucket)
    end = start + timedelta(hours=1)
    return f"{start.strftime('%-I%p').lower()} – {end.strftime('%-I%p').lower()}"


async def _resolve_window_bounds(
    session: AsyncSession,
    *,
    project_id: str,
    range_key: UsageRange,
    now: datetime,
) -> _WindowBounds:
    if range_key in _RANGE_TO_DAYS:
        window_days = _RANGE_TO_DAYS[range_key]
        start = now - timedelta(days=window_days)
        previous_end = start
        previous_start = previous_end - timedelta(days=window_days)
        return _WindowBounds(
            start=start,
            end=now,
            previous_start=previous_start,
            previous_end=previous_end,
            window_days=window_days,
        )

    result = await session.execute(
        text(
            """
            select
              (select min(ts) from usage_events where project_id = :project_id) as first_usage_ts,
              (select min(created_at) from audit_logs where project_id = :project_id) as first_log_ts
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first() or {}
    first_candidates = [
        _to_utc(value)
        for value in [row.get("first_usage_ts"), row.get("first_log_ts")]
        if value is not None
    ]
    first_seen = min(first_candidates) if first_candidates else now - timedelta(days=30)
    duration = max(now - first_seen, timedelta(days=30))

    start = first_seen
    previous_end = start
    previous_start = previous_end - duration
    return _WindowBounds(
        start=start,
        end=now,
        previous_start=previous_start,
        previous_end=previous_end,
        window_days=max(1, int(duration.total_seconds() // 86_400)),
    )


async def _read_usage_summary(
    session: AsyncSession,
    *,
    project_id: str,
    start: datetime,
    end: datetime,
) -> dict:
    result = await session.execute(
        text(
            """
            select
              count(*) as api_calls,
              coalesce(sum(vibe_tokens), 0) as vibe_tokens
            from usage_events
            where project_id = :project_id
              and ts >= :start
              and ts < :end
            """
        ),
        {
            "project_id": project_id,
            "start": start,
            "end": end,
        },
    )
    row = result.mappings().first() or {}
    return {
        "api_calls": int(row.get("api_calls", 0) or 0),
        "vibe_tokens": int(row.get("vibe_tokens", 0) or 0),
    }


async def _read_error_rate(
    session: AsyncSession,
    *,
    project_id: str,
    start: datetime,
    end: datetime,
) -> float:
    result = await session.execute(
        text(
            """
            select
              count(*) as total_count,
              count(*) filter (
                where lower(status) not in ('ok', 'success', 'complete', 'queued')
              ) as error_count
            from audit_logs
            where project_id = :project_id
              and created_at >= :start
              and created_at < :end
            """
        ),
        {
            "project_id": project_id,
            "start": start,
            "end": end,
        },
    )
    row = result.mappings().first() or {}
    total_count = int(row.get("total_count", 0) or 0)
    error_count = int(row.get("error_count", 0) or 0)
    if total_count <= 0:
        return 0.0
    return round((error_count * 100.0) / total_count, 1)


async def get_usage_analytics(
    session: AsyncSession,
    *,
    project_id: str,
    range_key: UsageRange,
) -> dict:
    now = datetime.now(timezone.utc)
    bounds = await _resolve_window_bounds(
        session,
        project_id=project_id,
        range_key=range_key,
        now=now,
    )

    current_summary = await _read_usage_summary(
        session,
        project_id=project_id,
        start=bounds.start,
        end=bounds.end,
    )
    previous_summary = await _read_usage_summary(
        session,
        project_id=project_id,
        start=bounds.previous_start,
        end=bounds.previous_end,
    )

    current_error_rate = await _read_error_rate(
        session,
        project_id=project_id,
        start=bounds.start,
        end=bounds.end,
    )
    previous_error_rate = await _read_error_rate(
        session,
        project_id=project_id,
        start=bounds.previous_start,
        end=bounds.previous_end,
    )

    trend_result = await session.execute(
        text(
            """
            with buckets as (
              select generate_series(
                date_trunc('day', cast(:start as timestamptz)),
                date_trunc('day', cast(:end as timestamptz)),
                interval '1 day'
              ) as bucket_start
            )
            select
              buckets.bucket_start,
              coalesce(count(ue.id), 0) as api_calls,
              coalesce(sum(ue.vibe_tokens), 0) as vibe_tokens
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
            "start": bounds.start,
            "end": bounds.end,
        },
    )
    trend_rows = trend_result.mappings().all()
    trend = [
        {
            "bucket_start": row["bucket_start"],
            "day_label": _to_utc(row["bucket_start"]).strftime("%a"),
            "api_calls": int(row.get("api_calls", 0) or 0),
            "vibe_tokens": int(row.get("vibe_tokens", 0) or 0),
        }
        for row in trend_rows
    ]

    tool_result = await session.execute(
        text(
            """
            select
              tool,
              count(*) as api_calls
            from usage_events
            where project_id = :project_id
              and ts >= :start
              and ts < :end
            group by tool
            order by api_calls desc, tool asc
            limit 8
            """
        ),
        {
            "project_id": project_id,
            "start": bounds.start,
            "end": bounds.end,
        },
    )
    tool_rows = tool_result.mappings().all()
    total_api_calls = max(current_summary["api_calls"], 1)
    tool_distribution = [
        {
            "tool": str(row.get("tool") or "unknown"),
            "api_calls": int(row.get("api_calls", 0) or 0),
            "share_pct": round((int(row.get("api_calls", 0) or 0) * 100.0) / total_api_calls, 1),
        }
        for row in tool_rows
    ]

    token_result = await session.execute(
        text(
            """
            select
              t.token_id,
              t.prefix,
              t.revoked_at,
              count(ue.id) as api_calls,
              coalesce(sum(ue.vibe_tokens), 0) as vibe_tokens
            from mcp_tokens t
            left join usage_events ue
              on ue.token_id = t.token_id
             and ue.project_id = t.project_id
             and ue.ts >= :start
             and ue.ts < :end
            where t.project_id = :project_id
            group by t.token_id, t.prefix, t.revoked_at, t.created_at
            order by api_calls desc, t.created_at desc
            limit 50
            """
        ),
        {
            "project_id": project_id,
            "start": bounds.start,
            "end": bounds.end,
        },
    )
    token_rows = token_result.mappings().all()
    token_breakdown = [
        {
            "token_id": str(row["token_id"]),
            "prefix": str(row.get("prefix") or "unknown"),
            "status": _token_status(revoked_at=row.get("revoked_at"), now=now),
            "api_calls": int(row.get("api_calls", 0) or 0),
            "vibe_tokens": int(row.get("vibe_tokens", 0) or 0),
            "avg_latency_ms": None,
            "share_pct": round((int(row.get("api_calls", 0) or 0) * 100.0) / total_api_calls, 1),
        }
        for row in token_rows
    ]

    peak_hour_result = await session.execute(
        text(
            """
            select
              date_trunc('hour', ts) as hour_bucket,
              count(*) as api_calls
            from usage_events
            where project_id = :project_id
              and ts >= :start
              and ts < :end
            group by hour_bucket
            order by api_calls desc, hour_bucket desc
            limit 1
            """
        ),
        {
            "project_id": project_id,
            "start": bounds.start,
            "end": bounds.end,
        },
    )
    peak_hour_row = peak_hour_result.mappings().first()

    most_active_token = next(
        (row["prefix"] for row in token_breakdown if int(row["api_calls"]) > 0),
        "—",
    )
    busiest_day = next(
        (
            _to_utc(row["bucket_start"]).strftime("%A")
            for row in sorted(
                trend_rows,
                key=lambda item: (int(item.get("api_calls", 0) or 0), item["bucket_start"]),
                reverse=True,
            )
            if int(row.get("api_calls", 0) or 0) > 0
        ),
        "—",
    )

    return {
        "range": range_key,
        "window_days": bounds.window_days,
        "date_range_label": _format_date_range_label(start=bounds.start, end=bounds.end),
        "summary": {
            "api_calls": {
                "value": current_summary["api_calls"],
                "change_pct": _compute_change_pct(
                    current=float(current_summary["api_calls"]),
                    previous=float(previous_summary["api_calls"]),
                ),
            },
            "tokens_consumed": {
                "value": current_summary["vibe_tokens"],
                "change_pct": _compute_change_pct(
                    current=float(current_summary["vibe_tokens"]),
                    previous=float(previous_summary["vibe_tokens"]),
                ),
            },
            "avg_response_time_ms": {
                "value": None,
                "change_pct": None,
            },
            "error_rate_pct": {
                "value": current_error_rate,
                "change_pct": _compute_change_pct(
                    current=current_error_rate,
                    previous=previous_error_rate,
                ),
            },
        },
        "trend": trend,
        "tool_distribution": tool_distribution,
        "token_breakdown": token_breakdown,
        "highlights": {
            "peak_hour": _format_peak_hour_label(
                peak_hour_row.get("hour_bucket") if peak_hour_row else None,
            ),
            "most_active_token": most_active_token,
            "busiest_day": busiest_day,
        },
    }
