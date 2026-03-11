from __future__ import annotations

from dataclasses import dataclass, field


OUTPUT_VERSION = "1.0"
_TOOL_ERROR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "code": {"type": "string"},
        "message": {"type": "string"},
        "details": {
            "type": "object",
            "additionalProperties": True,
        },
    },
    "required": ["code", "message", "details"],
}
_TOOL_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "output_version": {"type": "string"},
        "ok": {"type": "boolean"},
        "result": {
            "type": ["object", "null"],
            "additionalProperties": True,
        },
        "error": {
            "anyOf": [
                {"type": "null"},
                _TOOL_ERROR_SCHEMA,
            ]
        },
        "request_id": {"type": "string"},
    },
    "required": ["output_version", "ok", "result", "error", "request_id"],
}


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict = field(default_factory=lambda: dict(_TOOL_OUTPUT_SCHEMA))


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
        name="viberecall_save_episode",
        description="Store a raw observation in canonical memory with async enrichment queued.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "content": {"type": "string", "minLength": 1, "maxLength": 200000},
                "episode_kind": {"type": ["string", "null"], "default": None, "maxLength": 64},
                "source_kind": {"type": ["string", "null"], "default": None, "maxLength": 64},
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
        name="viberecall_save",
        description="Legacy compatibility wrapper for canonical episode save.",
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
        name="viberecall_search_memory",
        description="Search canonical memory facts and observations with grouped results.",
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
                        "salience_classes": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 32},
                            "maxItems": 10,
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
                "snapshot_token": {"type": ["string", "null"], "default": None, "maxLength": 2048},
                "memory_scope": {
                    "type": "string",
                    "enum": ["project", "linked", "org"],
                    "default": "project",
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="viberecall_search",
        description="Legacy compatibility wrapper for canonical memory search.",
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
                        "salience_classes": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 32},
                            "maxItems": 10,
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
                "memory_scope": {
                    "type": "string",
                    "enum": ["project", "linked", "org"],
                    "default": "project",
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="viberecall_get_fact",
        description="Fetch one canonical fact with lineage and provenance.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fact_version_id": {"type": ["string", "null"], "default": None, "maxLength": 128},
                "fact_group_id": {"type": ["string", "null"], "default": None, "maxLength": 128},
            },
            "anyOf": [
                {"required": ["fact_version_id"]},
                {"required": ["fact_group_id"]},
            ],
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
        description="Apply a transactional fact correction without overwriting history.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fact_id": {"type": ["string", "null"], "default": None, "minLength": 1, "maxLength": 128},
                "fact_group_id": {"type": ["string", "null"], "default": None, "minLength": 1, "maxLength": 128},
                "expected_current_version_id": {
                    "type": ["string", "null"],
                    "default": None,
                    "minLength": 1,
                    "maxLength": 128,
                },
                "new_text": {"type": ["string", "null"], "default": None, "minLength": 1, "maxLength": 20000},
                "statement": {"type": ["string", "null"], "default": None, "minLength": 1, "maxLength": 20000},
                "effective_time": {"type": "string"},
                "reason": {"type": ["string", "null"], "default": None, "maxLength": 2000},
                "metadata": {"type": "object", "additionalProperties": True},
            },
            "required": ["effective_time"],
        },
    ),
    ToolDefinition(
        name="viberecall_pin_memory",
        description="Manually pin, unpin, or demote the salience state of a canonical fact, entity, or episode.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "target_kind": {
                    "type": "string",
                    "enum": ["FACT", "ENTITY", "EPISODE"],
                },
                "target_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "pin_action": {
                    "type": "string",
                    "enum": ["PIN", "UNPIN", "DEMOTE"],
                },
                "reason": {"type": ["string", "null"], "default": None, "maxLength": 2000},
            },
            "required": ["target_kind", "target_id", "pin_action"],
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
        name="viberecall_get_operation",
        description="Get async operation status and result summary for the current project.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "operation_id": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            "required": ["operation_id"],
        },
    ),
    ToolDefinition(
        name="viberecall_index_repo",
        description="Index a code repository for project-aware context retrieval.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "repo_source": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "type": {"type": "string", "enum": ["git", "workspace_bundle"]},
                        "remote_url": {"type": "string", "minLength": 1, "maxLength": 2000},
                        "ref": {"type": "string", "minLength": 1, "maxLength": 512},
                        "credential_ref": {"type": ["string", "null"], "default": None, "maxLength": 128},
                        "bundle_ref": {"type": "string", "minLength": 1, "maxLength": 256},
                        "base_commit": {"type": ["string", "null"], "default": None, "maxLength": 256},
                        "repo_name": {"type": ["string", "null"], "default": None, "maxLength": 200},
                    },
                    "required": ["type"],
                    "allOf": [
                        {
                            "if": {"properties": {"type": {"const": "git"}}},
                            "then": {"required": ["remote_url", "ref"]},
                        },
                        {
                            "if": {"properties": {"type": {"const": "workspace_bundle"}}},
                            "then": {"required": ["bundle_ref"]},
                        },
                    ],
                },
                "mode": {"type": "string", "enum": ["FULL_SNAPSHOT"], "default": "FULL_SNAPSHOT"},
                "max_files": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 5000},
                "idempotency_key": {"type": ["string", "null"], "default": None, "maxLength": 128},
            },
            "required": ["repo_source"],
        },
    ),
    ToolDefinition(
        name="viberecall_get_index_status",
        description="Get repository index status using the canonical v3 tool name.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "index_run_id": {"type": ["string", "null"], "default": None, "minLength": 1, "maxLength": 128},
            },
        },
    ),
    ToolDefinition(
        name="viberecall_index_status",
        description="Legacy compatibility wrapper for repository index status.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "index_run_id": {"type": ["string", "null"], "default": None, "minLength": 1, "maxLength": 128},
            },
        },
    ),
    ToolDefinition(
        name="viberecall_search_entities",
        description="Search canonical project entities with aliases, support counts, and recent support snippets.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 2000},
                "entity_kinds": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 64},
                    "maxItems": 20,
                    "default": [],
                },
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 64},
                    "maxItems": 20,
                    "default": [],
                },
                "repo_scope": {"type": ["string", "null"], "default": None, "maxLength": 128},
                "salience_classes": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 32},
                    "maxItems": 10,
                    "default": [],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="viberecall_get_neighbors",
        description="Return a bounded depth-1 neighborhood around a canonical entity.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "entity_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "direction": {
                    "type": "string",
                    "enum": ["IN", "OUT", "BOTH"],
                    "default": "BOTH",
                },
                "relation_types": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 128},
                    "maxItems": 32,
                    "default": [],
                },
                "depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
                "current_only": {"type": "boolean", "default": True},
                "valid_at": {"type": ["string", "null"], "default": None},
                "as_of_system_time": {"type": ["string", "null"], "default": None},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": ["entity_id"],
        },
    ),
    ToolDefinition(
        name="viberecall_find_paths",
        description="Find bounded canonical graph paths between two entities using recursive SQL.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "src_entity_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "dst_entity_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "relation_types": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 128},
                    "maxItems": 32,
                    "default": [],
                },
                "max_depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 2},
                "current_only": {"type": "boolean", "default": True},
                "valid_at": {"type": ["string", "null"], "default": None},
                "as_of_system_time": {"type": ["string", "null"], "default": None},
                "limit_paths": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["src_entity_id", "dst_entity_id"],
        },
    ),
    ToolDefinition(
        name="viberecall_explain_fact",
        description="Explain a canonical fact version with lineage, provenance, and supporting episodes.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fact_version_id": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            "required": ["fact_version_id"],
        },
    ),
    ToolDefinition(
        name="viberecall_resolve_reference",
        description="Resolve a mention against canonical entities, augmented by the latest READY code index when available.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "mention_text": {"type": "string", "minLength": 1, "maxLength": 2000},
                "observed_kind": {"type": ["string", "null"], "default": None, "maxLength": 64},
                "repo_scope": {"type": ["string", "null"], "default": None, "maxLength": 400},
                "include_code_index": {"type": "boolean", "default": True},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["mention_text"],
        },
    ),
    ToolDefinition(
        name="viberecall_merge_entities",
        description="Privileged canonical entity merge with redirect creation and async projection reconciliation.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "target_entity_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "source_entity_ids": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 128},
                    "minItems": 1,
                    "maxItems": 50,
                },
                "reason": {"type": ["string", "null"], "default": None, "maxLength": 2000},
            },
            "required": ["target_entity_id", "source_entity_ids"],
        },
    ),
    ToolDefinition(
        name="viberecall_split_entity",
        description="Privileged canonical entity split with explicit alias and fact rebinding instructions.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "source_entity_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "reason": {"type": ["string", "null"], "default": None, "maxLength": 2000},
                "partitions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "target_entity_id": {"type": ["string", "null"], "default": None, "maxLength": 128},
                            "new_entity": {
                                "type": ["object", "null"],
                                "default": None,
                                "additionalProperties": False,
                                "properties": {
                                    "entity_kind": {"type": "string", "minLength": 1, "maxLength": 64},
                                    "canonical_name": {"type": "string", "minLength": 1, "maxLength": 400},
                                    "display_name": {"type": ["string", "null"], "default": None, "maxLength": 400},
                                },
                                "required": ["entity_kind", "canonical_name"],
                            },
                            "alias_values": {
                                "type": "array",
                                "items": {"type": "string", "minLength": 1, "maxLength": 400},
                                "maxItems": 200,
                                "default": [],
                            },
                            "fact_bindings": {
                                "type": "array",
                                "maxItems": 200,
                                "default": [],
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "fact_version_id": {"type": "string", "minLength": 1, "maxLength": 128},
                                        "slot": {"type": "string", "enum": ["subject", "object", "both"]},
                                    },
                                    "required": ["fact_version_id", "slot"],
                                },
                            },
                        },
                        "required": ["alias_values", "fact_bindings"],
                        "allOf": [
                            {
                                "anyOf": [
                                    {"required": ["target_entity_id"]},
                                    {"required": ["new_entity"]},
                                ]
                            }
                        ],
                    },
                },
            },
            "required": ["source_entity_id", "partitions"],
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
                "memory_scope": {
                    "type": "string",
                    "enum": ["project", "linked", "org"],
                    "default": "project",
                },
                "task_id": {"type": ["string", "null"], "default": None, "minLength": 1, "maxLength": 128},
                "session_id": {
                    "type": ["string", "null"],
                    "default": None,
                    "minLength": 1,
                    "maxLength": 128,
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="viberecall_working_memory_get",
        description="Get persisted working memory state for a task/session.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "task_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "session_id": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            "required": ["task_id", "session_id"],
        },
    ),
    ToolDefinition(
        name="viberecall_working_memory_patch",
        description="Patch persisted working memory state for a task/session.",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "task_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "session_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "patch": {
                    "type": "object",
                    "additionalProperties": True,
                },
                "checkpoint_note": {"type": ["string", "null"], "default": None, "maxLength": 500},
                "expires_at": {"type": ["string", "null"], "default": None},
            },
            "required": ["task_id", "session_id", "patch"],
        },
    ),
)


def get_tool_definitions() -> list[dict]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
            "outputSchema": tool.output_schema,
        }
        for tool in TOOL_DEFINITIONS
    ]


def get_tool_definition(name: str) -> ToolDefinition | None:
    for tool in TOOL_DEFINITIONS:
        if tool.name == name:
            return tool
    return None
