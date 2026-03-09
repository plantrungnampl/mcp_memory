from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.code_index_shared import _now_iso, _stats_payload
from viberecall_mcp.code_index_sources import (
    _INTERNAL_FULL_SNAPSHOT_MODE,
    _materialize_repo_source,
    _normalize_full_snapshot_mode,
    _repo_source_payload,
    _resolve_repo_path,
    normalize_repo_source,
)
from viberecall_mcp.code_index_store import (
    _clone_index_rows,
    _delete_previous_ready_children,
    _get_active_index_run,
    _get_index_run,
    _get_latest_ready_index_run,
    _insert_index_run,
    _load_index_file_rows,
    _mark_index_run_failed,
    _mark_index_run_ready,
    _mark_index_run_running,
    _set_index_run_job_id,
    _store_materialized_snapshot,
    _update_index_run_progress,
)
from viberecall_mcp.db import open_db_session
from viberecall_mcp.ids import new_id
from viberecall_mcp.repositories.operations import complete_operation, fail_operation, mark_operation_running


async def request_index_repo_impl(
    *,
    session: AsyncSession,
    project_id: str,
    repo_source: dict[str, Any],
    mode: str,
    max_files: int,
    requested_by_token_id: str | None,
    commit: bool = True,
) -> dict[str, Any]:
    normalized_mode = _normalize_full_snapshot_mode(mode)
    normalized_source = normalize_repo_source(repo_source)
    repo_path = str(normalized_source["repo_source_ref"])
    if normalized_source["type"] in {"git", "workspace_bundle"}:
        repo_root = repo_path
    else:
        repo_root = str(_resolve_repo_path(repo_path))

    active = await _get_active_index_run(session, project_id=project_id)
    if active is not None:
        raise RuntimeError(
            json.dumps(
                {
                    "code": "CONFLICT",
                    "index_id": active["index_id"],
                    "job_id": active.get("job_id"),
                }
            )
        )

    index_id = new_id("idx")
    await _insert_index_run(
        session,
        index_id=index_id,
        project_id=project_id,
        repo_path=str(repo_root),
        repo_source_type=str(normalized_source["type"]),
        repo_source_ref=str(normalized_source["repo_source_ref"]),
        source_ref_value=normalized_source.get("ref"),
        repo_name=normalized_source.get("repo_name"),
        base_commit=normalized_source.get("base_commit"),
        credential_ref=normalized_source.get("credential_ref"),
        mode=_INTERNAL_FULL_SNAPSHOT_MODE,
        base_ref=None,
        head_ref=None,
        max_files=max_files,
        requested_by_token_id=requested_by_token_id,
    )
    if commit:
        await session.commit()
    return {
        "index_run_id": index_id,
        "index_id": index_id,
        "project_id": project_id,
        "repo_source": _repo_source_payload(
            {
                "repo_source_type": normalized_source["type"],
                "repo_source_ref": normalized_source["repo_source_ref"],
                "source_ref_value": normalized_source.get("ref"),
                "repo_name": normalized_source.get("repo_name"),
                "base_commit": normalized_source.get("base_commit"),
                "credential_ref": normalized_source.get("credential_ref"),
            }
        ),
        "mode": normalized_mode,
        "max_files": max_files,
        "queued_at": _now_iso(),
    }


async def attach_index_job_id_impl(
    *,
    session: AsyncSession,
    index_id: str,
    job_id: str,
    commit: bool = True,
) -> None:
    await _set_index_run_job_id(session, index_id=index_id, job_id=job_id)
    if commit:
        await session.commit()


async def mark_index_request_failed_impl(
    *,
    session: AsyncSession,
    index_id: str,
    error: str,
    commit: bool = True,
) -> None:
    await _mark_index_run_failed(session, index_id=index_id, error=error)
    if commit:
        await session.commit()


async def run_index_job_impl(
    *,
    index_id: str,
    operation_id: str | None = None,
    open_db_session_ctx: Callable[[], Any] = open_db_session,
    get_index_run_fn: Callable[..., Awaitable[dict[str, Any] | None]] = _get_index_run,
    mark_operation_running_fn: Callable[..., Awaitable[None]] = mark_operation_running,
    mark_index_run_running_fn: Callable[..., Awaitable[None]] = _mark_index_run_running,
    get_latest_ready_index_run_fn: Callable[..., Awaitable[dict[str, Any] | None]] = _get_latest_ready_index_run,
    materialize_repo_source_ctx: Callable[..., Any] = _materialize_repo_source,
    iter_candidate_files_fn: Callable[..., list[Any]] | None = None,
    git_changed_files_fn: Callable[..., list[str]] | None = None,
    filter_supported_rel_paths_fn: Callable[..., list[Any]] | None = None,
    update_index_run_progress_fn: Callable[..., Awaitable[None]] = _update_index_run_progress,
    build_file_rows_fn: Callable[..., list[dict[str, Any]]] | None = None,
    mark_index_run_failed_fn: Callable[..., Awaitable[None]] = _mark_index_run_failed,
    load_index_file_rows_fn: Callable[..., Awaitable[list[dict[str, Any]]]] = _load_index_file_rows,
    materialize_index_fn: Callable[..., dict[str, Any]] | None = None,
    store_materialized_snapshot_fn: Callable[..., Awaitable[None]] = _store_materialized_snapshot,
    mark_index_run_ready_fn: Callable[..., Awaitable[None]] = _mark_index_run_ready,
    delete_previous_ready_children_fn: Callable[..., Awaitable[None]] = _delete_previous_ready_children,
    complete_operation_fn: Callable[..., Awaitable[None]] = complete_operation,
    fail_operation_fn: Callable[..., Awaitable[None]] = fail_operation,
    clone_index_rows_fn: Callable[..., Awaitable[None]] = _clone_index_rows,
    stats_payload_fn: Callable[[dict[str, Any] | None], dict[str, int]] = _stats_payload,
    now_iso_fn: Callable[[], str] = _now_iso,
) -> dict[str, Any]:
    if iter_candidate_files_fn is None or git_changed_files_fn is None or filter_supported_rel_paths_fn is None:
        raise ValueError("run_index_job_impl requires file discovery helpers")
    if build_file_rows_fn is None or materialize_index_fn is None:
        raise ValueError("run_index_job_impl requires materialization helpers")

    async with open_db_session_ctx() as session:
        run = await get_index_run_fn(session, index_id=index_id)
        if run is None:
            raise ValueError(f"Unknown index run: {index_id}")

        project_id = str(run["project_id"])
        mode = str(run["mode"])
        base_ref = run.get("base_ref")
        head_ref = run.get("head_ref")
        max_files = int(run.get("max_files") or 5000)

        try:
            if operation_id:
                await mark_operation_running_fn(session, operation_id=operation_id)
            await mark_index_run_running_fn(
                session,
                index_id=index_id,
                phase="discovering",
                effective_mode=mode,
            )
            await session.commit()

            latest_ready = await get_latest_ready_index_run_fn(session, project_id=project_id)
            latest_ready_id = str(latest_ready["index_id"]) if latest_ready is not None else None

            async with materialize_repo_source_ctx(
                session,
                project_id=project_id,
                repo_source_type=run.get("repo_source_type"),
                repo_source_ref=str(run.get("repo_source_ref") or run["repo_path"]),
                source_ref_value=run.get("source_ref_value"),
                credential_ref=run.get("credential_ref"),
            ) as repo_root:
                if mode == "snapshot":
                    target_paths = iter_candidate_files_fn(repo_root, max_files)
                    scanned_files = len(target_paths)
                    changed_files = len(target_paths)
                else:
                    try:
                        rel_paths = git_changed_files_fn(repo_root, str(base_ref), str(head_ref))
                    except RuntimeError as exc:
                        await mark_index_run_failed_fn(session, index_id=index_id, error=str(exc))
                        await session.commit()
                        raise

                    target_paths = filter_supported_rel_paths_fn(repo_root, rel_paths)[:max_files]
                    scanned_files = len(target_paths)
                    changed_files = len(target_paths)

                    if not target_paths:
                        async with session.begin():
                            if latest_ready_id is not None:
                                await clone_index_rows_fn(session, source_index_id=latest_ready_id, target_index_id=index_id)
                                source_ready = await get_index_run_fn(session, index_id=latest_ready_id)
                                ready_stats = stats_payload_fn(source_ready)
                                top_modules = list(source_ready.get("top_modules_json") or []) if source_ready else []
                                top_files = list(source_ready.get("top_files_json") or []) if source_ready else []
                            else:
                                ready_stats = stats_payload_fn(None)
                                top_modules = []
                                top_files = []
                            await mark_index_run_ready_fn(
                                session,
                                index_id=index_id,
                                effective_mode="diff",
                                scanned_files=0,
                                changed_files=0,
                                processed_files=0,
                                stats=ready_stats,
                                top_modules=top_modules,
                                top_files=top_files,
                            )
                            await delete_previous_ready_children_fn(session, project_id=project_id, keep_index_id=index_id)
                        result_payload = {
                            "status": "READY",
                            "project_id": project_id,
                            "index_id": index_id,
                            "scanned_files": 0,
                            "changed_files": 0,
                        }
                        if operation_id:
                            await complete_operation_fn(session, operation_id=operation_id, result_payload=result_payload)
                            await session.commit()
                        return result_payload

                await update_index_run_progress_fn(
                    session,
                    index_id=index_id,
                    phase="extracting",
                    processed_files=0,
                    total_files=len(target_paths),
                    scanned_files=scanned_files,
                    changed_files=changed_files,
                )
                await session.commit()

                new_rows = build_file_rows_fn(repo_root, target_paths)
                processed_files = len(new_rows)

                if mode == "diff":
                    if latest_ready_id is None:
                        await mark_index_run_failed_fn(
                            session,
                            index_id=index_id,
                            error="Diff indexing requires an existing READY snapshot for this project.",
                        )
                        await session.commit()
                        raise RuntimeError("Diff indexing requires an existing READY snapshot for this project.")
                    changed_set = {str(path.relative_to(repo_root)) for path in target_paths}
                    previous_rows = [
                        row
                        for row in await load_index_file_rows_fn(session, index_id=latest_ready_id)
                        if str(row.get("path") or "") not in changed_set
                    ]
                    merged_rows = previous_rows + new_rows
                else:
                    merged_rows = new_rows

                await update_index_run_progress_fn(
                    session,
                    index_id=index_id,
                    phase="materializing",
                    processed_files=processed_files,
                    total_files=len(target_paths),
                    scanned_files=scanned_files,
                    changed_files=changed_files,
                )
                await session.commit()

                materialized = materialize_index_fn(
                    project_id=project_id,
                    repo_path=repo_root,
                    indexed_at=now_iso_fn(),
                    mode=mode,
                    source="indexing",
                    file_rows=merged_rows,
                )

                async with session.begin():
                    await store_materialized_snapshot_fn(
                        session,
                        index_id=index_id,
                        file_rows=materialized.get("files") or [],
                        materialized=materialized,
                    )
                    await mark_index_run_ready_fn(
                        session,
                        index_id=index_id,
                        effective_mode=mode,
                        scanned_files=scanned_files,
                        changed_files=changed_files,
                        processed_files=processed_files,
                        stats=materialized.get("stats") or {},
                        top_modules=list((materialized.get("architecture") or {}).get("top_modules") or []),
                        top_files=list((materialized.get("architecture") or {}).get("top_files") or []),
                    )
                    await delete_previous_ready_children_fn(session, project_id=project_id, keep_index_id=index_id)

                result_payload = {
                    "status": "READY",
                    "project_id": project_id,
                    "index_id": index_id,
                    "scanned_files": scanned_files,
                    "changed_files": changed_files,
                }
                if operation_id:
                    await complete_operation_fn(session, operation_id=operation_id, result_payload=result_payload)
                    await session.commit()
                return result_payload
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            if (await get_index_run_fn(session, index_id=index_id) or {}).get("status") != "FAILED":
                await mark_index_run_failed_fn(session, index_id=index_id, error=str(exc))
                await session.commit()
            if operation_id:
                await fail_operation_fn(
                    session,
                    operation_id=operation_id,
                    error_payload={"code": "INDEX_FAILED", "message": str(exc)},
                )
                await session.commit()
            raise
