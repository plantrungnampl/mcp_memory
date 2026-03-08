from __future__ import annotations

from dataclasses import dataclass


OUTPUT_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict


def build_output_envelope(
    *,
    request_id: str,
    ok: bool,
    result: dict | None = None,
    error: dict | None = None,
) -> dict:
    return {
        "output_version": OUTPUT_VERSION,
        "ok": ok,
        "result": result if ok else None,
        "error": error if not ok else None,
        "request_id": request_id,
    }


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="viberecall_save",
        description="Persist an episode with fast acknowledgement and async enrichment.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "content": {"type": "string", "minLength": 1, "maxLength": 200000},
                "reference_time": {"type": ["string", "null"], "default": None},
                "metadata": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["decision", "bugfix", "requirement", "style", "note"],
                        },
                        "repo": {"type": "string", "maxLength": 200},
                        "branch": {"type": "string", "maxLength": 200},
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 400},
                            "maxItems": 200,
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 64},
                            "maxItems": 50,
                        },
                        "importance": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "default": "medium",
                        },
                    },
                },
                "idempotency_key": {"type": ["string", "null"], "default": None, "maxLength": 128},
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="viberecall_search",
        description="Search facts and recent episodes with temporal filters.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 2000},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "filters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "reference_time_from": {"type": ["string", "null"], "default": None},
                        "reference_time_to": {"type": ["string", "null"], "default": None},
                        "valid_at": {"type": ["string", "null"], "default": None},
                        "as_of_ingest": {"type": ["string", "null"], "default": None},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 64},
                            "maxItems": 50,
                            "default": [],
                        },
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 400},
                            "maxItems": 200,
                            "default": [],
                        },
                        "entity_types": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 64},
                            "maxItems": 20,
                            "default": [],
                        },
                    },
                },
                "sort": {
                    "type": "string",
                    "enum": ["RELEVANCE", "RECENCY", "TIME"],
                    "default": "RELEVANCE",
                },
                "cursor": {"type": ["string", "null"], "default": None, "maxLength": 2048},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="viberecall_get_facts",
        description="List facts with filters and pagination.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "filters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "entity_type": {"type": ["string", "null"], "default": None, "maxLength": 64},
                        "tag": {"type": ["string", "null"], "default": None, "maxLength": 64},
                        "valid_at": {"type": ["string", "null"], "default": None},
                    },
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                "cursor": {"type": ["string", "null"], "default": None, "maxLength": 2048},
            },
        },
    ),
    ToolDefinition(
        name="viberecall_update_fact",
        description="Apply a temporal update without overwriting history.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fact_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "new_text": {"type": "string", "minLength": 1, "maxLength": 20000},
                "effective_time": {"type": "string"},
                "reason": {"type": ["string", "null"], "default": None, "maxLength": 2000},
            },
            "required": ["fact_id", "new_text", "effective_time"],
        },
    ),
    ToolDefinition(
        name="viberecall_timeline",
        description="List timeline episodes for a project.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "from": {"type": ["string", "null"], "default": None},
                "to": {"type": ["string", "null"], "default": None},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                "cursor": {"type": ["string", "null"], "default": None, "maxLength": 2048},
            },
        },
    ),
    ToolDefinition(
        name="viberecall_get_status",
        description="Get MCP runtime and backend status for the current project.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
    ),
    ToolDefinition(
        name="viberecall_delete_episode",
        description="Delete one episode and related memory artifacts for the current project.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "episode_id": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            "required": ["episode_id"],
        },
    ),
    ToolDefinition(
        name="viberecall_index_repo",
        description="Index a code repository for project-aware context retrieval.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "repo_path": {"type": "string", "minLength": 1, "maxLength": 2000},
                "mode": {"type": "string", "enum": ["snapshot", "diff"], "default": "snapshot"},
                "base_ref": {"type": ["string", "null"], "default": None, "maxLength": 256},
                "head_ref": {"type": ["string", "null"], "default": None, "maxLength": 256},
                "max_files": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 5000},
            },
            "required": ["repo_path"],
        },
    ),
    ToolDefinition(
        name="viberecall_index_status",
        description="Get repository index status for the current project.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
    ),
    ToolDefinition(
        name="viberecall_search_entities",
        description="Search indexed project entities (files, modules, symbols) with relevance scores.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 2000},
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 64},
                    "maxItems": 20,
                    "default": [],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="viberecall_get_context_pack",
        description="Build a structured project context pack with architecture map, symbols, and citations.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 2000},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 12},
            },
            "required": ["query"],
        },
    ),
)


def get_tool_definitions() -> list[dict]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }
        for tool in TOOL_DEFINITIONS
    ]


def get_tool_definition(name: str) -> ToolDefinition | None:
    for tool in TOOL_DEFINITIONS:
        if tool.name == name:
            return tool
    return None
