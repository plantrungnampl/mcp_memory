from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from viberecall_mcp.tool_registry import TOOL_DEFINITIONS


ALL_TOOL_NAMES = frozenset(tool.name for tool in TOOL_DEFINITIONS)
PLAN_TOOL_ALLOWLIST = {
    "free": ALL_TOOL_NAMES,
    "pro": ALL_TOOL_NAMES,
    "team": ALL_TOOL_NAMES,
}
SCOPE_MATRIX = {
    "viberecall_save_episode": "memory:write",
    "viberecall_save": "memory:write",
    "viberecall_search_memory": "memory:read",
    "viberecall_search": "memory:read",
    "viberecall_get_fact": "memory:read",
    "viberecall_get_facts": "memory:read",
    "viberecall_update_fact": "facts:write",
    "viberecall_pin_memory": "facts:write",
    "viberecall_timeline": "memory:read",
    "viberecall_get_status": "ops:read",
    "viberecall_delete_episode": "delete:write",
    "viberecall_get_operation": "ops:read",
    "viberecall_index_repo": "index:run",
    "viberecall_get_index_status": "index:read",
    "viberecall_index_status": "index:read",
    "viberecall_search_entities": "entities:read",
    "viberecall_get_neighbors": "graph:read",
    "viberecall_find_paths": "graph:read",
    "viberecall_explain_fact": "memory:read",
    "viberecall_resolve_reference": "entities:read",
    "viberecall_merge_entities": "resolution:write",
    "viberecall_split_entity": "resolution:write",
    "viberecall_get_context_pack": "index:read",
    "viberecall_working_memory_get": "memory:read",
    "viberecall_working_memory_patch": "memory:write",
}
LEGACY_SCOPE_ALIASES = {
    "memory:read": {"memory:read"},
    "memory:write": {"memory:write"},
    "facts:write": {"facts:write"},
    "entities:read": {"entities:read", "memory:read", "index:read"},
    "graph:read": {"graph:read", "memory:read"},
    "index:read": {"index:read", "memory:read", "codeindex:read"},
    "index:run": {"index:run", "codeindex:write"},
    "resolution:write": {"resolution:write"},
    "ops:read": {"ops:read", "memory:read"},
    "delete:write": {"delete:write"},
}


def _tool_name(tool: Any) -> str | None:
    if hasattr(tool, "name"):
        value = getattr(tool, "name")
        return str(value) if value is not None else None
    if isinstance(tool, dict):
        value = tool.get("name")
        return str(value) if value is not None else None
    return None


def _normalize_plan(plan: str | None) -> str:
    candidate = str(plan or "free").strip().lower() or "free"
    return candidate if candidate in PLAN_TOOL_ALLOWLIST else "free"


def required_scope_for_tool(tool_name: str) -> str | None:
    return SCOPE_MATRIX.get(tool_name)


def is_tool_allowed_for_plan(plan: str, tool_name: str) -> bool:
    return tool_name in PLAN_TOOL_ALLOWLIST[_normalize_plan(plan)]


def filter_tools_for_plan(plan: str, tools: Iterable[Any]) -> list[Any]:
    allowed = PLAN_TOOL_ALLOWLIST[_normalize_plan(plan)]
    return [tool for tool in tools if (_tool_name(tool) or "") in allowed]


def token_has_scope(token_scopes: Iterable[str], required_scope: str) -> bool:
    current = set(token_scopes)
    accepted = LEGACY_SCOPE_ALIASES.get(required_scope, {required_scope})
    return any(scope in current for scope in accepted)


def is_tool_allowed_for_token(
    *,
    plan: str | None,
    scopes: Iterable[str],
    tool_name: str,
) -> bool:
    if not is_tool_allowed_for_plan(_normalize_plan(plan), tool_name):
        return False
    required_scope = required_scope_for_tool(tool_name)
    if required_scope is None:
        return True
    return token_has_scope(scopes, required_scope)


def filter_tools_for_token(
    *,
    plan: str | None,
    scopes: Iterable[str],
    tools: Iterable[Any],
) -> list[Any]:
    return [
        tool
        for tool in filter_tools_for_plan(_normalize_plan(plan), tools)
        if is_tool_allowed_for_token(
            plan=plan,
            scopes=scopes,
            tool_name=(_tool_name(tool) or ""),
        )
    ]
