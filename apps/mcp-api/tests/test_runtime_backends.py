from __future__ import annotations

from types import SimpleNamespace

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

    monkeypatch.setattr(runtime.settings, "memory_backend", "neo4j")
    monkeypatch.setattr(runtime.settings, "kv_backend", "redis")
    monkeypatch.setattr(runtime.settings, "queue_backend", "celery")

    assert runtime.get_memory_core() is runtime._neo4j_memory_core
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

    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_ingest_job", fake_run_ingest_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_update_fact_job", fake_run_update_fact_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_export_job", fake_run_export_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_retention_job", fake_run_retention_job)
    monkeypatch.setattr("viberecall_mcp.workers.tasks.run_purge_project_job", fake_run_purge_project_job)
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.run_migrate_inline_to_object_job",
        fake_run_migrate_inline_to_object_job,
    )

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

    assert ingest_job_id.startswith("job_ingest_")
    assert update_result.job_id.startswith("job_update_")
    assert update_result.immediate_result is not None
    assert export_job_id.startswith("job_export_")
    assert retention_job_id.startswith("job_retention_")
    assert purge_job_id.startswith("job_purge_")
    assert migrate_job_id.startswith("job_migrate_")


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

    assert ingest_job_id == "celery-ingest-1"
    assert update_result.job_id == "celery-update-1"
    assert update_result.immediate_result is None
    assert export_job_id == "celery-export-1"
    assert retention_job_id == "celery-retention-1"
    assert purge_job_id == "celery-purge-1"
    assert migrate_job_id == "celery-migrate-1"
