from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from viberecall_mcp.config import get_settings
from viberecall_mcp.exports import (
    build_signed_download,
    delete_local_object,
    delete_local_prefix,
    export_storage_key,
    write_local_export,
)
from viberecall_mcp.metrics import job_duration_ms
from viberecall_mcp.db import SessionLocal
from viberecall_mcp.object_storage import (
    delete_object as delete_episode_object,
    delete_prefix as delete_episode_prefix,
    episode_storage_key,
    get_text as get_episode_text,
    put_text as put_episode_text,
)
from viberecall_mcp.repositories.audit_logs import insert_audit_log
from viberecall_mcp.repositories.episodes import (
    get_episode,
    list_project_episodes_for_export,
    mark_episode_enrichment_failed,
    mark_episode_enrichment_status,
)
from viberecall_mcp.repositories.exports import (
    get_export,
    mark_export_complete,
    mark_export_failed,
    mark_export_processing,
)
from viberecall_mcp.repositories.maintenance import (
    delete_all_project_episodes,
    delete_all_project_exports,
    delete_all_project_usage_events,
    delete_all_project_webhooks,
    delete_project_episodes_before,
    delete_project_exports_before,
    get_current_database_size_bytes,
    get_project_retention_days,
    list_inline_episodes_for_migration,
    mark_episode_content_externalized,
    scrub_project_audit_logs,
)
from viberecall_mcp.repositories.usage_events import create_usage_event
from viberecall_mcp.runtime import get_memory_core
from viberecall_mcp.workers.celery_app import celery_app


settings = get_settings()


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


async def _collect_all_facts(project_id: str) -> list[dict]:
    memory_core = get_memory_core()
    rows: list[dict] = []
    offset = 0
    page_size = 200
    while True:
        page = await memory_core.get_facts(
            project_id,
            filters={},
            limit=page_size,
            offset=offset,
        )
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def _build_export_document(
    *,
    project_id: str,
    episodes: list[dict],
    facts: list[dict],
) -> dict:
    entities_by_id: dict[str, dict] = {}
    relationships: set[tuple[str, str, str]] = set()

    fact_rows: list[dict] = []
    for fact in facts:
        fact_id = str(fact["id"])
        provenance = fact.get("provenance") or {}
        episode_ids = [str(value) for value in (provenance.get("episode_ids") or []) if value]
        for episode_id in episode_ids:
            relationships.add(("SUPPORTS", episode_id, fact_id))

        for entity in fact.get("entities") or []:
            entity_id = str(entity.get("id") or "")
            if not entity_id:
                continue
            entities_by_id.setdefault(
                entity_id,
                {
                    "entity_id": entity_id,
                    "type": str(entity.get("type") or ""),
                    "name": str(entity.get("name") or ""),
                },
            )
            relationships.add(("ABOUT", fact_id, entity_id))

        fact_rows.append(
            {
                "fact_id": fact_id,
                "text": str(fact.get("text") or ""),
                "valid_at": _iso(fact.get("valid_at")),
                "invalid_at": _iso(fact.get("invalid_at")),
                "ingested_at": _iso(fact.get("ingested_at")),
                "provenance": {
                    "episode_ids": episode_ids,
                    "reference_time": _iso(provenance.get("reference_time")),
                    "ingested_at": _iso(provenance.get("ingested_at")),
                },
            }
        )

    episode_rows = [
        {
            "episode_id": str(episode["episode_id"]),
            "reference_time": _iso(episode.get("reference_time")),
            "ingested_at": _iso(episode.get("ingested_at")),
            "summary": episode.get("summary"),
            "metadata": episode.get("metadata") or {},
        }
        for episode in episodes
    ]

    relation_rows = [
        {"type": rel_type, "source_id": source_id, "target_id": target_id}
        for rel_type, source_id, target_id in sorted(relationships)
    ]

    return {
        "format": "viberecall-export",
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "episodes": episode_rows,
        "entities": sorted(entities_by_id.values(), key=lambda item: item["entity_id"]),
        "facts": fact_rows,
        "relationships": relation_rows,
    }


def _delete_export_refs(refs: list[str]) -> int:
    deleted = 0
    for ref in refs:
        if not ref:
            continue
        if "://" in ref:
            continue
        if delete_local_object(object_key=ref):
            deleted += 1
    return deleted


async def _delete_episode_refs(refs: list[str]) -> int:
    deleted = 0
    for ref in refs:
        if not ref:
            continue
        if "://" in ref:
            continue
        if await delete_episode_object(object_key=ref):
            deleted += 1
    return deleted


async def run_ingest_job(*, episode_id: str, project_id: str, request_id: str, token_id: str | None) -> dict:
    started = time.perf_counter()
    async with SessionLocal() as session:
        episode = await get_episode(session, episode_id)
        if episode is None:
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/ingest",
                status="episode_not_found",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="ingest").observe((time.perf_counter() - started) * 1000)
            return {"status": "missing"}

        try:
            if not episode.get("content") and episode.get("content_ref"):
                episode["content"] = await get_episode_text(object_key=str(episode["content_ref"]))
            result = await get_memory_core().ingest_episode(project_id, episode)
            await mark_episode_enrichment_status(
                session,
                episode_id=episode_id,
                status="complete",
                summary=result.get("summary"),
            )
            await create_usage_event(
                session,
                project_id=project_id,
                token_id=token_id,
                tool="viberecall_save",
                vibe_tokens=1,
            )
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/ingest",
                status="complete",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="ingest").observe((time.perf_counter() - started) * 1000)
            return result
        except Exception as exc:  # noqa: BLE001
            await mark_episode_enrichment_failed(
                session,
                episode_id=episode_id,
                error=str(exc),
            )
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/ingest",
                status="failed",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="ingest").observe((time.perf_counter() - started) * 1000)
            raise


async def run_update_fact_job(
    *,
    project_id: str,
    request_id: str,
    token_id: str | None,
    fact_id: str,
    new_fact_id: str,
    new_text: str,
    effective_time: str,
    reason: str | None,
) -> dict:
    started = time.perf_counter()
    async with SessionLocal() as session:
        try:
            result = await get_memory_core().update_fact(
                project_id,
                fact_id=fact_id,
                new_fact_id=new_fact_id,
                new_text=new_text,
                effective_time=effective_time,
                reason=reason,
            )
            await create_usage_event(
                session,
                project_id=project_id,
                token_id=token_id,
                tool="viberecall_update_fact",
                vibe_tokens=1,
            )
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/update_fact",
                status="complete",
                project_id=project_id,
                token_id=token_id,
                tool_name="viberecall_update_fact",
            )
            job_duration_ms.labels(job="update_fact").observe((time.perf_counter() - started) * 1000)
            return result
        except Exception:  # noqa: BLE001
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/update_fact",
                status="failed",
                project_id=project_id,
                token_id=token_id,
                tool_name="viberecall_update_fact",
            )
            job_duration_ms.labels(job="update_fact").observe((time.perf_counter() - started) * 1000)
            raise


async def run_export_job(
    *,
    export_id: str,
    project_id: str,
    request_id: str,
    token_id: str | None,
) -> dict:
    started = time.perf_counter()
    async with SessionLocal() as session:
        export = await get_export(session, project_id=project_id, export_id=export_id)
        if export is None:
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/export",
                status="export_not_found",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="export").observe((time.perf_counter() - started) * 1000)
            return {"status": "missing"}

        await mark_export_processing(session, export_id=export_id)
        try:
            facts = await _collect_all_facts(project_id)
            episodes = await list_project_episodes_for_export(session, project_id=project_id)
            payload = _build_export_document(
                project_id=project_id,
                episodes=episodes,
                facts=facts,
            )
            object_key = export_storage_key(project_id, export_id)
            write_local_export(object_key=object_key, payload=payload)
            object_url, expires_at = build_signed_download(
                project_id=project_id,
                export_id=export_id,
            )
            await mark_export_complete(
                session,
                export_id=export_id,
                object_key=object_key,
                object_url=object_url,
                expires_at=expires_at,
            )
            await create_usage_event(
                session,
                project_id=project_id,
                token_id=token_id,
                tool="viberecall_export",
                vibe_tokens=1,
            )
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/export",
                status="complete",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="export").observe((time.perf_counter() - started) * 1000)
            return {"status": "complete", "export_id": export_id, "object_url": object_url}
        except Exception as exc:  # noqa: BLE001
            await mark_export_failed(session, export_id=export_id, error=str(exc))
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/export",
                status="failed",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="export").observe((time.perf_counter() - started) * 1000)
            raise


async def run_retention_job(
    *,
    project_id: str,
    request_id: str,
    token_id: str | None,
) -> dict:
    started = time.perf_counter()
    async with SessionLocal() as session:
        retention_days = await get_project_retention_days(session, project_id=project_id)
        if retention_days is None:
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/retention",
                status="project_not_found",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="retention").observe((time.perf_counter() - started) * 1000)
            return {"status": "missing"}

        cutoff = datetime.now(timezone.utc) - timedelta(days=max(retention_days, 0))
        try:
            deleted_episodes = await delete_project_episodes_before(
                session,
                project_id=project_id,
                cutoff=cutoff,
            )
            deleted_exports = await delete_project_exports_before(
                session,
                project_id=project_id,
                cutoff=cutoff,
            )
            await session.commit()

            deleted_objects = await _delete_episode_refs(deleted_episodes["content_refs"]) + _delete_export_refs(
                deleted_exports["object_keys"]
            )
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/retention",
                status="complete",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="retention").observe((time.perf_counter() - started) * 1000)
            return {
                "status": "complete",
                "project_id": project_id,
                "retention_days": retention_days,
                "cutoff": cutoff.isoformat(),
                "deleted_episodes": deleted_episodes["deleted_count"],
                "deleted_exports": deleted_exports["deleted_count"],
                "deleted_objects": deleted_objects,
            }
        except Exception:  # noqa: BLE001
            await session.rollback()
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/retention",
                status="failed",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="retention").observe((time.perf_counter() - started) * 1000)
            raise


async def run_purge_project_job(
    *,
    project_id: str,
    request_id: str,
    token_id: str | None,
) -> dict:
    started = time.perf_counter()
    async with SessionLocal() as session:
        try:
            exports_result = await delete_all_project_exports(session, project_id=project_id)
            episodes_result = await delete_all_project_episodes(session, project_id=project_id)
            usage_deleted = await delete_all_project_usage_events(session, project_id=project_id)
            webhooks_deleted = await delete_all_project_webhooks(session, project_id=project_id)
            scrubbed_logs = await scrub_project_audit_logs(session, project_id=project_id)
            await session.commit()

            deleted_episode_prefix = await delete_episode_prefix(f"projects/{project_id}/episodes")
            deleted_export_prefix = delete_local_prefix(f"projects/{project_id}/exports")
            deleted_refs = await _delete_episode_refs(episodes_result["content_refs"]) + _delete_export_refs(
                exports_result["object_keys"]
            )
            await get_memory_core().purge_project(project_id)

            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/purge_project",
                status="complete",
                project_id=project_id,
                token_id=token_id,
                args_hash=None,
            )
            job_duration_ms.labels(job="purge_project").observe((time.perf_counter() - started) * 1000)
            return {
                "status": "complete",
                "project_id": project_id,
                "deleted_episodes": episodes_result["deleted_count"],
                "deleted_exports": exports_result["deleted_count"],
                "deleted_usage_events": usage_deleted,
                "deleted_webhooks": webhooks_deleted,
                "scrubbed_audit_logs": scrubbed_logs,
                "deleted_objects": deleted_episode_prefix + deleted_export_prefix + deleted_refs,
            }
        except Exception:  # noqa: BLE001
            await session.rollback()
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/purge_project",
                status="failed",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="purge_project").observe((time.perf_counter() - started) * 1000)
            raise


async def run_migrate_inline_to_object_job(
    *,
    project_id: str,
    request_id: str,
    token_id: str | None,
    force: bool,
) -> dict:
    started = time.perf_counter()
    async with SessionLocal() as session:
        try:
            current_db_size = await get_current_database_size_bytes(session)
            threshold = settings.inline_migration_db_size_threshold_bytes
            if not force and current_db_size < threshold:
                await insert_audit_log(
                    session,
                    request_id=request_id,
                    action="worker/migrate_inline_to_object",
                    status="skipped:db_size_below_threshold",
                    project_id=project_id,
                    token_id=token_id,
                )
                job_duration_ms.labels(job="migrate_inline_to_object").observe(
                    (time.perf_counter() - started) * 1000
                )
                return {
                    "status": "skipped",
                    "project_id": project_id,
                    "db_size_bytes": current_db_size,
                    "threshold_bytes": threshold,
                    "migrated_count": 0,
                }

            migrated_count = 0
            migrated_bytes = 0
            while True:
                rows = await list_inline_episodes_for_migration(
                    session,
                    project_id=project_id,
                    min_bytes=settings.raw_episode_inline_max_bytes,
                    limit=100,
                )
                if not rows:
                    break

                uploaded_in_batch: list[str] = []
                try:
                    for row in rows:
                        content = str(row.get("content") or "")
                        if not content:
                            continue
                        object_key = episode_storage_key(project_id, str(row["episode_id"]))
                        await put_episode_text(object_key=object_key, content=content)
                        uploaded_in_batch.append(object_key)
                        await mark_episode_content_externalized(
                            session,
                            episode_id=str(row["episode_id"]),
                            content_ref=object_key,
                            summary=content[:160].strip() or None,
                        )
                        migrated_count += 1
                        migrated_bytes += len(content.encode("utf-8"))
                    await session.commit()
                except Exception:
                    await session.rollback()
                    for object_key in uploaded_in_batch:
                        try:
                            await delete_episode_object(object_key=object_key)
                        except Exception:  # noqa: BLE001
                            pass
                    raise

            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/migrate_inline_to_object",
                status="complete",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="migrate_inline_to_object").observe((time.perf_counter() - started) * 1000)
            return {
                "status": "complete",
                "project_id": project_id,
                "db_size_bytes": current_db_size,
                "threshold_bytes": threshold,
                "migrated_count": migrated_count,
                "migrated_bytes": migrated_bytes,
            }
        except Exception:
            await insert_audit_log(
                session,
                request_id=request_id,
                action="worker/migrate_inline_to_object",
                status="failed",
                project_id=project_id,
                token_id=token_id,
            )
            job_duration_ms.labels(job="migrate_inline_to_object").observe((time.perf_counter() - started) * 1000)
            raise


@celery_app.task(
    name="viberecall.ingest_episode",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def ingest_episode_task(episode_id: str, project_id: str, request_id: str, token_id: str | None) -> dict:
    import asyncio

    return asyncio.run(
        run_ingest_job(
            episode_id=episode_id,
            project_id=project_id,
            request_id=request_id,
            token_id=token_id,
        )
    )


@celery_app.task(
    name="viberecall.update_fact",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def update_fact_task(
    project_id: str,
    request_id: str,
    token_id: str | None,
    fact_id: str,
    new_fact_id: str,
    new_text: str,
    effective_time: str,
    reason: str | None,
) -> dict:
    import asyncio

    return asyncio.run(
        run_update_fact_job(
            project_id=project_id,
            request_id=request_id,
            token_id=token_id,
            fact_id=fact_id,
            new_fact_id=new_fact_id,
            new_text=new_text,
            effective_time=effective_time,
            reason=reason,
        )
    )


@celery_app.task(
    name="viberecall.export_project",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def export_project_task(export_id: str, project_id: str, request_id: str, token_id: str | None) -> dict:
    import asyncio

    return asyncio.run(
        run_export_job(
            export_id=export_id,
            project_id=project_id,
            request_id=request_id,
            token_id=token_id,
        )
    )


@celery_app.task(
    name="viberecall.retention_project",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def retention_project_task(project_id: str, request_id: str, token_id: str | None) -> dict:
    import asyncio

    return asyncio.run(
        run_retention_job(
            project_id=project_id,
            request_id=request_id,
            token_id=token_id,
        )
    )


@celery_app.task(
    name="viberecall.purge_project",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def purge_project_task(project_id: str, request_id: str, token_id: str | None) -> dict:
    import asyncio

    return asyncio.run(
        run_purge_project_job(
            project_id=project_id,
            request_id=request_id,
            token_id=token_id,
        )
    )


@celery_app.task(
    name="viberecall.migrate_inline_to_object",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def migrate_inline_to_object_task(project_id: str, request_id: str, token_id: str | None, force: bool) -> dict:
    import asyncio

    return asyncio.run(
        run_migrate_inline_to_object_job(
            project_id=project_id,
            request_id=request_id,
            token_id=token_id,
            force=force,
        )
    )
