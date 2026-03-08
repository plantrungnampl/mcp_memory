from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text

from viberecall_mcp import code_index
from viberecall_mcp.db import SessionLocal
from viberecall_mcp.ids import new_id
from viberecall_mcp import runtime


def test_runtime_selectors_choose_expected_backends(monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "memory_backend", "local")
    monkeypatch.setattr(runtime.settings, "kv_backend", "local")
    monkeypatch.setattr(runtime.settings, "queue_backend", "eager")

    assert runtime.get_memory_core() is runtime._local_memory_core
    assert runtime.get_idempotency_store() is runtime._local_idempotency_store
    assert runtime.get_rate_limiter() is runtime._local_rate_limiter
    assert runtime.get_task_queue() is runtime._eager_task_queue

    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    assert runtime.get_memory_core() is runtime._graphiti_memory_core

    monkeypatch.setattr(runtime.settings, "memory_backend", "falkordb")
    monkeypatch.setattr(runtime.settings, "kv_backend", "redis")
    monkeypatch.setattr(runtime.settings, "queue_backend", "celery")

    assert runtime.get_memory_core() is runtime._falkordb_memory_core
    assert runtime.get_idempotency_store() is runtime._redis_idempotency_store
    assert runtime.get_rate_limiter() is runtime._redis_rate_limiter
    assert runtime.get_task_queue() is runtime._celery_task_queue


async def test_eager_task_queue_returns_job_ids(monkeypatch) -> None:
    async def fake_run_ingest_job(**kwargs):
        return {"status": "complete"}

    async def fake_run_update_fact_job(**kwargs):
        return {"old_fact": {"id": "fact_old"}, "new_fact": {"id": "fact_new"}}

    async def fake_run_export_job(**kwargs):
        return {"status": "complete"}

    async def fake_run_retention_job(**kwargs):
        return {"status": "complete"}

    async def fake_run_purge_project_job(**kwargs):
        return {"status": "complete"}

    async def fake_run_migrate_inline_to_object_job(**kwargs):
        return {"status": "complete"}

    async def fake_run_index_job(**kwargs):
        return {"status": "complete"}

    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_ingest_job", fake_run_ingest_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_update_fact_job", fake_run_update_fact_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_export_job", fake_run_export_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_retention_job", fake_run_retention_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_purge_project_job", fake_run_purge_project_job)
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.run_migrate_inline_to_object_job",
        fake_run_migrate_inline_to_object_job,
    )
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_index_job", fake_run_index_job)

    ingest_job_id = await runtime.EagerTaskQueue().enqueue_ingest(
        episode_id="ep_123",
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    update_result = await runtime.EagerTaskQueue().enqueue_update_fact(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
        fact_id="fact_old",
        new_fact_id="fact_new",
        new_text="new text",
        effective_time="2026-02-28T00:00:00Z",
        reason=None,
    )
    export_job_id = await runtime.EagerTaskQueue().enqueue_export(
        export_id="exp_123",
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    retention_job_id = await runtime.EagerTaskQueue().enqueue_retention(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    purge_job_id = await runtime.EagerTaskQueue().enqueue_purge_project(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    migrate_job_id = await runtime.EagerTaskQueue().enqueue_migrate_inline_to_object(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
        force=True,
    )
    index_job_id = await runtime.EagerTaskQueue().enqueue_index_repo(
        index_id="idx_123",
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )

    assert ingest_job_id.startswith("job_ingest_")
    assert update_result.job_id.startswith("job_update_")
    assert update_result.immediate_result is not None
    assert export_job_id.startswith("job_export_")
    assert retention_job_id.startswith("job_retention_")
    assert purge_job_id.startswith("job_purge_")
    assert migrate_job_id.startswith("job_migrate_")
    assert index_job_id.startswith("job_index_")


async def test_celery_task_queue_uses_delay_result_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.ingest_episode_task.delay",
        lambda *args: SimpleNamespace(id="celery-ingest-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.update_fact_task.delay",
        lambda *args: SimpleNamespace(id="celery-update-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.export_project_task.delay",
        lambda *args: SimpleNamespace(id="celery-export-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.retention_project_task.delay",
        lambda *args: SimpleNamespace(id="celery-retention-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.purge_project_task.delay",
        lambda *args: SimpleNamespace(id="celery-purge-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.migrate_inline_to_object_task.delay",
        lambda *args: SimpleNamespace(id="celery-migrate-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.index_repo_task.delay",
        lambda *args: SimpleNamespace(id="celery-index-1"),
    )

    ingest_job_id = await runtime.CeleryTaskQueue().enqueue_ingest(
        episode_id="ep_123",
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    update_result = await runtime.CeleryTaskQueue().enqueue_update_fact(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
        fact_id="fact_old",
        new_fact_id="fact_new",
        new_text="new text",
        effective_time="2026-02-28T00:00:00Z",
        reason=None,
    )
    export_job_id = await runtime.CeleryTaskQueue().enqueue_export(
        export_id="exp_123",
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    retention_job_id = await runtime.CeleryTaskQueue().enqueue_retention(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    purge_job_id = await runtime.CeleryTaskQueue().enqueue_purge_project(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )
    migrate_job_id = await runtime.CeleryTaskQueue().enqueue_migrate_inline_to_object(
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
        force=False,
    )
    index_job_id = await runtime.CeleryTaskQueue().enqueue_index_repo(
        index_id="idx_123",
        project_id="proj_123",
        request_id="req_123",
        token_id="tok_123",
    )

    assert ingest_job_id == "celery-ingest-1"
    assert update_result.job_id == "celery-update-1"
    assert update_result.immediate_result is None
    assert export_job_id == "celery-export-1"
    assert retention_job_id == "celery-retention-1"
    assert purge_job_id == "celery-purge-1"
    assert migrate_job_id == "celery-migrate-1"
    assert index_job_id == "celery-index-1"


async def test_graph_dependency_failure_detail_uses_cached_probe(monkeypatch) -> None:
    calls = {"count": 0}

    async def fake_verify_connectivity() -> None:
        calls["count"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(runtime.settings, "dependency_probe_cache_ok_ttl_seconds", 30.0)
    monkeypatch.setattr(runtime.settings, "dependency_probe_cache_error_ttl_seconds", 30.0)
    monkeypatch.setattr(runtime._falkordb_admin, "verify_connectivity", fake_verify_connectivity)

    await runtime.reset_runtime_state()
    detail_one = await runtime.get_graph_dependency_failure_detail()
    detail_two = await runtime.get_graph_dependency_failure_detail()

    assert calls["count"] == 1
    assert detail_one == detail_two
    assert detail_one is not None
    assert "boom" in detail_one


async def test_code_index_snapshot_persists_text_arrays_for_asyncpg() -> None:
    project_id = new_id("proj")
    index_id = new_id("idx")
    repo_path = Path("/Data/VibeRecall_Memory/apps/mcp-api/src/viberecall_mcp")
    file_rows = [
        {
            "path": "demo.py",
            "language": "python",
            "module": "root",
            "sha1": "demo-sha1",
            "symbols": [
                {
                    "name": "handle_index_repo",
                    "kind": "function",
                    "line_start": 1,
                    "line_end": 2,
                    "snippet": "def handle_index_repo():\n    return None",
                    "tokens": ["handle_index_repo", "return"],
                }
            ],
            "imports": ["json"],
            "snippet": "def handle_index_repo():\n    return None",
            "tokens": ["handle_index_repo", "json"],
        }
    ]
    materialized = code_index._materialize_index(
        project_id=project_id,
        repo_path=repo_path,
        indexed_at=code_index._now_iso(),
        mode="snapshot",
        source="snapshot",
        file_rows=file_rows,
    )

    async with SessionLocal() as session:
        try:
            await session.execute(
                text(
                    """
                    insert into projects (id, name, owner_id, plan, retention_days, isolation_mode)
                    values (:id, :name, :owner_id, :plan, :retention_days, :isolation_mode)
                    """
                ),
                {
                    "id": project_id,
                    "name": "Code Index Array Regression",
                    "owner_id": "codex-runtime-test",
                    "plan": "free",
                    "retention_days": 30,
                    "isolation_mode": "falkordb_graph",
                },
            )
            await code_index._insert_index_run(
                session,
                index_id=index_id,
                project_id=project_id,
                repo_path=str(repo_path),
                mode="snapshot",
                base_ref=None,
                head_ref=None,
                max_files=100,
                requested_by_token_id=None,
            )
            await code_index._store_materialized_snapshot(
                session,
                index_id=index_id,
                file_rows=file_rows,
                materialized=materialized,
            )
            await session.commit()

            entities = await code_index._entity_candidate_rows(
                session,
                index_id=index_id,
                query_lower="handle_index_repo",
                entity_types=["Symbol"],
            )
            assert any(entity["name"] == "handle_index_repo" for entity in entities)

            chunks = await code_index._chunk_candidate_rows(
                session,
                index_id=index_id,
                query_tokens={"handle_index_repo"},
                boosted_entity_ids={entity["entity_id"] for entity in entities},
            )
            assert any(chunk["entity_id"].startswith("symbol:demo.py:handle_index_repo:1") for chunk in chunks)
        finally:
            await session.execute(text("delete from projects where id = :project_id"), {"project_id": project_id})
            await session.commit()
