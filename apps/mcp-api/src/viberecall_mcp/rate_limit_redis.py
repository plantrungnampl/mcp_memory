from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from viberecall_mcp.runtime_types import RateLimitResult


RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local seq_key = KEYS[2]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)
if count >= capacity then
  local earliest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local earliest_score = now
  if earliest[2] ~= nil then
    earliest_score = tonumber(earliest[2])
  end
  return {0, earliest_score + ttl}
end

local seq = redis.call('INCR', seq_key)
redis.call('EXPIRE', seq_key, ttl)
redis.call('ZADD', key, now, tostring(now) .. ':' .. tostring(seq))
redis.call('EXPIRE', key, ttl)
return {1, now + ttl}
"""


class RedisRateLimiter:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def check(self, key: str, *, capacity: int, window_seconds: int) -> RateLimitResult:
        now = datetime.now(timezone.utc)
        now_ms = int(now.timestamp() * 1000)
        window_start_ms = int((now - timedelta(seconds=window_seconds)).timestamp() * 1000)
        allowed, reset_at_ms = await self._redis.eval(
            RATE_LIMIT_SCRIPT,
            2,
            self._redis_key(key),
            self._seq_key(key),
            now_ms,
            window_start_ms,
            capacity,
            window_seconds,
        )
        reset_at = datetime.fromtimestamp(int(reset_at_ms) / 1000, tz=timezone.utc).isoformat()
        return RateLimitResult(allowed=bool(int(allowed)), reset_at=reset_at)

    async def reset(self) -> None:
        return None

    @staticmethod
    def _redis_key(key: str) -> str:
        return f"rl:{key}"

    @staticmethod
    def _seq_key(key: str) -> str:
        return f"rlseq:{key}"
