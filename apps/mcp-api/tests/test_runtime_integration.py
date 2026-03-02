from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from redis import asyncio as redis_async

from viberecall_mcp.idempotency_redis import RedisIdempotencyStore
from viberecall_mcp.memory_core.neo4j_adapter import Neo4jMemoryCore
from viberecall_mcp.memory_core.neo4j_admin import Neo4jDatabaseManager
from viberecall_mcp.rate_limit_redis import RedisRateLimiter


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RUNTIME_INTEGRATION") != "1",
    reason="Set RUN_RUNTIME_INTEGRATION=1 with Neo4j and Redis running to enable runtime integration tests.",
)


@pytest.mark.asyncio
async def test_runtime_integration_neo4j_and_redis_roundtrip() -> None:
    admin = Neo4jDatabaseManager()
    memory = Neo4jMemoryCore(admin)
    redis = redis_async.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    idem = RedisIdempotencyStore(redis)
    limiter = RedisRateLimiter(redis)

    project_id = f"proj_integration_{int(datetime.now(timezone.utc).timestamp())}"
    episode_id = f"ep_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    idem_key = f"{project_id}:viberecall_save:idem_1"
    rl_key = f"token:{project_id}:tok_1"

    try:
        await admin.reset_database(project_id)

        episode = {
            "episode_id": episode_id,
            "project_id": project_id,
            "reference_time": "2026-02-28T10:00:00Z",
            "ingested_at": "2026-02-28T10:00:02Z",
            "content": "Fix auth middleware bug in callback flow",
            "content_ref": episode_id,
            "summary": None,
            "metadata_json": {
                "repo": "viberecall",
                "branch": "main",
                "tags": ["auth"],
                "files": ["apps/web/src/proxy.ts"],
                "type": "bugfix",
            },
        }
        ingest = await memory.ingest_episode(project_id, episode)
        assert ingest["fact_id"] == f"fact_{episode_id}"

        search_results = await memory.search(
            project_id,
            query="auth middleware",
            filters={},
            sort="RELEVANCE",
            limit=10,
            offset=0,
        )
        assert search_results, "Expected at least one search result after ingest"
        assert search_results[0]["kind"] == "fact"

        facts_before = await memory.get_facts(
            project_id,
            filters={"tag": "auth"},
            limit=10,
            offset=0,
        )
        assert facts_before
        fact_id = facts_before[0]["id"]

        update = await memory.update_fact(
            project_id,
            fact_id=fact_id,
            new_fact_id=f"{fact_id}_v2",
            new_text="Fix race condition in auth callback middleware",
            effective_time="2026-02-28T10:10:00Z",
            reason="Root cause narrowed",
        )
        assert update["old_fact"]["id"] == fact_id
        assert update["new_fact"]["id"] == f"{fact_id}_v2"

        facts_after = await memory.get_facts(
            project_id,
            filters={},
            limit=20,
            offset=0,
        )
        fact_ids = {item["id"] for item in facts_after}
        assert fact_id in fact_ids
        assert f"{fact_id}_v2" in fact_ids

        claimed = await idem.claim(idem_key, ttl_seconds=30)
        assert claimed is True
        claimed_again = await idem.claim(idem_key, ttl_seconds=30)
        assert claimed_again is False

        await idem.put(idem_key, "hash_1", {"ok": True}, ttl_seconds=60)
        idem_record = await idem.get(idem_key)
        assert idem_record is not None
        assert idem_record.payload_hash == "hash_1"
        assert idem_record.response == {"ok": True}

        check_1 = await limiter.check(rl_key, capacity=1, window_seconds=60)
        check_2 = await limiter.check(rl_key, capacity=1, window_seconds=60)
        assert check_1.allowed is True
        assert check_2.allowed is False
    finally:
        await admin.reset_database(project_id)
        await redis.delete(f"idem:result:{idem_key}")
        await redis.delete(f"idem:lock:{idem_key}")
        await redis.delete(f"rl:{rl_key}")
        await redis.delete(f"rlseq:{rl_key}")
        await redis.close()
        await admin.close()
