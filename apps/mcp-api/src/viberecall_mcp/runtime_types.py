from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class StoredIdempotencyResult:
    payload_hash: str
    response: dict
    expires_at: str


@dataclass(slots=True)
class RateLimitResult:
    allowed: bool
    reset_at: str


@dataclass(slots=True)
class EnqueueUpdateFactResult:
    job_id: str
    immediate_result: dict | None = None


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> StoredIdempotencyResult | None: ...

    async def put(self, key: str, payload_hash: str, response: dict, ttl_seconds: int) -> None: ...

    async def reset(self) -> None: ...


class RateLimiter(Protocol):
    async def check(self, key: str, *, capacity: int, window_seconds: int) -> RateLimitResult: ...

    async def reset(self) -> None: ...


class TaskQueue(Protocol):
    async def enqueue_ingest(
        self,
        *,
        episode_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str: ...

    async def enqueue_update_fact(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
        fact_id: str,
        new_fact_id: str,
        new_text: str,
        effective_time: str,
        reason: str | None,
    ) -> EnqueueUpdateFactResult: ...

    async def enqueue_export(
        self,
        *,
        export_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str: ...

    async def enqueue_retention(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str: ...

    async def enqueue_purge_project(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str: ...

    async def enqueue_migrate_inline_to_object(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
        force: bool,
    ) -> str: ...
