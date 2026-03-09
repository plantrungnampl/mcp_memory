from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from viberecall_mcp.tool_registry import TOOL_DEFINITIONS


FREE_RUNTIME_TOOL_NAMES = frozenset(tool.name for tool in TOOL_DEFINITIONS)
SCOPE_MATRIX = {
    "viberecall_save_episode": "memory:write",
    "viberecall_save": "memory:write",
    "viberecall_search_memory": "memory:read",
    "viberecall_search": "memory:read",
    "viberecall_get_fact": "memory:read",
    "viberecall_get_facts": "memory:read",
    "viberecall_update_fact": "facts:write",
    "viberecall_timeline": "memory:read",
    "viberecall_get_status": "ops:read",
    "viberecall_delete_episode": "delete:write",
    "viberecall_get_operation": "ops:read",
    "viberecall_index_repo": "index:run",
    "viberecall_get_index_status": "index:read",
    "viberecall_index_status": "index:read",
    "viberecall_search_entities": "index:read",
    "viberecall_get_context_pack": "index:read",
    "viberecall_working_memory_get": "memory:read",
    "viberecall_working_memory_patch": "memory:write",
}
LEGACY_SCOPE_ALIASES = {
    "memory:read": {"memory:read"},
    "memory:write": {"memory:write"},
    "facts:write": {"facts:write"},
    "index:read": {"index:read", "memory:read"},
    "index:run": {"index:run", "memory:write"},
    "ops:read": {"ops:read", "memory:read"},
    "delete:write": {"delete:write", "memory:write"},
}


def _tool_name(tool: Any) -> str | None:
    if hasattr(tool, "name"):
        value = getattr(tool, "name")
        return str(value) if value is not None else None
    if isinstance(tool, dict):
        value = tool.get("name")
        return str(value) if value is not None else None
    return None


def is_tool_allowed_for_plan(plan: str, tool_name: str) -> bool:
    _ = plan
    return tool_name in FREE_RUNTIME_TOOL_NAMES


def filter_tools_for_plan(plan: str, tools: Iterable[Any]) -> list[Any]:
    _ = plan
    return [tool for tool in tools if (_tool_name(tool) or "") in FREE_RUNTIME_TOOL_NAMES]


def token_has_scope(token_scopes: Iterable[str], required_scope: str) -> bool:
    current = set(token_scopes)
    accepted = LEGACY_SCOPE_ALIASES.get(required_scope, {required_scope})
    return any(scope in current for scope in accepted)
