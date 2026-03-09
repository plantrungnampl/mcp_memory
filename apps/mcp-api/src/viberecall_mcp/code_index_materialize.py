from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path
from typing import Any

from viberecall_mcp.code_index_shared import (
    _JS_CLASS_RE,
    _JS_FUNCTION_RE,
    _JS_IMPORT_FROM_RE,
    _JS_REQUIRE_RE,
    _JS_VAR_FUNC_RE,
    _MAX_TOKENS_PER_CHUNK,
    _SKIP_DIRS,
    _SUPPORTED_EXTENSIONS,
    _entity_row,
    _file_entity_id,
    _import_entity_id,
    _module_entity_id,
    _symbol_entity_id,
    _tokenize,
    _trim_snippet,
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _language_for_path(path: Path) -> str | None:
    return _SUPPORTED_EXTENSIONS.get(path.suffix.lower())


def _extract_snippet(lines: list[str], line_start: int, line_end: int) -> str:
    start = max(1, line_start)
    end = max(start, line_end)
    snippet = "\n".join(lines[start - 1 : end])
    return _trim_snippet(snippet)


def _module_name_for_file(rel_path: str) -> str:
    parts = [part for part in Path(rel_path).parts if part not in {"."}]
    if not parts or len(parts) == 1:
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


def _python_symbols_and_imports(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    symbols: list[dict[str, Any]] = []
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
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return symbols, sorted(imports)


def _js_ts_symbols_and_imports(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    symbols: list[dict[str, Any]] = []
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


def _extract_file_row(repo_path: Path, file_path: Path) -> dict[str, Any]:
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

    symbol_rows: list[dict[str, Any]] = []
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


def _materialize_index(
    *,
    project_id: str,
    repo_path: Path,
    indexed_at: str,
    mode: str,
    source: str,
    file_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    _ = source
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
            relationships.append({"type": "CONTAINS", "source_id": module_id, "target_id": file_id, "weight": 1})
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
                relationships.append({"type": "IMPORTS", "source_id": file_id, "target_id": import_id, "weight": 1})
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
                relationships.append({"type": "CONTAINS", "source_id": file_id, "target_id": symbol_id, "weight": 1})
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


def _build_file_rows(repo_path: Path, file_paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in file_paths:
        try:
            rows.append(_extract_file_row(repo_path, path))
        except (OSError, ValueError):
            continue
    return rows
