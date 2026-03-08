from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.config import get_settings
from viberecall_mcp.db import open_db_session
from viberecall_mcp.ids import new_id


_SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}

_SKIP_DIRS = {
    ".git",
    ".viberecall",
    "node_modules",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "coverage",
}

_MAX_SNIPPET_LINES = 30
_MAX_SNIPPET_BYTES = 4096
_MAX_TOKENS_PER_CHUNK = 256

_JS_FUNCTION_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)")
_JS_CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_]\w*)")
_JS_VAR_FUNC_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_]\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_]\w*)\s*=>"
)
_JS_IMPORT_FROM_RE = re.compile(r"""from\s+['"]([^'"]+)['"]""")
_JS_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")
settings = get_settings()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _language_for_path(path: Path) -> str | None:
    return _SUPPORTED_EXTENSIONS.get(path.suffix.lower())


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def _trim_snippet(text: str) -> str:
    lines = text.splitlines()
    if len(lines) > _MAX_SNIPPET_LINES:
        text = "\n".join(lines[:_MAX_SNIPPET_LINES])
    raw = text.encode("utf-8", errors="ignore")
    if len(raw) <= _MAX_SNIPPET_BYTES:
        return text
    return raw[:_MAX_SNIPPET_BYTES].decode("utf-8", errors="ignore")


def _extract_snippet(lines: list[str], line_start: int, line_end: int) -> str:
    start = max(1, line_start)
    end = max(start, line_end)
    snippet = "\n".join(lines[start - 1 : end])
    return _trim_snippet(snippet)


def _module_name_for_file(rel_path: str) -> str:
    parts = [part for part in Path(rel_path).parts if part not in {"."}]
    if not parts:
        return "root"
    if len(parts) == 1:
        return "root"
    return parts[0]


def _iter_candidate_files(repo_path: Path, max_files: int) -> list[Path]:
    files: list[Path] = []
    for root, dir_names, file_names in repo_path.walk(top_down=True):
        dir_names[:] = [name for name in dir_names if name not in _SKIP_DIRS]
        for file_name in file_names:
            path = root / file_name
            if _language_for_path(path) is None:
                continue
            files.append(path)
            if len(files) >= max_files:
                return files
    return files


def _git_changed_files(repo_path: Path, base_ref: str, head_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "diff", "--name-only", f"{base_ref}..{head_ref}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "git diff failed").strip()
        raise RuntimeError(detail)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _python_symbols_and_imports(content: str) -> tuple[list[dict], list[str]]:
    symbols: list[dict] = []
    imports: set[str] = set()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return symbols, list(imports)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            symbols.append(
                {
                    "name": node.name,
                    "kind": "function",
                    "line_start": int(getattr(node, "lineno", 1)),
                    "line_end": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
                }
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append(
                {
                    "name": node.name,
                    "kind": "class",
                    "line_start": int(getattr(node, "lineno", 1)),
                    "line_end": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
                }
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return symbols, sorted(imports)


def _js_ts_symbols_and_imports(content: str) -> tuple[list[dict], list[str]]:
    symbols: list[dict] = []
    imports: set[str] = set()
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for regex, kind in (
            (_JS_FUNCTION_RE, "function"),
            (_JS_CLASS_RE, "class"),
            (_JS_VAR_FUNC_RE, "function"),
        ):
            match = regex.match(line)
            if match:
                symbols.append(
                    {
                        "name": match.group(1),
                        "kind": kind,
                        "line_start": idx,
                        "line_end": min(len(lines), idx + 12),
                    }
                )
                break
        for import_match in _JS_IMPORT_FROM_RE.finditer(line):
            imports.add(import_match.group(1))
        for require_match in _JS_REQUIRE_RE.finditer(line):
            imports.add(require_match.group(1))
    return symbols, sorted(imports)


def _extract_file_row(repo_path: Path, file_path: Path) -> dict:
    rel_path = str(file_path.relative_to(repo_path))
    language = _language_for_path(file_path)
    if language is None:
        raise ValueError(f"Unsupported file extension for {rel_path}")

    content = _read_text(file_path)
    content_hash = _sha1(content)
    lines = content.splitlines()
    if language == "python":
        symbols, imports = _python_symbols_and_imports(content)
    else:
        symbols, imports = _js_ts_symbols_and_imports(content)

    symbol_rows: list[dict] = []
    for symbol in symbols:
        line_start = int(symbol["line_start"])
        line_end = int(symbol["line_end"])
        snippet = _extract_snippet(lines, line_start, line_end)
        symbol_rows.append(
            {
                "name": str(symbol["name"]),
                "kind": str(symbol["kind"]),
                "line_start": line_start,
                "line_end": line_end,
                "snippet": snippet,
                "tokens": _tokenize(f"{symbol['name']} {snippet}")[:_MAX_TOKENS_PER_CHUNK],
            }
        )

    return {
        "path": rel_path,
        "language": language,
        "module": _module_name_for_file(rel_path),
        "sha1": content_hash,
        "symbols": symbol_rows,
        "imports": imports,
        "snippet": _trim_snippet("\n".join(lines[:40])),
        "tokens": _tokenize(content)[:_MAX_TOKENS_PER_CHUNK],
    }


def _file_entity_id(path: str) -> str:
    return f"file:{path}"


def _module_entity_id(module: str) -> str:
    return f"module:{module}"


def _symbol_entity_id(file_path: str, symbol_name: str, line_start: int) -> str:
    return f"symbol:{file_path}:{symbol_name}:{line_start}"


def _import_entity_id(module_name: str) -> str:
    return f"import:{module_name}"


def _entity_search_text(
    *,
    entity_id: str,
    entity_type: str,
    name: str,
    file_path: str | None,
    kind: str | None,
) -> str:
    return " ".join(
        [
            entity_id,
            entity_type,
            name,
            file_path or "",
            kind or "",
        ]
    ).lower()


def _entity_row(
    *,
    entity_id: str,
    entity_type: str,
    name: str,
    file_path: str | None,
    language: str | None,
    kind: str | None,
    line_start: int | None = None,
    line_end: int | None = None,
) -> dict[str, Any]:
    search_text = _entity_search_text(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        file_path=file_path,
        kind=kind,
    )
    row: dict[str, Any] = {
        "entity_id": entity_id,
        "type": entity_type,
        "name": name,
        "file_path": file_path,
        "language": language,
        "kind": kind,
        "search_text": search_text,
        "search_tokens": sorted(set(_tokenize(search_text))),
    }
    if line_start is not None:
        row["line_start"] = line_start
    if line_end is not None:
        row["line_end"] = line_end
    return row


def _materialize_index(
    *,
    project_id: str,
    repo_path: Path,
    indexed_at: str,
    mode: str,
    source: str,
    file_rows: list[dict],
) -> dict:
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    relationship_seen: set[tuple[str, str, str]] = set()

    module_to_files: dict[str, int] = {}
    file_to_symbol_count: dict[str, int] = {}
    module_to_symbol_count: dict[str, int] = {}
    file_entities: set[str] = set()
    module_entities: set[str] = set()
    import_entities: set[str] = set()

    for file_row in file_rows:
        file_path = str(file_row["path"])
        language = str(file_row["language"])
        module_name = str(file_row["module"])
        file_id = _file_entity_id(file_path)
        module_id = _module_entity_id(module_name)

        if module_id not in module_entities:
            entities.append(
                _entity_row(
                    entity_id=module_id,
                    entity_type="Module",
                    name=module_name,
                    file_path=None,
                    language=None,
                    kind=None,
                )
            )
            module_entities.add(module_id)
        if file_id not in file_entities:
            entities.append(
                _entity_row(
                    entity_id=file_id,
                    entity_type="File",
                    name=file_path,
                    file_path=file_path,
                    language=language,
                    kind=None,
                )
            )
            file_entities.add(file_id)

        rel_key = ("CONTAINS", module_id, file_id)
        if rel_key not in relationship_seen:
            relationships.append(
                {"type": "CONTAINS", "source_id": module_id, "target_id": file_id, "weight": 1}
            )
            relationship_seen.add(rel_key)

        module_to_files[module_name] = module_to_files.get(module_name, 0) + 1
        file_to_symbol_count[file_path] = 0
        module_to_symbol_count.setdefault(module_name, 0)

        for import_name in file_row.get("imports") or []:
            import_id = _import_entity_id(str(import_name))
            if import_id not in import_entities:
                entities.append(
                    _entity_row(
                        entity_id=import_id,
                        entity_type="Import",
                        name=str(import_name),
                        file_path=None,
                        language=None,
                        kind=None,
                    )
                )
                import_entities.add(import_id)
            rel_key = ("IMPORTS", file_id, import_id)
            if rel_key not in relationship_seen:
                relationships.append(
                    {"type": "IMPORTS", "source_id": file_id, "target_id": import_id, "weight": 1}
                )
                relationship_seen.add(rel_key)

        for symbol in file_row.get("symbols") or []:
            symbol_name = str(symbol["name"])
            line_start = int(symbol["line_start"])
            line_end = int(symbol["line_end"])
            symbol_id = _symbol_entity_id(file_path, symbol_name, line_start)
            entities.append(
                _entity_row(
                    entity_id=symbol_id,
                    entity_type="Symbol",
                    name=symbol_name,
                    file_path=file_path,
                    language=language,
                    kind=str(symbol["kind"]),
                    line_start=line_start,
                    line_end=line_end,
                )
            )
            rel_key = ("CONTAINS", file_id, symbol_id)
            if rel_key not in relationship_seen:
                relationships.append(
                    {"type": "CONTAINS", "source_id": file_id, "target_id": symbol_id, "weight": 1}
                )
                relationship_seen.add(rel_key)

            chunk_id = f"chunk:{symbol_id}"
            snippet = str(symbol.get("snippet") or "")
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "entity_id": symbol_id,
                    "file_path": file_path,
                    "language": language,
                    "line_start": line_start,
                    "line_end": line_end,
                    "snippet": snippet,
                    "tokens": list(symbol.get("tokens") or []),
                }
            )
            file_to_symbol_count[file_path] += 1
            module_to_symbol_count[module_name] = module_to_symbol_count.get(module_name, 0) + 1

        # File-level chunk for architecture/context retrieval.
        chunks.append(
            {
                "chunk_id": f"chunk:file:{file_path}",
                "entity_id": file_id,
                "file_path": file_path,
                "language": language,
                "line_start": 1,
                "line_end": min(40, len(str(file_row.get("snippet") or "").splitlines()) or 1),
                "snippet": str(file_row.get("snippet") or ""),
                "tokens": list(file_row.get("tokens") or []),
            }
        )

    file_rows_sorted = sorted(file_rows, key=lambda row: str(row["path"]))
    top_modules = sorted(
        (
            {
                "module": module,
                "file_count": module_to_files.get(module, 0),
                "symbol_count": module_to_symbol_count.get(module, 0),
            }
            for module in module_to_files
        ),
        key=lambda item: (item["symbol_count"], item["file_count"], item["module"]),
        reverse=True,
    )[:12]
    top_files = sorted(
        (
            {
                "file_path": file_path,
                "symbol_count": file_to_symbol_count.get(file_path, 0),
            }
            for file_path in file_to_symbol_count
        ),
        key=lambda item: (item["symbol_count"], item["file_path"]),
        reverse=True,
    )[:20]

    return {
        "project_id": project_id,
        "repo_path": str(repo_path),
        "indexed_at": indexed_at,
        "mode": mode,
        "stats": {
            "file_count": len(file_rows_sorted),
            "symbol_count": sum(int(row["symbol_count"]) for row in top_files)
            if top_files
            else sum(len(row.get("symbols") or []) for row in file_rows_sorted),
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "chunk_count": len(chunks),
        },
        "architecture": {
            "top_modules": top_modules,
            "top_files": top_files,
        },
        "files": file_rows_sorted,
        "entities": entities,
        "relationships": relationships,
        "chunks": chunks,
    }

def _resolve_repo_path(repo_path: str) -> Path:
    path = Path(repo_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Repository path does not exist: {repo_path}")
    allowed_roots = settings.resolved_index_repo_allowed_roots()
    if not any(path == root or root in path.parents for root in allowed_roots):
        raise ValueError("Repository path is not within INDEX_REPO_ALLOWED_ROOTS")
    return path


def _filter_supported_rel_paths(repo_path: Path, rel_paths: list[str]) -> list[Path]:
    result: list[Path] = []
    for rel_path in rel_paths:
        path = (repo_path / rel_path).resolve()
        if not str(path).startswith(str(repo_path)):
            continue
        if not path.exists() or not path.is_file():
            continue
        if _language_for_path(path) is None:
            continue
        result.append(path)
    return result


def _build_file_rows(repo_path: Path, file_paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in file_paths:
        try:
            rows.append(_extract_file_row(repo_path, path))
        except (OSError, ValueError):
            continue
    return rows


def _pg_text_array(values: list[str]) -> list[str]:
    return [str(value) for value in values]


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _stats_payload(row: dict | None) -> dict[str, int]:
    source = row or {}
    return {
        "file_count": int(source.get("file_count") or 0),
        "symbol_count": int(source.get("symbol_count") or 0),
        "entity_count": int(source.get("entity_count") or 0),
        "relationship_count": int(source.get("relationship_count") or 0),
        "chunk_count": int(source.get("chunk_count") or 0),
    }


def _current_run_payload(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        "index_id": row["index_id"],
        "job_id": row.get("job_id"),
        "repo_path": row.get("repo_path"),
        "mode": row.get("mode"),
        "effective_mode": row.get("effective_mode"),
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


def _latest_ready_payload(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        "index_id": row["index_id"],
        "repo_path": row.get("repo_path"),
        "indexed_at": _iso_or_none(row.get("completed_at")),
        "mode": row.get("mode"),
        "effective_mode": row.get("effective_mode"),
        "stats": _stats_payload(row),
        "top_modules": list(row.get("top_modules_json") or []),
        "top_files": list(row.get("top_files_json") or []),
    }


async def _get_index_run(session: AsyncSession, *, index_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, mode, effective_mode, status, phase,
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


async def _get_active_index_run(session: AsyncSession, *, project_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, mode, effective_mode, status, phase,
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


async def _get_latest_index_run(session: AsyncSession, *, project_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, mode, effective_mode, status, phase,
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


async def _get_latest_ready_index_run(session: AsyncSession, *, project_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select index_id, project_id, job_id, repo_path, mode, effective_mode, status, phase,
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
                index_id, project_id, repo_path, mode, base_ref, head_ref,
                max_files, status, phase, requested_by_token_id
            ) values (
                :index_id, :project_id, :repo_path, :mode, :base_ref, :head_ref,
                :max_files, 'QUEUED', 'queued', :requested_by_token_id
            )
            """
        ),
        {
            "index_id": index_id,
            "project_id": project_id,
            "repo_path": repo_path,
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


async def request_index_repo(
    *,
    session: AsyncSession,
    project_id: str,
    repo_path: str,
    mode: str,
    base_ref: str | None,
    head_ref: str | None,
    max_files: int,
    requested_by_token_id: str | None,
) -> dict:
    repo_root = _resolve_repo_path(repo_path)
    if mode == "diff" and (not base_ref or not head_ref):
        raise ValueError("diff mode requires both base_ref and head_ref")

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
        mode=mode,
        base_ref=base_ref,
        head_ref=head_ref,
        max_files=max_files,
        requested_by_token_id=requested_by_token_id,
    )
    await session.commit()
    return {
        "index_id": index_id,
        "project_id": project_id,
        "repo_path": str(repo_root),
        "mode": mode,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "max_files": max_files,
        "queued_at": _now_iso(),
    }


async def attach_index_job_id(
    *,
    session: AsyncSession,
    index_id: str,
    job_id: str,
) -> None:
    await _set_index_run_job_id(session, index_id=index_id, job_id=job_id)
    await session.commit()


async def mark_index_request_failed(
    *,
    session: AsyncSession,
    index_id: str,
    error: str,
) -> None:
    await _mark_index_run_failed(session, index_id=index_id, error=error)
    await session.commit()


async def index_status(
    *,
    session: AsyncSession,
    project_id: str,
) -> dict:
    latest_run = await _get_latest_index_run(session, project_id=project_id)
    latest_ready = await _get_latest_ready_index_run(session, project_id=project_id)
    if latest_run is None and latest_ready is None:
        return {
            "status": "EMPTY",
            "project_id": project_id,
            "current": None,
            "latest_ready": None,
        }

    if latest_run is not None and str(latest_run.get("status")) in {"QUEUED", "RUNNING", "FAILED"}:
        return {
            "status": str(latest_run["status"]),
            "project_id": project_id,
            "current": _current_run_payload(latest_run),
            "latest_ready": _latest_ready_payload(latest_ready),
        }

    return {
        "status": "READY",
        "project_id": project_id,
        "current": None,
        "latest_ready": _latest_ready_payload(latest_ready or latest_run),
    }


def _search_entities_in_state(
    *,
    indexed_at: str | None,
    entities: list[dict[str, Any]],
    query: str,
    entity_types: list[str] | None,
    limit: int,
) -> dict:
    query_lower = query.strip().lower()
    query_tokens = set(_tokenize(query_lower))
    allowed_types = {item.strip() for item in (entity_types or []) if item.strip()}

    results: list[dict[str, Any]] = []
    for entity in entities:
        entity_type = str(entity.get("type") or entity.get("entity_type") or "")
        if allowed_types and entity_type not in allowed_types:
            continue
        name = str(entity.get("name") or "")
        search_text = str(
            entity.get("search_text")
            or _entity_search_text(
                entity_id=str(entity.get("entity_id") or ""),
                entity_type=entity_type,
                name=name,
                file_path=str(entity.get("file_path") or "") or None,
                kind=str(entity.get("kind") or "") or None,
            )
        )
        search_tokens = set(entity.get("search_tokens") or _tokenize(search_text))
        if query_lower not in search_text and not query_tokens.intersection(search_tokens):
            continue

        score = 0.3
        if query_lower and query_lower in name.lower():
            score += 0.5
        if query_lower and query_lower in entity_type.lower():
            score += 0.2
        if query_tokens:
            overlap = len(query_tokens.intersection(search_tokens))
            if overlap:
                score += min(0.4, overlap / max(1, len(query_tokens)) * 0.4)

        results.append(
            {
                "entity_id": entity.get("entity_id"),
                "type": entity_type,
                "name": name,
                "file_path": entity.get("file_path"),
                "language": entity.get("language"),
                "kind": entity.get("kind"),
                "line_start": entity.get("line_start"),
                "line_end": entity.get("line_end"),
                "score": round(float(min(score, 1.0)), 4),
            }
        )

    results.sort(
        key=lambda item: (item["score"], str(item.get("type") or ""), str(item.get("name") or "")),
        reverse=True,
    )
    return {
        "status": "READY",
        "entities": results[:limit],
        "total": len(results),
        "indexed_at": indexed_at,
    }


async def search_entities(
    *,
    session: AsyncSession,
    project_id: str,
    query: str,
    entity_types: list[str] | None,
    limit: int,
) -> dict:
    ready_run = await _get_latest_ready_index_run(session, project_id=project_id)
    if ready_run is None:
        return {"entities": [], "total": 0, "status": "EMPTY"}

    entity_rows = await _entity_candidate_rows(
        session,
        index_id=str(ready_run["index_id"]),
        query_lower=query.strip().lower(),
        entity_types=entity_types,
    )
    return _search_entities_in_state(
        indexed_at=_iso_or_none(ready_run.get("completed_at")),
        entities=[
            {
                "entity_id": row.get("entity_id"),
                "type": row.get("entity_type"),
                "name": row.get("name"),
                "file_path": row.get("file_path"),
                "language": row.get("language"),
                "kind": row.get("kind"),
                "line_start": row.get("line_start"),
                "line_end": row.get("line_end"),
                "search_text": row.get("search_text"),
                "search_tokens": list(row.get("search_tokens") or []),
            }
            for row in entity_rows
        ],
        query=query,
        entity_types=entity_types,
        limit=limit,
    )


def _chunk_score(query_tokens: set[str], chunk: dict, boosted_entity_ids: set[str]) -> float:
    tokens = set(chunk.get("tokens") or [])
    if not tokens:
        return 0.0
    overlap = len(query_tokens.intersection(tokens))
    base = overlap / max(1, len(query_tokens))
    if str(chunk.get("entity_id") or "") in boosted_entity_ids:
        base += 0.25
    return min(base, 1.0)


async def build_context_pack(
    *,
    session: AsyncSession,
    project_id: str,
    query: str,
    limit: int,
) -> dict:
    ready_run = await _get_latest_ready_index_run(session, project_id=project_id)
    if ready_run is None:
        return {
            "status": "EMPTY",
            "query": query,
            "architecture_map": {
                "indexed_at": None,
                "repo_path": None,
                "summary": {
                    "file_count": 0,
                    "symbol_count": 0,
                    "entity_count": 0,
                    "relationship_count": 0,
                    "chunk_count": 0,
                },
                "top_modules": [],
                "top_files": [],
            },
            "relevant_symbols": [],
            "citations": [],
        }

    query_lower = query.strip().lower()
    query_tokens = set(_tokenize(query_lower))

    entity_rows = await _entity_candidate_rows(
        session,
        index_id=str(ready_run["index_id"]),
        query_lower=query_lower,
        entity_types=["Symbol", "File", "Module"],
    )
    entity_result = _search_entities_in_state(
        indexed_at=_iso_or_none(ready_run.get("completed_at")),
        entities=[
            {
                "entity_id": row.get("entity_id"),
                "type": row.get("entity_type"),
                "name": row.get("name"),
                "file_path": row.get("file_path"),
                "language": row.get("language"),
                "kind": row.get("kind"),
                "line_start": row.get("line_start"),
                "line_end": row.get("line_end"),
                "search_text": row.get("search_text"),
                "search_tokens": list(row.get("search_tokens") or []),
            }
            for row in entity_rows
        ],
        query=query,
        entity_types=["Symbol", "File", "Module"],
        limit=max(limit * 3, 25),
    )
    boosted_entity_ids = {str(item.get("entity_id") or "") for item in entity_result.get("entities", [])}

    chunk_rows = await _chunk_candidate_rows(
        session,
        index_id=str(ready_run["index_id"]),
        query_tokens=query_tokens,
        boosted_entity_ids=boosted_entity_ids,
    )
    ranked_chunks: list[dict[str, Any]] = []
    for chunk in chunk_rows:
        score = _chunk_score(query_tokens, chunk, boosted_entity_ids)
        if score <= 0:
            continue
        ranked_chunks.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "entity_id": chunk.get("entity_id"),
                "file_path": chunk.get("file_path"),
                "language": chunk.get("language"),
                "line_start": chunk.get("line_start"),
                "line_end": chunk.get("line_end"),
                "snippet": chunk.get("snippet"),
                "score": round(float(score), 4),
            }
        )

    ranked_chunks.sort(
        key=lambda item: (item["score"], str(item.get("file_path") or ""), str(item.get("chunk_id") or "")),
        reverse=True,
    )
    top_chunks = ranked_chunks[: max(limit, 1)]

    relevant_symbols = [item for item in entity_result.get("entities", []) if item.get("type") == "Symbol"][:limit]
    citations = [
        {
            "citation_id": str(chunk.get("chunk_id") or ""),
            "source_type": "code_chunk",
            "entity_id": chunk.get("entity_id"),
            "file_path": chunk.get("file_path"),
            "line_start": chunk.get("line_start"),
            "line_end": chunk.get("line_end"),
            "snippet": chunk.get("snippet"),
            "score": chunk.get("score"),
        }
        for chunk in top_chunks
    ]

    return {
        "status": "READY",
        "query": query,
        "architecture_map": {
            "indexed_at": _iso_or_none(ready_run.get("completed_at")),
            "repo_path": ready_run.get("repo_path"),
            "summary": _stats_payload(ready_run),
            "top_modules": list(ready_run.get("top_modules_json") or []),
            "top_files": list(ready_run.get("top_files_json") or []),
        },
        "relevant_symbols": relevant_symbols,
        "citations": citations,
        "gaps": [] if citations else ["No high-scoring code citations for this query."],
    }


async def run_index_job(
    *,
    index_id: str,
) -> dict:
    async with open_db_session() as session:
        run = await _get_index_run(session, index_id=index_id)
        if run is None:
            raise ValueError(f"Unknown index run: {index_id}")

        project_id = str(run["project_id"])
        repo_root = _resolve_repo_path(str(run["repo_path"]))
        mode = str(run["mode"])
        base_ref = run.get("base_ref")
        head_ref = run.get("head_ref")
        max_files = int(run.get("max_files") or 5000)

        try:
            await _mark_index_run_running(
                session,
                index_id=index_id,
                phase="discovering",
                effective_mode=mode,
            )
            await session.commit()

            latest_ready = await _get_latest_ready_index_run(session, project_id=project_id)
            latest_ready_id = str(latest_ready["index_id"]) if latest_ready is not None else None

            if mode == "snapshot":
                target_paths = _iter_candidate_files(repo_root, max_files)
                scanned_files = len(target_paths)
                changed_files = len(target_paths)
            else:
                try:
                    rel_paths = _git_changed_files(repo_root, str(base_ref), str(head_ref))
                except RuntimeError as exc:
                    await _mark_index_run_failed(session, index_id=index_id, error=str(exc))
                    await session.commit()
                    raise

                target_paths = _filter_supported_rel_paths(repo_root, rel_paths)[:max_files]
                scanned_files = len(target_paths)
                changed_files = len(target_paths)

                if not target_paths:
                    async with session.begin():
                        if latest_ready_id is not None:
                            await _clone_index_rows(session, source_index_id=latest_ready_id, target_index_id=index_id)
                            source_ready = await _get_index_run(session, index_id=latest_ready_id)
                            ready_stats = _stats_payload(source_ready)
                            top_modules = list(source_ready.get("top_modules_json") or []) if source_ready else []
                            top_files = list(source_ready.get("top_files_json") or []) if source_ready else []
                        else:
                            ready_stats = _stats_payload(None)
                            top_modules = []
                            top_files = []
                        await _mark_index_run_ready(
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
                        await _delete_previous_ready_children(session, project_id=project_id, keep_index_id=index_id)
                    return {
                        "status": "READY",
                        "project_id": project_id,
                        "index_id": index_id,
                        "scanned_files": 0,
                        "changed_files": 0,
                    }

            await _update_index_run_progress(
                session,
                index_id=index_id,
                phase="extracting",
                processed_files=0,
                total_files=len(target_paths),
                scanned_files=scanned_files,
                changed_files=changed_files,
            )
            await session.commit()

            new_rows = _build_file_rows(repo_root, target_paths)
            processed_files = len(new_rows)

            if mode == "diff":
                if latest_ready_id is None:
                    await _mark_index_run_failed(
                        session,
                        index_id=index_id,
                        error="Diff indexing requires an existing READY snapshot for this project.",
                    )
                    await session.commit()
                    raise RuntimeError("Diff indexing requires an existing READY snapshot for this project.")
                changed_set = {str(path.relative_to(repo_root)) for path in target_paths}
                previous_rows = [
                    row
                    for row in await _load_index_file_rows(session, index_id=latest_ready_id)
                    if str(row.get("path") or "") not in changed_set
                ]
                merged_rows = previous_rows + new_rows
            else:
                merged_rows = new_rows

            await _update_index_run_progress(
                session,
                index_id=index_id,
                phase="materializing",
                processed_files=processed_files,
                total_files=len(target_paths),
                scanned_files=scanned_files,
                changed_files=changed_files,
            )
            await session.commit()

            materialized = _materialize_index(
                project_id=project_id,
                repo_path=repo_root,
                indexed_at=_now_iso(),
                mode=mode,
                source="indexing",
                file_rows=merged_rows,
            )

            async with session.begin():
                await _store_materialized_snapshot(
                    session,
                    index_id=index_id,
                    file_rows=materialized.get("files") or [],
                    materialized=materialized,
                )
                await _mark_index_run_ready(
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
                await _delete_previous_ready_children(session, project_id=project_id, keep_index_id=index_id)

            return {
                "status": "READY",
                "project_id": project_id,
                "index_id": index_id,
                "scanned_files": scanned_files,
                "changed_files": changed_files,
            }
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            if (await _get_index_run(session, index_id=index_id) or {}).get("status") != "FAILED":
                await _mark_index_run_failed(session, index_id=index_id, error=str(exc))
                await session.commit()
            raise
