from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
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


def test_celery_app_registers_ingest_task_for_worker_boot() -> None:
    from viberecall_mcp.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()

    assert "viberecall.ingest_episode" in celery_app.tasks


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
            await session.execute(
                text(
                    """
                    insert into code_index_runs (
                        index_id, project_id, repo_path, mode, status, phase
                    ) values (
                        :index_id, :project_id, :repo_path, :mode, 'READY', 'ready'
                    )
                    """
                ),
                {
                    "index_id": index_id,
                    "project_id": project_id,
                    "repo_path": str(repo_path),
                    "mode": "snapshot",
                },
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
            await session.execute(text("delete from code_index_runs where index_id = :index_id"), {"index_id": index_id})
            await session.execute(text("delete from projects where id = :project_id"), {"project_id": project_id})
            await session.commit()


def test_normalize_repo_source_rejects_unknown_git_credential_ref(monkeypatch) -> None:
    monkeypatch.setattr(code_index.settings, "index_remote_git_enabled", True)
    monkeypatch.setattr(code_index.settings, "index_git_credential_refs_json", '{"known":{"allowed_hosts":["github.com"],"token":"secret"}}')
    with pytest.raises(ValueError, match="Unknown git credential_ref"):
        code_index.normalize_repo_source(
            {
                "type": "git",
                "remote_url": "https://github.com/acme/repo.git",
                "ref": "main",
                "credential_ref": "missing",
            }
        )


def test_normalize_repo_source_rejects_host_mismatch_for_git_credential_ref(monkeypatch) -> None:
    monkeypatch.setattr(code_index.settings, "index_remote_git_enabled", True)
    monkeypatch.setattr(code_index.settings, "index_git_credential_refs_json", '{"known":{"allowed_hosts":["github.com"],"token":"secret"}}')
    with pytest.raises(ValueError, match="is not allowed for host"):
        code_index.normalize_repo_source(
            {
                "type": "git",
                "remote_url": "https://gitlab.com/acme/repo.git",
                "ref": "main",
                "credential_ref": "known",
            }
        )


def test_normalize_repo_source_rejects_remote_git_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(code_index.settings, "index_remote_git_enabled", False)
    with pytest.raises(ValueError, match="remote git indexing is disabled"):
        code_index.normalize_repo_source(
            {
                "type": "git",
                "remote_url": "https://github.com/acme/repo.git",
                "ref": "main",
            }
        )


async def test_probe_runtime_dependencies_checks_redis_and_celery(monkeypatch) -> None:
    class FakeRedisClient:
        def __init__(self, url: str):
            self.url = url

        async def ping(self) -> None:
            if self.url.endswith("/1"):
                raise RuntimeError("result backend down")

        async def aclose(self) -> None:
            return None

    async def fake_verify_connectivity() -> None:
        return None

    monkeypatch.setattr(runtime.settings, "memory_backend", "falkordb")
    monkeypatch.setattr(runtime.settings, "kv_backend", "redis")
    monkeypatch.setattr(runtime.settings, "queue_backend", "celery")
    monkeypatch.setattr(runtime.settings, "redis_url", "redis://redis.internal:6379/0")
    monkeypatch.setattr(runtime.settings, "celery_broker_url", "redis://redis.internal:6379/0")
    monkeypatch.setattr(runtime.settings, "celery_result_backend", "redis://redis.internal:6379/1")
    monkeypatch.setattr(runtime._falkordb_admin, "verify_connectivity", fake_verify_connectivity)
    monkeypatch.setattr(runtime.redis_async, "from_url", lambda url, decode_responses=True: FakeRedisClient(url))

    await runtime.reset_runtime_state()
    dependency_state = await runtime.probe_runtime_dependencies()

    assert dependency_state["status"] == "degraded"
    assert dependency_state["checks"]["falkordb"]["status"] == "ok"
    assert dependency_state["checks"]["redis"]["status"] == "ok"
    assert dependency_state["checks"]["celery_broker"]["status"] == "ok"
    assert dependency_state["checks"]["celery_result_backend"]["status"] == "error"
    assert dependency_state["runtime"]["redis_target"] == "redis.internal:6379"
    assert dependency_state["runtime"]["celery_broker_target"] == "redis.internal:6379"
    assert dependency_state["runtime"]["celery_result_backend_target"] == "redis.internal:6379"


async def test_run_index_job_wrapper_passes_current_code_index_helpers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_index_job_impl(**kwargs):
        captured.update(kwargs)
        return {"status": "READY"}

    def sentinel_build_file_rows(*_args, **_kwargs):
        return []

    monkeypatch.setattr(code_index, "run_index_job_impl", fake_run_index_job_impl)
    monkeypatch.setattr(code_index, "_build_file_rows", sentinel_build_file_rows)

    result = await code_index.run_index_job(index_id="idx_test")

    assert result == {"status": "READY"}
    assert captured["index_id"] == "idx_test"
    assert captured["build_file_rows_fn"] is sentinel_build_file_rows
    assert captured["materialize_index_fn"] is code_index._materialize_index
    assert captured["materialize_repo_source_ctx"] is code_index._materialize_repo_source
