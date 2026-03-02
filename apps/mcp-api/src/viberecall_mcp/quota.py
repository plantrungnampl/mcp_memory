from __future__ import annotations

from datetime import datetime, timezone

from viberecall_mcp.config import get_settings


settings = get_settings()


def monthly_quota_for_plan(plan: str) -> int | None:
    if plan == "free":
        return settings.quota_free_monthly_vibe_tokens
    if plan == "pro":
        return settings.quota_pro_monthly_vibe_tokens
    if plan == "team":
        return settings.quota_team_monthly_vibe_tokens
    return None


def next_month_reset_at(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.month == 12:
        reset = current.replace(year=current.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        reset = current.replace(month=current.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return reset.isoformat()

