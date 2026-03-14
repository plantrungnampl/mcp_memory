from __future__ import annotations

from dataclasses import dataclass

from viberecall_mcp.tool_access import required_scope_for_tool


SCENARIO_GROUPS = (
    "memory-core",
    "ops-status",
    "graph-resolution",
    "index-context",
)


@dataclass(frozen=True, slots=True)
class ToolValidationEntry:
    tool_name: str
    scenario_group: str
    smoke_profile: str
    required_scope: str | None


@dataclass(frozen=True, slots=True)
class SmokeProfileDefinition:
    name: str
    tool_names: tuple[str, ...]
    required_scopes: tuple[str, ...]
    required_token_key: str
    requires_repo_source: bool = False
    requires_remote_indexing: bool = False
    destructive: bool = False


def _entry(tool_name: str, *, scenario_group: str, smoke_profile: str) -> ToolValidationEntry:
    return ToolValidationEntry(
        tool_name=tool_name,
        scenario_group=scenario_group,
        smoke_profile=smoke_profile,
        required_scope=required_scope_for_tool(tool_name),
    )


TOOL_VALIDATION_MATRIX = {
    "viberecall_save_episode": _entry(
        "viberecall_save_episode",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_save": _entry(
        "viberecall_save",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_search_memory": _entry(
        "viberecall_search_memory",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_search": _entry(
        "viberecall_search",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_get_fact": _entry(
        "viberecall_get_fact",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_get_facts": _entry(
        "viberecall_get_facts",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_update_fact": _entry(
        "viberecall_update_fact",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_pin_memory": _entry(
        "viberecall_pin_memory",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_timeline": _entry(
        "viberecall_timeline",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_get_status": _entry(
        "viberecall_get_status",
        scenario_group="ops-status",
        smoke_profile="ops",
    ),
    "viberecall_delete_episode": _entry(
        "viberecall_delete_episode",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_get_operation": _entry(
        "viberecall_get_operation",
        scenario_group="ops-status",
        smoke_profile="ops",
    ),
    "viberecall_index_repo": _entry(
        "viberecall_index_repo",
        scenario_group="index-context",
        smoke_profile="index",
    ),
    "viberecall_get_index_status": _entry(
        "viberecall_get_index_status",
        scenario_group="index-context",
        smoke_profile="index",
    ),
    "viberecall_index_status": _entry(
        "viberecall_index_status",
        scenario_group="index-context",
        smoke_profile="index",
    ),
    "viberecall_search_entities": _entry(
        "viberecall_search_entities",
        scenario_group="graph-resolution",
        smoke_profile="graph",
    ),
    "viberecall_get_neighbors": _entry(
        "viberecall_get_neighbors",
        scenario_group="graph-resolution",
        smoke_profile="graph",
    ),
    "viberecall_find_paths": _entry(
        "viberecall_find_paths",
        scenario_group="graph-resolution",
        smoke_profile="graph",
    ),
    "viberecall_explain_fact": _entry(
        "viberecall_explain_fact",
        scenario_group="graph-resolution",
        smoke_profile="graph",
    ),
    "viberecall_resolve_reference": _entry(
        "viberecall_resolve_reference",
        scenario_group="graph-resolution",
        smoke_profile="graph",
    ),
    "viberecall_merge_entities": _entry(
        "viberecall_merge_entities",
        scenario_group="graph-resolution",
        smoke_profile="resolution",
    ),
    "viberecall_split_entity": _entry(
        "viberecall_split_entity",
        scenario_group="graph-resolution",
        smoke_profile="resolution",
    ),
    "viberecall_get_context_pack": _entry(
        "viberecall_get_context_pack",
        scenario_group="index-context",
        smoke_profile="index",
    ),
    "viberecall_working_memory_get": _entry(
        "viberecall_working_memory_get",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
    "viberecall_working_memory_patch": _entry(
        "viberecall_working_memory_patch",
        scenario_group="memory-core",
        smoke_profile="core",
    ),
}


SMOKE_PROFILE_DEFINITIONS = {
    "core": SmokeProfileDefinition(
        name="core",
        tool_names=tuple(
            tool_name
            for tool_name, entry in TOOL_VALIDATION_MATRIX.items()
            if entry.smoke_profile == "core"
        ),
        required_scopes=("memory:read", "memory:write", "facts:write", "delete:write"),
        required_token_key="core",
        destructive=True,
    ),
    "ops": SmokeProfileDefinition(
        name="ops",
        tool_names=tuple(
            tool_name
            for tool_name, entry in TOOL_VALIDATION_MATRIX.items()
            if entry.smoke_profile == "ops"
        ),
        required_scopes=("ops:read",),
        required_token_key="ops",
    ),
    "graph": SmokeProfileDefinition(
        name="graph",
        tool_names=tuple(
            tool_name
            for tool_name, entry in TOOL_VALIDATION_MATRIX.items()
            if entry.smoke_profile == "graph"
        ),
        required_scopes=("memory:write", "memory:read", "facts:write", "entities:read", "graph:read"),
        required_token_key="graph",
    ),
    "index": SmokeProfileDefinition(
        name="index",
        tool_names=tuple(
            tool_name
            for tool_name, entry in TOOL_VALIDATION_MATRIX.items()
            if entry.smoke_profile == "index"
        ),
        required_scopes=("index:run", "index:read", "ops:read"),
        required_token_key="index",
        requires_repo_source=True,
        requires_remote_indexing=True,
    ),
    "resolution": SmokeProfileDefinition(
        name="resolution",
        tool_names=tuple(
            tool_name
            for tool_name, entry in TOOL_VALIDATION_MATRIX.items()
            if entry.smoke_profile == "resolution"
        ),
        required_scopes=("resolution:write", "memory:write", "entities:read", "ops:read"),
        required_token_key="resolution",
        destructive=True,
    ),
}
