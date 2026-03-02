from __future__ import annotations

from dataclasses import dataclass

from viberecall_mcp.config import get_settings
from viberecall_mcp.idempotency import LocalIdempotencyStore
from viberecall_mcp.idempotency_redis import RedisIdempotencyStore
from viberecall_mcp.ids import new_id
from viberecall_mcp.metrics import queue_depth
from viberecall_mcp.memory_core.graphiti_adapter import GraphitiMemoryCore
from viberecall_mcp.memory_core.interface import MemoryCore
from viberecall_mcp.memory_core.local_adapter import LocalMemoryCore
from viberecall_mcp.memory_core.neo4j_adapter import Neo4jMemoryCore
from viberecall_mcp.memory_core.neo4j_admin import Neo4jDatabaseManager
from viberecall_mcp.rate_limit import LocalRateLimiter
from viberecall_mcp.rate_limit_redis import RedisRateLimiter
from viberecall_mcp.redis_client import get_redis_client
from viberecall_mcp.runtime_types import EnqueueUpdateFactResult, IdempotencyStore, RateLimiter, TaskQueue


@dataclass(slots=True)
class EagerTaskQueue:
    async def enqueue_ingest(
        self,
        *,
        episode_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers import tasks

        job_id = new_id("job_ingest")
        queue_depth.labels(queue="memory").inc()
        try:
            await tasks.run_ingest_job(
                episode_id=episode_id,
                project_id=project_id,
                request_id=request_id,
                token_id=token_id,
            )
        finally:
            queue_depth.labels(queue="memory").dec()
        return job_id

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
    ) -> EnqueueUpdateFactResult:
        from viberecall_mcp.workers import tasks

        job_id = new_id("job_update")
        queue_depth.labels(queue="memory").inc()
        try:
            result = await tasks.run_update_fact_job(
                project_id=project_id,
                request_id=request_id,
                token_id=token_id,
                fact_id=fact_id,
                new_fact_id=new_fact_id,
                new_text=new_text,
                effective_time=effective_time,
                reason=reason,
            )
        finally:
            queue_depth.labels(queue="memory").dec()
        return EnqueueUpdateFactResult(job_id=job_id, immediate_result=result)

    async def enqueue_export(
        self,
        *,
        export_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers import tasks

        job_id = new_id("job_export")
        queue_depth.labels(queue="exports").inc()
        try:
            await tasks.run_export_job(
                export_id=export_id,
                project_id=project_id,
                request_id=request_id,
                token_id=token_id,
            )
        finally:
            queue_depth.labels(queue="exports").dec()
        return job_id

    async def enqueue_retention(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers import tasks

        job_id = new_id("job_retention")
        queue_depth.labels(queue="maintenance").inc()
        try:
            await tasks.run_retention_job(
                project_id=project_id,
                request_id=request_id,
                token_id=token_id,
            )
        finally:
            queue_depth.labels(queue="maintenance").dec()
        return job_id

    async def enqueue_purge_project(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers import tasks

        job_id = new_id("job_purge")
        queue_depth.labels(queue="maintenance").inc()
        try:
            await tasks.run_purge_project_job(
                project_id=project_id,
                request_id=request_id,
                token_id=token_id,
            )
        finally:
            queue_depth.labels(queue="maintenance").dec()
        return job_id

    async def enqueue_migrate_inline_to_object(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
        force: bool,
    ) -> str:
        from viberecall_mcp.workers import tasks

        job_id = new_id("job_migrate")
        queue_depth.labels(queue="maintenance").inc()
        try:
            await tasks.run_migrate_inline_to_object_job(
                project_id=project_id,
                request_id=request_id,
                token_id=token_id,
                force=force,
            )
        finally:
            queue_depth.labels(queue="maintenance").dec()
        return job_id


@dataclass(slots=True)
class CeleryTaskQueue:
    async def enqueue_ingest(
        self,
        *,
        episode_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers.tasks import ingest_episode_task

        task = ingest_episode_task.delay(episode_id, project_id, request_id, token_id)
        return str(task.id)

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
    ) -> EnqueueUpdateFactResult:
        from viberecall_mcp.workers.tasks import update_fact_task

        task = update_fact_task.delay(
            project_id,
            request_id,
            token_id,
            fact_id,
            new_fact_id,
            new_text,
            effective_time,
            reason,
        )
        return EnqueueUpdateFactResult(job_id=str(task.id), immediate_result=None)

    async def enqueue_export(
        self,
        *,
        export_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers.tasks import export_project_task

        task = export_project_task.delay(export_id, project_id, request_id, token_id)
        return str(task.id)

    async def enqueue_retention(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers.tasks import retention_project_task

        task = retention_project_task.delay(project_id, request_id, token_id)
        return str(task.id)

    async def enqueue_purge_project(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
    ) -> str:
        from viberecall_mcp.workers.tasks import purge_project_task

        task = purge_project_task.delay(project_id, request_id, token_id)
        return str(task.id)

    async def enqueue_migrate_inline_to_object(
        self,
        *,
        project_id: str,
        request_id: str,
        token_id: str | None,
        force: bool,
    ) -> str:
        from viberecall_mcp.workers.tasks import migrate_inline_to_object_task

        task = migrate_inline_to_object_task.delay(project_id, request_id, token_id, force)
        return str(task.id)


settings = get_settings()
_neo4j_admin = Neo4jDatabaseManager()
_local_memory_core = LocalMemoryCore()
_neo4j_memory_core = Neo4jMemoryCore(_neo4j_admin)
_graphiti_memory_core = GraphitiMemoryCore(_neo4j_admin)
_local_idempotency_store = LocalIdempotencyStore()
_redis_idempotency_store = RedisIdempotencyStore(get_redis_client())
_local_rate_limiter = LocalRateLimiter()
_redis_rate_limiter = RedisRateLimiter(get_redis_client())
_eager_task_queue = EagerTaskQueue()
_celery_task_queue = CeleryTaskQueue()


def get_memory_core() -> MemoryCore:
    if settings.memory_backend == "graphiti":
        return _graphiti_memory_core
    if settings.memory_backend == "neo4j":
        return _neo4j_memory_core
    return _local_memory_core


def get_idempotency_store() -> IdempotencyStore:
    if settings.kv_backend == "redis":
        return _redis_idempotency_store
    return _local_idempotency_store


def get_rate_limiter() -> RateLimiter:
    if settings.kv_backend == "redis":
        return _redis_rate_limiter
    return _local_rate_limiter


def get_task_queue() -> TaskQueue:
    if settings.queue_backend == "celery":
        return _celery_task_queue
    return _eager_task_queue


async def reset_runtime_state() -> None:
    if settings.memory_backend == "local":
        await _local_memory_core.reset()
    if settings.kv_backend == "local":
        await _local_idempotency_store.reset()
        await _local_rate_limiter.reset()
