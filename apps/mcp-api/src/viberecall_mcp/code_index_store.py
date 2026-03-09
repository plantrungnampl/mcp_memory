from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.code_index_shared import _iso_or_none, _pg_text_array, _stats_payload, _tokenize
from viberecall_mcp.code_index_sources import _repo_source_payload


def _current_run_payload(row: dict | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "index_run_id": row["index_id"],
        "job_id": row.get("job_id"),
        "repo_source": _repo_source_payload(row),
        "mode": "FULL_SNAPSHOT",
        "effective_mode": "FULL_SNAPSHOT" if row.get("effective_mode") else None,
        "phase": row.get("phase"),
        "processed_files": int(row.get("processed_files") or 0),
        "total_files": int(row.get("total_files") or 0),
        "scanned_files": int(row.get("scanned_files") or 0),
        "changed_files": int(row.get("changed_files") or 0),
        "queued_at": _iso_or_none(row.get("created_at")),
        "started_at": _iso_or_none(row.get("started_at")),
        "completed_at": _iso_or_none(row.get("completed_at")),
        "error": row.get("error"),
        "stats": _stats_payload(row),
    }


def _latest_ready_payload(row: dict | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "index_run_id": row["index_id"],
        "repo_source": _repo_source_payload(row),
        "indexed_at": _iso_or_none(row.get("completed_at")),
        "mode": "FULL_SNAPSHOT",
        "effective_mode": "FULL_SNAPSHOT" if row.get("effective_mode") else None,
        "stats": _stats_payload(row),
        "top_modules": list(row.get("top_modules_json") or []),
        "top_files": list(row.get("top_files_json") or []),
    }


async def _get_index_run(session: AsyncSession, *, index_id: str) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, repo_source_type, repo_source_ref,
                   source_ref_value, repo_name, base_commit, credential_ref, mode, effective_mode, status, phase,
                   processed_files, total_files, scanned_files, changed_files,
                   file_count, symbol_count, entity_count, relationship_count, chunk_count,
                   top_modules_json, top_files_json, error,
                   created_at, started_at, completed_at, base_ref, head_ref, max_files, requested_by_token_id
            from code_index_runs
            where index_id = :index_id
            """
        ),
        {"index_id": index_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _get_project_index_run(session: AsyncSession, *, project_id: str, index_id: str) -> dict[str, Any] | None:
    row = await _get_index_run(session, index_id=index_id)
    if row is None or str(row.get("project_id")) != project_id:
        return None
    return row


async def _get_active_index_run(session: AsyncSession, *, project_id: str) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, repo_source_type, repo_source_ref,
                   source_ref_value, repo_name, base_commit, credential_ref, mode, effective_mode, status, phase,
                   processed_files, total_files, scanned_files, changed_files,
                   file_count, symbol_count, entity_count, relationship_count, chunk_count,
                   top_modules_json, top_files_json, error,
                   created_at, started_at, completed_at
            from code_index_runs
            where project_id = :project_id
              and status in ('QUEUED', 'RUNNING')
            order by created_at desc, index_id desc
            limit 1
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _get_latest_index_run(session: AsyncSession, *, project_id: str) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, repo_source_type, repo_source_ref,
                   source_ref_value, repo_name, base_commit, credential_ref, mode, effective_mode, status, phase,
                   processed_files, total_files, scanned_files, changed_files,
                   file_count, symbol_count, entity_count, relationship_count, chunk_count,
                   top_modules_json, top_files_json, error,
                   created_at, started_at, completed_at
            from code_index_runs
            where project_id = :project_id
            order by created_at desc, index_id desc
            limit 1
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _get_latest_ready_index_run(session: AsyncSession, *, project_id: str) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, repo_source_type, repo_source_ref,
                   source_ref_value, repo_name, base_commit, credential_ref, mode, effective_mode, status, phase,
                   processed_files, total_files, scanned_files, changed_files,
                   file_count, symbol_count, entity_count, relationship_count, chunk_count,
                   top_modules_json, top_files_json, error,
                   created_at, started_at, completed_at
            from code_index_runs
            where project_id = :project_id
              and status = 'READY'
            order by completed_at desc nulls last, created_at desc, index_id desc
            limit 1
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _insert_index_run(
    session: AsyncSession,
    *,
    index_id: str,
    project_id: str,
    repo_path: str,
    repo_source_type: str,
    repo_source_ref: str,
    source_ref_value: str | None,
    repo_name: str | None,
    base_commit: str | None,
    credential_ref: str | None,
    mode: str,
    base_ref: str | None,
    head_ref: str | None,
    max_files: int,
    requested_by_token_id: str | None,
) -> None:
    await session.execute(
        text(
            """
            insert into code_index_runs (
                index_id, project_id, repo_path, repo_source_type, repo_source_ref,
                source_ref_value, repo_name, base_commit, credential_ref,
                mode, base_ref, head_ref, max_files, status, phase, requested_by_token_id
            ) values (
                :index_id, :project_id, :repo_path, :repo_source_type, :repo_source_ref,
                :source_ref_value, :repo_name, :base_commit, :credential_ref,
                :mode, :base_ref, :head_ref, :max_files, 'QUEUED', 'queued', :requested_by_token_id
            )
            """
        ),
        {
            "index_id": index_id,
            "project_id": project_id,
            "repo_path": repo_path,
            "repo_source_type": repo_source_type,
            "repo_source_ref": repo_source_ref,
            "source_ref_value": source_ref_value,
            "repo_name": repo_name,
            "base_commit": base_commit,
            "credential_ref": credential_ref,
            "mode": mode,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "max_files": max_files,
            "requested_by_token_id": requested_by_token_id,
        },
    )


async def _set_index_run_job_id(session: AsyncSession, *, index_id: str, job_id: str) -> None:
    await session.execute(
        text(
            """
            update code_index_runs
            set job_id = :job_id
            where index_id = :index_id
            """
        ),
        {"index_id": index_id, "job_id": job_id},
    )


async def _mark_index_run_running(
    session: AsyncSession,
    *,
    index_id: str,
    phase: str,
    effective_mode: str,
) -> None:
    await session.execute(
        text(
            """
            update code_index_runs
            set status = 'RUNNING',
                phase = :phase,
                effective_mode = :effective_mode,
                started_at = coalesce(started_at, now()),
                error = null
            where index_id = :index_id
            """
        ),
        {"index_id": index_id, "phase": phase, "effective_mode": effective_mode},
    )


async def _update_index_run_progress(
    session: AsyncSession,
    *,
    index_id: str,
    phase: str,
    processed_files: int,
    total_files: int,
    scanned_files: int,
    changed_files: int,
) -> None:
    await session.execute(
        text(
            """
            update code_index_runs
            set phase = :phase,
                processed_files = :processed_files,
                total_files = :total_files,
                scanned_files = :scanned_files,
                changed_files = :changed_files
            where index_id = :index_id
            """
        ),
        {
            "index_id": index_id,
            "phase": phase,
            "processed_files": processed_files,
            "total_files": total_files,
            "scanned_files": scanned_files,
            "changed_files": changed_files,
        },
    )


async def _mark_index_run_ready(
    session: AsyncSession,
    *,
    index_id: str,
    effective_mode: str,
    scanned_files: int,
    changed_files: int,
    processed_files: int,
    stats: dict[str, Any],
    top_modules: list[dict[str, Any]],
    top_files: list[dict[str, Any]],
) -> None:
    await session.execute(
        text(
            """
            update code_index_runs
            set status = 'READY',
                phase = 'ready',
                effective_mode = :effective_mode,
                processed_files = :processed_files,
                total_files = :processed_files,
                scanned_files = :scanned_files,
                changed_files = :changed_files,
                file_count = :file_count,
                symbol_count = :symbol_count,
                entity_count = :entity_count,
                relationship_count = :relationship_count,
                chunk_count = :chunk_count,
                top_modules_json = cast(:top_modules_json as jsonb),
                top_files_json = cast(:top_files_json as jsonb),
                error = null,
                completed_at = now()
            where index_id = :index_id
            """
        ),
        {
            "index_id": index_id,
            "effective_mode": effective_mode,
            "processed_files": processed_files,
            "scanned_files": scanned_files,
            "changed_files": changed_files,
            "file_count": int(stats.get("file_count", 0) or 0),
            "symbol_count": int(stats.get("symbol_count", 0) or 0),
            "entity_count": int(stats.get("entity_count", 0) or 0),
            "relationship_count": int(stats.get("relationship_count", 0) or 0),
            "chunk_count": int(stats.get("chunk_count", 0) or 0),
            "top_modules_json": json.dumps(top_modules, ensure_ascii=True),
            "top_files_json": json.dumps(top_files, ensure_ascii=True),
        },
    )


async def _purge_index_rows(session: AsyncSession, *, index_id: str) -> None:
    await session.execute(text("delete from code_index_chunks where index_id = :index_id"), {"index_id": index_id})
    await session.execute(text("delete from code_index_entities where index_id = :index_id"), {"index_id": index_id})
    await session.execute(text("delete from code_index_files where index_id = :index_id"), {"index_id": index_id})


async def _mark_index_run_failed(session: AsyncSession, *, index_id: str, error: str) -> None:
    await _purge_index_rows(session, index_id=index_id)
    await session.execute(
        text(
            """
            update code_index_runs
            set status = 'FAILED',
                phase = 'failed',
                error = :error,
                completed_at = now()
            where index_id = :index_id
            """
        ),
        {"index_id": index_id, "error": error[:2000]},
    )


async def _load_index_file_rows(session: AsyncSession, *, index_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            select row_json
            from code_index_files
            where index_id = :index_id
            order by file_path asc
            """
        ),
        {"index_id": index_id},
    )
    rows = []
    for mapping in result.mappings().all():
        row_json = mapping["row_json"]
        rows.append(dict(row_json) if isinstance(row_json, dict) else json.loads(row_json))
    return rows


async def _clone_index_rows(session: AsyncSession, *, source_index_id: str, target_index_id: str) -> None:
    await session.execute(
        text(
            """
            insert into code_index_files (index_id, file_path, language, module_name, sha1, row_json)
            select :target_index_id, file_path, language, module_name, sha1, row_json
            from code_index_files
            where index_id = :source_index_id
            """
        ),
        {"source_index_id": source_index_id, "target_index_id": target_index_id},
    )
    await session.execute(
        text(
            """
            insert into code_index_entities (
                index_id, entity_id, entity_type, name, file_path, language,
                kind, line_start, line_end, search_text, search_tokens
            )
            select :target_index_id, entity_id, entity_type, name, file_path, language,
                   kind, line_start, line_end, search_text, search_tokens
            from code_index_entities
            where index_id = :source_index_id
            """
        ),
        {"source_index_id": source_index_id, "target_index_id": target_index_id},
    )
    await session.execute(
        text(
            """
            insert into code_index_chunks (
                index_id, chunk_id, entity_id, file_path, language,
                line_start, line_end, snippet, tokens
            )
            select :target_index_id, chunk_id, entity_id, file_path, language,
                   line_start, line_end, snippet, tokens
            from code_index_chunks
            where index_id = :source_index_id
            """
        ),
        {"source_index_id": source_index_id, "target_index_id": target_index_id},
    )


async def _delete_previous_ready_children(
    session: AsyncSession,
    *,
    project_id: str,
    keep_index_id: str,
) -> None:
    result = await session.execute(
        text(
            """
            select index_id
            from code_index_runs
            where project_id = :project_id
              and status = 'READY'
              and index_id <> :keep_index_id
            """
        ),
        {"project_id": project_id, "keep_index_id": keep_index_id},
    )
    stale_ids = [str(row["index_id"]) for row in result.mappings().all()]
    if not stale_ids:
        return
    await session.execute(
        text("delete from code_index_chunks where index_id = any(cast(:index_ids as text[]))"),
        {"index_ids": _pg_text_array(stale_ids)},
    )
    await session.execute(
        text("delete from code_index_entities where index_id = any(cast(:index_ids as text[]))"),
        {"index_ids": _pg_text_array(stale_ids)},
    )
    await session.execute(
        text("delete from code_index_files where index_id = any(cast(:index_ids as text[]))"),
        {"index_ids": _pg_text_array(stale_ids)},
    )


async def _store_materialized_snapshot(
    session: AsyncSession,
    *,
    index_id: str,
    file_rows: list[dict[str, Any]],
    materialized: dict[str, Any],
) -> None:
    await _purge_index_rows(session, index_id=index_id)

    if file_rows:
        await session.execute(
            text(
                """
                insert into code_index_files (
                    index_id, file_path, language, module_name, sha1, row_json
                ) values (
                    :index_id, :file_path, :language, :module_name, :sha1, cast(:row_json as jsonb)
                )
                """
            ),
            [
                {
                    "index_id": index_id,
                    "file_path": str(row["path"]),
                    "language": str(row["language"]),
                    "module_name": str(row["module"]),
                    "sha1": str(row["sha1"]),
                    "row_json": json.dumps(row, ensure_ascii=True),
                }
                for row in file_rows
            ],
        )

    entities = materialized.get("entities") or []
    if entities:
        await session.execute(
            text(
                """
                insert into code_index_entities (
                    index_id, entity_id, entity_type, name, file_path, language,
                    kind, line_start, line_end, search_text, search_tokens
                ) values (
                    :index_id, :entity_id, :entity_type, :name, :file_path, :language,
                    :kind, :line_start, :line_end, :search_text, cast(:search_tokens as text[])
                )
                """
            ),
            [
                {
                    "index_id": index_id,
                    "entity_id": str(entity["entity_id"]),
                    "entity_type": str(entity["type"]),
                    "name": str(entity["name"]),
                    "file_path": entity.get("file_path"),
                    "language": entity.get("language"),
                    "kind": entity.get("kind"),
                    "line_start": entity.get("line_start"),
                    "line_end": entity.get("line_end"),
                    "search_text": str(entity.get("search_text") or ""),
                    "search_tokens": _pg_text_array([str(item) for item in (entity.get("search_tokens") or [])]),
                }
                for entity in entities
            ],
        )

    chunks = materialized.get("chunks") or []
    if chunks:
        await session.execute(
            text(
                """
                insert into code_index_chunks (
                    index_id, chunk_id, entity_id, file_path, language,
                    line_start, line_end, snippet, tokens
                ) values (
                    :index_id, :chunk_id, :entity_id, :file_path, :language,
                    :line_start, :line_end, :snippet, cast(:tokens as text[])
                )
                """
            ),
            [
                {
                    "index_id": index_id,
                    "chunk_id": str(chunk["chunk_id"]),
                    "entity_id": str(chunk["entity_id"]),
                    "file_path": chunk.get("file_path"),
                    "language": chunk.get("language"),
                    "line_start": chunk.get("line_start"),
                    "line_end": chunk.get("line_end"),
                    "snippet": chunk.get("snippet"),
                    "tokens": _pg_text_array([str(item) for item in (chunk.get("tokens") or [])]),
                }
                for chunk in chunks
            ],
        )


async def _entity_candidate_rows(
    session: AsyncSession,
    *,
    index_id: str,
    query_lower: str,
    entity_types: list[str] | None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"index_id": index_id}
    where = ["index_id = :index_id"]
    filtered_types = [item.strip() for item in (entity_types or []) if item.strip()]
    if filtered_types:
        params["entity_types"] = _pg_text_array(filtered_types)
        where.append("entity_type = any(cast(:entity_types as text[]))")
    if query_lower:
        query_tokens = sorted(set(_tokenize(query_lower)))
        params["query_lower"] = query_lower
        if query_tokens:
            params["query_tokens"] = _pg_text_array(query_tokens)
            where.append(
                "(position(:query_lower in search_text) > 0 or search_tokens && cast(:query_tokens as text[]))"
            )
        else:
            where.append("position(:query_lower in search_text) > 0")
    result = await session.execute(
        text(
            f"""
            select entity_id, entity_type, name, file_path, language, kind, line_start, line_end,
                   search_text, search_tokens
            from code_index_entities
            where {' and '.join(where)}
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


async def _chunk_candidate_rows(
    session: AsyncSession,
    *,
    index_id: str,
    query_tokens: set[str],
    boosted_entity_ids: set[str],
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"index_id": index_id}
    candidate_filters: list[str] = []
    if query_tokens:
        params["query_tokens"] = _pg_text_array(sorted(query_tokens))
        candidate_filters.append("tokens && cast(:query_tokens as text[])")
    if boosted_entity_ids:
        params["boosted_entity_ids"] = _pg_text_array(sorted(boosted_entity_ids))
        candidate_filters.append("entity_id = any(cast(:boosted_entity_ids as text[]))")
    if not candidate_filters:
        return []
    result = await session.execute(
        text(
            f"""
            select chunk_id, entity_id, file_path, language, line_start, line_end, snippet, tokens
            from code_index_chunks
            where index_id = :index_id
              and ({' or '.join(candidate_filters)})
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


async def _file_rows_for_index(session: AsyncSession, *, index_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            select file_path, module_name, row_json
            from code_index_files
            where index_id = :index_id
            order by file_path asc
            """
        ),
        {"index_id": index_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def _entity_rows_for_file_paths(
    session: AsyncSession,
    *,
    index_id: str,
    file_paths: list[str],
    entity_type: str,
) -> list[dict[str, Any]]:
    if not file_paths:
        return []
    result = await session.execute(
        text(
            """
            select entity_id, entity_type, name, file_path, language, kind, line_start, line_end
            from code_index_entities
            where index_id = :index_id
              and entity_type = :entity_type
              and file_path = any(cast(:file_paths as text[]))
            order by file_path asc, line_start asc nulls last, name asc
            """
        ),
        {
            "index_id": index_id,
            "entity_type": entity_type,
            "file_paths": _pg_text_array(file_paths),
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def _chunk_rows_for_entity_ids(
    session: AsyncSession,
    *,
    index_id: str,
    entity_ids: list[str],
) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    result = await session.execute(
        text(
            """
            select chunk_id, entity_id, file_path, language, line_start, line_end, snippet
            from code_index_chunks
            where index_id = :index_id
              and entity_id = any(cast(:entity_ids as text[]))
            order by file_path asc, line_start asc nulls last, chunk_id asc
            """
        ),
        {
            "index_id": index_id,
            "entity_ids": _pg_text_array(entity_ids),
        },
    )
    return [dict(row) for row in result.mappings().all()]
