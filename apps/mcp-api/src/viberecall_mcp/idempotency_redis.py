from __future__ import annotations

import json
from datetime import datetime, timezone

from redis.asyncio import Redis

from viberecall_mcp.runtime_types import StoredIdempotencyResult


class RedisIdempotencyStore:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> StoredIdempotencyResult | None:
        payload = await self._redis.get(self._result_key(key))
        if payload is None:
            return None
        decoded = json.loads(payload)
        return StoredIdempotencyResult(
            payload_hash=decoded["payload_hash"],
            response=decoded["response"],
            expires_at=decoded["expires_at"],
        )

    async def put(self, key: str, payload_hash: str, response: dict, ttl_seconds: int) -> None:
        await self._redis.set(
            self._result_key(key),
            json.dumps(
                {
                    "payload_hash": payload_hash,
                    "response": response,
                    "expires_at": datetime.fromtimestamp(
                        datetime.now(timezone.utc).timestamp() + ttl_seconds,
                        tz=timezone.utc,
                    ).isoformat(),
                },
                default=str,
            ),
            ex=ttl_seconds,
        )
        await self._redis.delete(self._lock_key(key))

    async def claim(self, key: str, *, ttl_seconds: int) -> bool:
        return bool(
            await self._redis.set(
                self._lock_key(key),
                "1",
                ex=ttl_seconds,
                nx=True,
            )
        )

    async def release(self, key: str) -> None:
        await self._redis.delete(self._lock_key(key))

    async def reset(self) -> None:
        return None

    @staticmethod
    def _result_key(key: str) -> str:
        return f"idem:result:{key}"

    @staticmethod
    def _lock_key(key: str) -> str:
        return f"idem:lock:{key}"
