from __future__ import annotations

from functools import lru_cache

from redis import asyncio as redis_async

from viberecall_mcp.config import get_settings


@lru_cache
def get_redis_client() -> redis_async.Redis:
    settings = get_settings()
    return redis_async.from_url(settings.redis_url, decode_responses=True)
