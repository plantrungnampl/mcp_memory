import pytest

from viberecall_mcp.config import REPO_ROOT, Settings
from viberecall_mcp.mcp_server import build_initialize_result, get_tool_definitions


def test_initialize_capabilities_present() -> None:
    result = build_initialize_result()
    assert "tools" in result["capabilities"]


def test_public_tools_registered() -> None:
    tools = get_tool_definitions()
    assert [tool["name"] for tool in tools] == [
        "viberecall_save",
        "viberecall_search",
        "viberecall_get_facts",
        "viberecall_update_fact",
        "viberecall_timeline",
        "viberecall_get_status",
        "viberecall_delete_episode",
        "viberecall_index_repo",
        "viberecall_index_status",
        "viberecall_search_entities",
        "viberecall_get_context_pack",
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


def test_settings_default_index_roots_fall_back_to_repo_root() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        control_plane_internal_secret="test-control-plane-secret",
        token_pepper="test-token-pepper",
        index_repo_allowed_roots="",
    )
    assert settings.resolved_index_repo_allowed_roots() == (REPO_ROOT.resolve(),)
