from __future__ import annotations

import json

from viberecall_mcp.ids import new_id
from viberecall_mcp.tool_registry import build_output_envelope, get_tool_definition, get_tool_definitions
from viberecall_mcp.tool_access import filter_tools_for_plan


def build_initialize_result() -> dict:
    return {
        "protocolVersion": "2025-06-18",
        "serverInfo": {
            "name": "viberecall-mcp",
            "title": "VibeRecall MCP",
            "version": "0.1.0",
        },
        "capabilities": {
            "tools": {"listChanged": True},
        },
    }


def list_tools_result(plan: str | None = None) -> dict:
    return {"tools": filter_tools_for_plan(plan or "free", get_tool_definitions())}


def tool_error(request_id: str, code: str, message: str, details: dict | None = None) -> dict:
    return build_output_envelope(
        request_id=request_id,
        ok=False,
        error={"code": code, "message": message, "details": details or {}},
    )


def stub_tool_response(tool_name: str) -> dict:
    request_id = new_id("req")
    if get_tool_definition(tool_name) is None:
        return tool_error(request_id, "INVALID_ARGUMENT", f"Unknown tool: {tool_name}")
    return tool_error(
        request_id,
        "INTERNAL",
        f"Tool handler not implemented yet: {tool_name}",
    )


def as_mcp_text_result(payload: dict, *, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "isError": is_error,
    }
