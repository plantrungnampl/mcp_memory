from __future__ import annotations

import json

from viberecall_mcp.idempotency_redis import RedisIdempotencyStore
from viberecall_mcp.rate_limit_redis import RedisRateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.deleted: list[str] = []
        self.locks: set[str] = set()

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.locks:
            return False
        if nx:
            self.locks.add(key)
        self.store[key] = value
        return True

    async def delete(self, key: str):
        self.deleted.append(key)
        self.locks.discard(key)
        self.store.pop(key, None)

    async def eval(self, script: str, numkeys: int, *args):
        key = args[0]
        if key.endswith("token:tok"):
            return [1, 1735689660000]
        return [0, 1735689720000]


async def test_redis_idempotency_store_roundtrip_and_lock() -> None:
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis)

    claimed = await store.claim("proj:tool:key", ttl_seconds=30)
    assert claimed is True
    claimed_again = await store.claim("proj:tool:key", ttl_seconds=30)
    assert claimed_again is False

    await store.put("proj:tool:key", "hash-1", {"ok": True}, ttl_seconds=60)
    record = await store.get("proj:tool:key")
    assert record is not None
    assert record.payload_hash == "hash-1"
    assert record.response == {"ok": True}


async def test_redis_rate_limiter_maps_eval_result() -> None:
    limiter = RedisRateLimiter(FakeRedis())

    allowed = await limiter.check("token:tok", capacity=10, window_seconds=60)
    blocked = await limiter.check("project:proj", capacity=10, window_seconds=60)

    assert allowed.allowed is True
    assert blocked.allowed is False
    assert allowed.reset_at.endswith("+00:00")
    assert blocked.reset_at.endswith("+00:00")
