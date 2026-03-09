from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.code_index_jobs import (
    attach_index_job_id_impl,
    mark_index_request_failed_impl,
    request_index_repo_impl,
    run_index_job_impl,
)
from viberecall_mcp.code_index_materialize import (
    _build_file_rows,
    _extract_file_row,
    _extract_snippet,
    _git_changed_files,
    _iter_candidate_files,
    _js_ts_symbols_and_imports,
    _language_for_path,
    _materialize_index,
    _module_name_for_file,
    _python_symbols_and_imports,
    _read_text,
    _sha1,
    _filter_supported_rel_paths,
)
from viberecall_mcp.code_index_read_models import (
    _chunk_score,
    _module_entity_id_from_name,
    _search_entities_in_state,
    build_code_topology_graph_impl,
    build_context_pack_impl,
    get_code_topology_entity_detail_impl,
    index_status_impl,
    search_entities_impl,
)
from viberecall_mcp.code_index_shared import (
    _JS_CLASS_RE,
    _JS_FUNCTION_RE,
    _JS_IMPORT_FROM_RE,
    _JS_REQUIRE_RE,
    _JS_VAR_FUNC_RE,
    _MAX_SNIPPET_BYTES,
    _MAX_SNIPPET_LINES,
    _MAX_TOKENS_PER_CHUNK,
    _SKIP_DIRS,
    _SUPPORTED_EXTENSIONS,
    _TOKEN_RE,
    _entity_row,
    _entity_search_text,
    _file_entity_id,
    _import_entity_id,
    _iso_or_none,
    _module_entity_id,
    _now_iso,
    _pg_text_array,
    _stats_payload,
    _symbol_entity_id,
    _tokenize,
    _trim_snippet,
    settings,
)
from viberecall_mcp.code_index_sources import (
    _INTERNAL_FULL_SNAPSHOT_MODE,
    _authenticated_git_remote_url,
    _git_credential_config,
    _is_zip_symlink,
    _materialize_git_repo,
    _materialize_repo_source,
    _normalize_bundle_ref,
    _normalize_full_snapshot_mode,
    _repo_source_payload,
    _resolve_repo_path,
    _run_git_command,
    _safe_extract_bundle,
    normalize_repo_source,
    validate_workspace_bundle_archive,
)
from viberecall_mcp.code_index_store import (
    _chunk_candidate_rows,
    _chunk_rows_for_entity_ids,
    _clone_index_rows,
    _current_run_payload,
    _delete_previous_ready_children,
    _entity_candidate_rows,
    _entity_rows_for_file_paths,
    _file_rows_for_index,
    _get_active_index_run,
    _get_index_run,
    _get_latest_index_run,
    _get_latest_ready_index_run,
    _get_project_index_run,
    _insert_index_run,
    _latest_ready_payload,
    _load_index_file_rows,
    _mark_index_run_failed,
    _mark_index_run_ready,
    _mark_index_run_running,
    _purge_index_rows,
    _set_index_run_job_id,
    _store_materialized_snapshot,
    _update_index_run_progress,
)
from viberecall_mcp.db import open_db_session
from viberecall_mcp.repositories.operations import complete_operation, fail_operation, mark_operation_running


async def request_index_repo(
    *,
    session: AsyncSession,
    project_id: str,
    repo_source: dict[str, Any],
    mode: str,
    max_files: int,
    requested_by_token_id: str | None,
    commit: bool = True,
) -> dict[str, Any]:
    return await request_index_repo_impl(
        session=session,
        project_id=project_id,
        repo_source=repo_source,
        mode=mode,
        max_files=max_files,
        requested_by_token_id=requested_by_token_id,
        commit=commit,
    )


async def attach_index_job_id(
    *,
    session: AsyncSession,
    index_id: str,
    job_id: str,
    commit: bool = True,
) -> None:
    await attach_index_job_id_impl(session=session, index_id=index_id, job_id=job_id, commit=commit)


async def mark_index_request_failed(
    *,
    session: AsyncSession,
    index_id: str,
    error: str,
    commit: bool = True,
) -> None:
    await mark_index_request_failed_impl(session=session, index_id=index_id, error=error, commit=commit)


async def index_status(
    *,
    session: AsyncSession,
    project_id: str,
    index_run_id: str | None = None,
) -> dict[str, Any]:
    return await index_status_impl(session=session, project_id=project_id, index_run_id=index_run_id)


async def search_entities(
    *,
    session: AsyncSession,
    project_id: str,
    query: str,
    entity_types: list[str] | None,
    limit: int,
) -> dict[str, Any]:
    return await search_entities_impl(
        session=session,
        project_id=project_id,
        query=query,
        entity_types=entity_types,
        limit=limit,
    )


async def build_context_pack(
    *,
    session: AsyncSession,
    project_id: str,
    query: str,
    limit: int,
) -> dict[str, Any]:
    return await build_context_pack_impl(session=session, project_id=project_id, query=query, limit=limit)


async def build_code_topology_graph(
    *,
    session: AsyncSession,
    project_id: str,
    query: str | None,
    max_nodes: int,
    max_edges: int,
) -> dict[str, Any]:
    return await build_code_topology_graph_impl(
        session=session,
        project_id=project_id,
        query=query,
        max_nodes=max_nodes,
        max_edges=max_edges,
    )


async def get_code_topology_entity_detail(
    *,
    session: AsyncSession,
    project_id: str,
    entity_id: str,
) -> dict[str, Any]:
    return await get_code_topology_entity_detail_impl(
        session=session,
        project_id=project_id,
        entity_id=entity_id,
    )


async def run_index_job(
    *,
    index_id: str,
    operation_id: str | None = None,
) -> dict[str, Any]:
    return await run_index_job_impl(
        index_id=index_id,
        operation_id=operation_id,
        open_db_session_ctx=open_db_session,
        get_index_run_fn=_get_index_run,
        mark_operation_running_fn=mark_operation_running,
        mark_index_run_running_fn=_mark_index_run_running,
        get_latest_ready_index_run_fn=_get_latest_ready_index_run,
        materialize_repo_source_ctx=_materialize_repo_source,
        iter_candidate_files_fn=_iter_candidate_files,
        git_changed_files_fn=_git_changed_files,
        filter_supported_rel_paths_fn=_filter_supported_rel_paths,
        update_index_run_progress_fn=_update_index_run_progress,
        build_file_rows_fn=_build_file_rows,
        mark_index_run_failed_fn=_mark_index_run_failed,
        load_index_file_rows_fn=_load_index_file_rows,
        materialize_index_fn=_materialize_index,
        store_materialized_snapshot_fn=_store_materialized_snapshot,
        mark_index_run_ready_fn=_mark_index_run_ready,
        delete_previous_ready_children_fn=_delete_previous_ready_children,
        complete_operation_fn=complete_operation,
        fail_operation_fn=fail_operation,
        clone_index_rows_fn=_clone_index_rows,
        stats_payload_fn=_stats_payload,
        now_iso_fn=_now_iso,
    )
