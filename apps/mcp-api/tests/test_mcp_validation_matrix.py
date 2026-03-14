from __future__ import annotations

from viberecall_mcp.tool_access import required_scope_for_tool
from viberecall_mcp.tool_registry import TOOL_DEFINITIONS
from viberecall_mcp.tool_validation_matrix import (
    SCENARIO_GROUPS,
    SMOKE_PROFILE_DEFINITIONS,
    TOOL_VALIDATION_MATRIX,
)


def test_validation_matrix_covers_every_public_tool_exactly_once() -> None:
    registry_tools = {tool.name for tool in TOOL_DEFINITIONS}
    matrix_tools = set(TOOL_VALIDATION_MATRIX)

    assert matrix_tools == registry_tools


def test_validation_matrix_matches_scope_contract() -> None:
    for tool_name, entry in TOOL_VALIDATION_MATRIX.items():
        assert entry.scenario_group in SCENARIO_GROUPS
        assert entry.required_scope == required_scope_for_tool(tool_name)


def test_smoke_profiles_cover_all_tools_without_overlap() -> None:
    seen: set[str] = set()

    for profile in SMOKE_PROFILE_DEFINITIONS.values():
        for tool_name in profile.tool_names:
            assert tool_name not in seen
            seen.add(tool_name)
            assert tool_name in TOOL_VALIDATION_MATRIX
            assert TOOL_VALIDATION_MATRIX[tool_name].smoke_profile == profile.name
            required_scope = TOOL_VALIDATION_MATRIX[tool_name].required_scope
            assert required_scope is None or required_scope in profile.required_scopes

    assert seen == set(TOOL_VALIDATION_MATRIX)


def test_index_profile_is_explicitly_gated() -> None:
    index_profile = SMOKE_PROFILE_DEFINITIONS["index"]

    assert index_profile.requires_repo_source is True
    assert index_profile.requires_remote_indexing is True
    assert "viberecall_index_repo" in index_profile.tool_names
    assert "viberecall_get_context_pack" in index_profile.tool_names


def test_resolution_profile_is_privileged_and_destructive() -> None:
    resolution_profile = SMOKE_PROFILE_DEFINITIONS["resolution"]

    assert resolution_profile.destructive is True
    assert resolution_profile.required_token_key == "resolution"
    assert set(resolution_profile.tool_names) == {
        "viberecall_merge_entities",
        "viberecall_split_entity",
    }
