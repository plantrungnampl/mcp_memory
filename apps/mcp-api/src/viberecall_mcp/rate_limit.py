from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from viberecall_mcp.runtime_types import RateLimitResult


class LocalRateLimiter:
    def __init__(self) -> None:
        self._counters: dict[str, list[datetime]] = defaultdict(list)

    async def check(self, key: str, *, capacity: int, window_seconds: int) -> RateLimitResult:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)
        current = [stamp for stamp in self._counters[key] if stamp > window_start]
        if len(current) >= capacity:
            reset_at = min(current) + timedelta(seconds=window_seconds)
            self._counters[key] = current
            return RateLimitResult(allowed=False, reset_at=reset_at.isoformat())

        current.append(now)
        self._counters[key] = current
        return RateLimitResult(
            allowed=True,
            reset_at=(now + timedelta(seconds=window_seconds)).isoformat(),
        )

    async def reset(self) -> None:
        self._counters.clear()
