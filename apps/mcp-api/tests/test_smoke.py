import pytest

from viberecall_mcp.config import REPO_ROOT, Settings
from viberecall_mcp.mcp_server import build_initialize_result, get_tool_definitions


def test_initialize_capabilities_present() -> None:
    result = build_initialize_result()
    assert "tools" in result["capabilities"]


def test_public_tools_registered() -> None:
    tools = get_tool_definitions()
    assert [tool["name"] for tool in tools] == [
        "viberecall_save_episode",
        "viberecall_save",
        "viberecall_search_memory",
        "viberecall_search",
        "viberecall_get_fact",
        "viberecall_get_facts",
        "viberecall_update_fact",
        "viberecall_pin_memory",
        "viberecall_timeline",
        "viberecall_get_status",
        "viberecall_delete_episode",
        "viberecall_get_operation",
        "viberecall_index_repo",
        "viberecall_get_index_status",
        "viberecall_index_status",
        "viberecall_search_entities",
        "viberecall_get_neighbors",
        "viberecall_find_paths",
        "viberecall_explain_fact",
        "viberecall_resolve_reference",
        "viberecall_merge_entities",
        "viberecall_split_entity",
        "viberecall_get_context_pack",
        "viberecall_working_memory_get",
        "viberecall_working_memory_patch",
    ]


def test_settings_reject_placeholder_runtime_secrets_outside_development() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL must be configured"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/viberecall",
            token_pepper="change-me",
            export_signing_secret="dev-export-secret",
            control_plane_internal_secret="dev-control-plane-secret",
            stripe_webhook_secret="whsec_dev",
        )


def test_settings_require_graphiti_api_key_when_graphiti_backend_enabled() -> None:
    with pytest.raises(ValueError, match="GRAPHITI_API_KEY must be configured when MEMORY_BACKEND=graphiti"):
        Settings(
            _env_file=None,
            app_env="development",
            memory_backend="graphiti",
            control_plane_internal_secret="test-control-plane-secret",
            token_pepper="test-token-pepper",
            graphiti_api_key="",
        )


def test_settings_accept_graphiti_api_key_when_graphiti_backend_enabled() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        memory_backend="graphiti",
        control_plane_internal_secret="test-control-plane-secret",
        token_pepper="test-token-pepper",
        graphiti_api_key="sk-test-graphiti",
    )

    assert settings.memory_backend == "graphiti"
    assert settings.graphiti_api_key == "sk-test-graphiti"


def test_settings_default_index_roots_fall_back_to_repo_root() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        control_plane_internal_secret="test-control-plane-secret",
        token_pepper="test-token-pepper",
        index_repo_allowed_roots="",
    )
    assert settings.resolved_index_repo_allowed_roots() == (REPO_ROOT.resolve(),)
