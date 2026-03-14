from __future__ import annotations

import pytest

from viberecall_mcp.deployed_smoke import (
    SmokeConfig,
    SmokeContext,
    SmokeFailure,
    build_index_repo_source,
    ensure_profile_tools_available,
    resolve_profile_names,
    resolve_profile_token,
    run_core_profile,
)
from viberecall_mcp.tool_validation_matrix import SMOKE_PROFILE_DEFINITIONS


def test_resolve_profile_names_defaults_to_core() -> None:
    assert resolve_profile_names([]) == ("core",)


def test_resolve_profile_names_preserves_order_without_duplicates() -> None:
    assert resolve_profile_names(["core", "ops", "core", "graph"]) == ("core", "ops", "graph")


def test_resolve_profile_token_prefers_profile_specific_value() -> None:
    token = resolve_profile_token(
        "graph",
        shared_token="shared-token",
        profile_tokens={"graph": "graph-token"},
    )

    assert token == "graph-token"


def test_resolve_profile_token_falls_back_to_shared_token() -> None:
    token = resolve_profile_token(
        "ops",
        shared_token="shared-token",
        profile_tokens={},
    )

    assert token == "shared-token"


def test_resolve_profile_token_fails_when_profile_token_missing() -> None:
    with pytest.raises(SmokeFailure, match="Missing token for smoke profile 'resolution'"):
        resolve_profile_token("resolution", shared_token=None, profile_tokens={})


def test_ensure_profile_tools_available_reports_missing_tool_by_profile() -> None:
    with pytest.raises(SmokeFailure, match="Profile 'graph' is missing expected tools: viberecall_find_paths"):
        ensure_profile_tools_available(
            "graph",
            [
                "viberecall_search_entities",
                "viberecall_get_neighbors",
                "viberecall_explain_fact",
                "viberecall_resolve_reference",
            ],
        )


def test_build_index_repo_source_requires_all_index_fields() -> None:
    with pytest.raises(SmokeFailure, match="Index profile requires --index-repo-url, --index-ref, and --index-repo-name"):
        build_index_repo_source(repo_url=None, ref="main", repo_name="smoke-repo")


def test_build_index_repo_source_builds_git_source_payload() -> None:
    repo_source = build_index_repo_source(
        repo_url="https://example.com/smoke.git",
        ref="main",
        repo_name="smoke-repo",
    )

    assert repo_source == {
        "type": "git",
        "remote_url": "https://example.com/smoke.git",
        "ref": "main",
        "repo_name": "smoke-repo",
    }


def test_run_core_profile_rechecks_fact_after_pin(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    monkeypatch.setattr(
        "viberecall_mcp.deployed_smoke.list_tools",
        lambda context, token: list(SMOKE_PROFILE_DEFINITIONS["core"].tool_names),
    )

    def fake_tool_call(
        context,
        *,
        token: str,
        request_id: str,
        tool_name: str,
        arguments: dict,
        idempotency_key: str | None = None,
    ) -> dict:
        _ = (context, token, idempotency_key)
        calls.append((request_id, tool_name, arguments))
        if request_id == "core-save-episode":
            return {
                "ok": True,
                "result": {
                    "fact_group_id": "factgrp_core",
                    "fact_version_id": "factv_core",
                    "operation_id": "op_core",
                },
            }
        if request_id == "core-get-fact":
            return {
                "ok": True,
                "result": {
                    "current": {
                        "fact_group_id": "factgrp_core",
                        "fact_version_id": "factv_core",
                        "salience_class": "WARM",
                    }
                },
            }
        if request_id == "core-search-memory":
            return {
                "ok": True,
                "result": {
                    "facts": [
                        {
                            "fact_group_id": "factgrp_core",
                            "fact_version_id": "factv_core",
                            "salience_class": "WARM",
                        }
                    ]
                },
            }
        if request_id == "core-pin-memory":
            return {
                "ok": True,
                "result": {
                    "resolved_target": {
                        "fact_group_id": "factgrp_core",
                        "fact_version_id": "factv_core",
                    }
                },
            }
        if request_id == "core-get-fact-pinned":
            return {
                "ok": True,
                "result": {
                    "current": {
                        "fact_group_id": "factgrp_core",
                        "fact_version_id": "factv_core",
                        "salience_class": "PINNED",
                    }
                },
            }
        if request_id == "core-working-memory-patch":
            return {"ok": True, "result": {"status": "ok"}}
        if request_id == "core-working-memory-get":
            return {
                "ok": True,
                "result": {"state": {"active_constraints": {"profile": "core"}}},
            }
        if request_id == "core-save":
            return {
                "ok": True,
                "result": {
                    "episode_id": "ep_legacy",
                    "operation_id": "op_legacy",
                },
            }
        if request_id == "core-search":
            return {
                "ok": True,
                "result": {
                    "results": [
                        {
                            "kind": "fact",
                            "fact": {"id": "fact_legacy"},
                        }
                    ]
                },
            }
        if request_id == "core-get-facts":
            return {
                "ok": True,
                "result": {
                    "facts": [
                        {
                            "id": "fact_legacy",
                        }
                    ]
                },
            }
        if request_id == "core-update-fact":
            return {"ok": True, "result": {"operation_id": "op_update"}}
        if request_id == "core-timeline":
            return {
                "ok": True,
                "result": {
                    "episodes": [
                        {
                            "episode_id": "ep_legacy",
                        }
                    ]
                },
            }
        if request_id == "core-delete":
            return {"ok": True, "result": {"status": "DELETED"}}
        raise AssertionError(f"Unexpected smoke call: {request_id} {tool_name} {arguments}")

    monkeypatch.setattr("viberecall_mcp.deployed_smoke._tool_call", fake_tool_call)

    state: dict[str, object] = {"operation_ids": []}
    result = run_core_profile(
        SmokeContext(base_url="https://api.example.com", project_id="proj_smoke"),
        token="shared-token",
        config=SmokeConfig(
            profiles=("core",),
            shared_token="shared-token",
            profile_tokens={},
            query="production smoke test",
            tag="deploy-smoke",
            index_repo_source=None,
            index_timeout_seconds=90,
            poll_interval_seconds=2.0,
        ),
        state=state,
    )

    assert result["fact_group_id"] == "factgrp_core"
    assert ("core-get-fact-pinned", "viberecall_get_fact", {"fact_group_id": "factgrp_core"}) in calls
