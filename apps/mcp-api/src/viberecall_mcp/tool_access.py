from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from viberecall_mcp.tool_registry import TOOL_DEFINITIONS


FREE_RUNTIME_TOOL_NAMES = frozenset(tool.name for tool in TOOL_DEFINITIONS)


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
