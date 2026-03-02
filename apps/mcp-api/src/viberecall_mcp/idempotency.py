from __future__ import annotations

from datetime import datetime, timedelta, timezone

from viberecall_mcp.runtime_types import StoredIdempotencyResult



class LocalIdempotencyStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredIdempotencyResult] = {}
        self._locks: set[str] = set()

    def _prune(self) -> None:
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, item in self._items.items() if datetime.fromisoformat(item.expires_at) <= now
        ]
        for key in expired_keys:
            self._items.pop(key, None)

    async def get(self, key: str) -> StoredIdempotencyResult | None:
        self._prune()
        return self._items.get(key)

    async def put(self, key: str, payload_hash: str, response: dict, ttl_seconds: int) -> None:
        self._items[key] = StoredIdempotencyResult(
            payload_hash=payload_hash,
            response=response,
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(),
        )
        self._locks.discard(key)

    async def claim(self, key: str, *, ttl_seconds: int) -> bool:
        self._prune()
        if key in self._locks:
            return False
        self._locks.add(key)
        return True

    async def release(self, key: str) -> None:
        self._locks.discard(key)

    async def reset(self) -> None:
        self._items.clear()
        self._locks.clear()
