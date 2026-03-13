from celery import Celery

from viberecall_mcp.config import get_settings


settings = get_settings()

celery_app = Celery(
    "viberecall_mcp",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["viberecall_mcp.workers.tasks"],
)
celery_app.conf.task_always_eager = settings.queue_backend == "eager"
celery_app.conf.task_default_queue = "memory"
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.broker_connection_retry_on_startup = True
