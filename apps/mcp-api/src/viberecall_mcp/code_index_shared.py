from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from viberecall_mcp.config import get_settings


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
    return " ".join([entity_id, entity_type, name, file_path or "", kind or ""]).lower()


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
