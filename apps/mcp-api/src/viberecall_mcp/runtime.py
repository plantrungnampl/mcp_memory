from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit

from redis import asyncio as redis_async

from viberecall_mcp.config import get_settings
from viberecall_mcp.graphiti_upstream_bridge import UpstreamGraphitiBridge
from viberecall_mcp.idempotency import LocalIdempotencyStore
from viberecall_mcp.idempotency_redis import RedisIdempotencyStore
from viberecall_mcp.ids import new_id
from viberecall_mcp.metrics import queue_depth
from viberecall_mcp.memory_core.graphiti_adapter import GraphitiMemoryCore
from viberecall_mcp.memory_core.interface import MemoryCore
from viberecall_mcp.memory_core.local_adapter import LocalMemoryCore
from viberecall_mcp.memory_core.falkordb_adapter import FalkorDBMemoryCore
from viberecall_mcp.memory_core.falkordb_admin import FalkorDBGraphManager
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
        operation_id: str | None = None,
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
                operation_id=operation_id,
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
        operation_id: str | None = None,
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
                operation_id=operation_id,
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

    async def enqueue_index_repo(
        self,
        *,
        index_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
        operation_id: str | None = None,
    ) -> str:
        from viberecall_mcp.workers import tasks

        job_id = new_id("job_index")
        queue_depth.labels(queue="indexing").inc()
        try:
            await tasks.run_index_job(index_id=index_id, operation_id=operation_id)
        finally:
            queue_depth.labels(queue="indexing").dec()
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
        operation_id: str | None = None,
    ) -> str:
        from viberecall_mcp.workers.tasks import ingest_episode_task

        task = ingest_episode_task.delay(episode_id, project_id, request_id, token_id, operation_id)
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
        operation_id: str | None = None,
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
            operation_id,
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

    async def enqueue_index_repo(
        self,
        *,
        index_id: str,
        project_id: str,
        request_id: str,
        token_id: str | None,
        operation_id: str | None = None,
    ) -> str:
        from viberecall_mcp.workers.tasks import index_repo_task

        task = index_repo_task.delay(index_id, project_id, request_id, token_id, operation_id)
        return str(task.id)


settings = get_settings()
_falkordb_admin = FalkorDBGraphManager()
_local_memory_core = LocalMemoryCore()
_falkordb_memory_core = FalkorDBMemoryCore(_falkordb_admin)
_graphiti_memory_core = GraphitiMemoryCore(_falkordb_admin)
_graphiti_upstream_bridge = UpstreamGraphitiBridge(_falkordb_admin)
_local_idempotency_store = LocalIdempotencyStore()
_redis_idempotency_store = RedisIdempotencyStore(get_redis_client())
_local_rate_limiter = LocalRateLimiter()
_redis_rate_limiter = RedisRateLimiter(get_redis_client())
_eager_task_queue = EagerTaskQueue()
_celery_task_queue = CeleryTaskQueue()


@dataclass(slots=True)
class _DependencyProbeCacheEntry:
    fingerprint: tuple[str, ...]
    value: dict
    expires_at_monotonic: float


_dependency_probe_cache: _DependencyProbeCacheEntry | None = None


def _sanitize_falkordb_target(host: str, port: int) -> str:
    try:
        parsed = urlsplit(f"redis://{host}:{port}")
        target_host = parsed.hostname or host or "unknown"
        target_port = parsed.port or port
        return f"{target_host}:{target_port}"
    except Exception:  # noqa: BLE001
        return f"{host}:{port}"


def _sanitize_redis_url_target(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if parsed.scheme == "unix":
            return parsed.path or "unix-socket"
        host = parsed.hostname or parsed.path or "unknown"
        port = parsed.port or 6379
        return f"{host}:{port}"
    except Exception:  # noqa: BLE001
        return "unknown"


async def _probe_redis_url(url: str, *, detail_label: str) -> dict[str, str]:
    split = urlsplit(url)
    if split.scheme not in {"redis", "rediss", "unix"}:
        return {
            "status": "skipped",
            "detail": f"{detail_label} uses unsupported scheme '{split.scheme or 'unknown'}'.",
        }

    client = redis_async.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "detail": str(exc).strip() or f"{detail_label} connectivity check failed.",
        }
    finally:
        await client.aclose()

    return {
        "status": "ok",
        "detail": f"{detail_label} connection is healthy.",
    }


def _dependency_probe_fingerprint() -> tuple[str, ...]:
    return (
        settings.memory_backend,
        settings.kv_backend,
        settings.queue_backend,
        settings.falkordb_host,
        str(settings.falkordb_port),
        settings.falkordb_username,
        settings.falkordb_password,
        settings.redis_url,
        settings.celery_broker_url,
        settings.celery_result_backend,
    )


def _cached_dependency_state() -> dict | None:
    global _dependency_probe_cache

    entry = _dependency_probe_cache
    if entry is None:
        return None
    if entry.fingerprint != _dependency_probe_fingerprint():
        _dependency_probe_cache = None
        return None
    if monotonic() >= entry.expires_at_monotonic:
        _dependency_probe_cache = None
        return None
    return deepcopy(entry.value)


def _store_dependency_state(value: dict) -> dict:
    global _dependency_probe_cache

    ttl_seconds = (
        settings.dependency_probe_cache_ok_ttl_seconds
        if value.get("status") == "ok"
        else settings.dependency_probe_cache_error_ttl_seconds
    )
    ttl_seconds = max(0.0, float(ttl_seconds))
    stored_value = deepcopy(value)
    _dependency_probe_cache = _DependencyProbeCacheEntry(
        fingerprint=_dependency_probe_fingerprint(),
        value=stored_value,
        expires_at_monotonic=monotonic() + ttl_seconds,
    )
    return deepcopy(stored_value)


def get_memory_core() -> MemoryCore:
    backend = settings.memory_backend
    if backend == "graphiti":
        return _graphiti_memory_core
    if backend == "falkordb":
        return _falkordb_memory_core
    return _local_memory_core


def get_graphiti_upstream_bridge() -> UpstreamGraphitiBridge:
    return _graphiti_upstream_bridge


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


def build_graph_dependency_detail(
    dependency_state: dict,
    *,
    fallback_detail: str | None = None,
) -> str:
    falkordb_detail = dependency_state.get("checks", {}).get("falkordb", {}).get("detail")
    backend = dependency_state.get("runtime", {}).get("memory_backend", "unknown")
    detail = falkordb_detail or fallback_detail
    detail_suffix = f": {detail}" if detail else ""
    return f"Graph dependency check failed for memory backend '{backend}'{detail_suffix}"


async def get_graph_dependency_failure_detail() -> str | None:
    if settings.memory_backend not in {"falkordb", "graphiti"}:
        return None

    dependency_state = await probe_runtime_dependencies()
    if dependency_state["status"] == "ok":
        return None
    return build_graph_dependency_detail(dependency_state)


async def probe_runtime_dependencies() -> dict:
    cached = _cached_dependency_state()
    if cached is not None:
        return cached

    memory_backend = settings.memory_backend
    checks = {
        "falkordb": {
            "status": "skipped",
            "detail": "FalkorDB is not required for local memory backend.",
        },
        "redis": {
            "status": "skipped",
            "detail": "Redis KV backend is not required.",
        },
        "celery_broker": {
            "status": "skipped",
            "detail": "Celery queue backend is not required.",
        },
        "celery_result_backend": {
            "status": "skipped",
            "detail": "Celery result backend is not required.",
        },
    }

    if memory_backend in {"falkordb", "graphiti"}:
        try:
            await _falkordb_admin.verify_connectivity()
            checks["falkordb"] = {
                "status": "ok",
                "detail": "FalkorDB connection is healthy.",
            }
        except Exception as exc:  # noqa: BLE001
            checks["falkordb"] = {
                "status": "error",
                "detail": str(exc).strip() or "FalkorDB connectivity check failed.",
            }

    if settings.kv_backend == "redis":
        checks["redis"] = await _probe_redis_url(
            settings.redis_url,
            detail_label="Redis KV backend",
        )

    if settings.queue_backend == "celery":
        checks["celery_broker"] = await _probe_redis_url(
            settings.celery_broker_url,
            detail_label="Celery broker",
        )
        checks["celery_result_backend"] = await _probe_redis_url(
            settings.celery_result_backend,
            detail_label="Celery result backend",
        )

    status = "degraded" if any(check["status"] == "error" for check in checks.values()) else "ok"
    return _store_dependency_state(
        {
            "status": status,
            "runtime": {
                "memory_backend": memory_backend,
                "kv_backend": settings.kv_backend,
                "queue_backend": settings.queue_backend,
                "falkordb_target": _sanitize_falkordb_target(settings.falkordb_host, settings.falkordb_port),
                "redis_target": _sanitize_redis_url_target(settings.redis_url),
                "celery_broker_target": _sanitize_redis_url_target(settings.celery_broker_url),
                "celery_result_backend_target": _sanitize_redis_url_target(settings.celery_result_backend),
            },
            "checks": checks,
        }
    )


async def reset_runtime_state() -> None:
    global _dependency_probe_cache

    if settings.memory_backend == "local":
        await _local_memory_core.reset()
    if settings.kv_backend == "local":
        await _local_idempotency_store.reset()
        await _local_rate_limiter.reset()
    await _graphiti_upstream_bridge.close()
    _dependency_probe_cache = None
