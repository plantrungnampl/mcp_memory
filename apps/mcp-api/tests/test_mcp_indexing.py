from __future__ import annotations

import pytest

from tests.support.mcp_harness import *


@pytest.fixture(autouse=True)
def enable_remote_git_indexing_for_legacy_tests(monkeypatch) -> None:
    monkeypatch.setattr(code_index.settings, "index_remote_git_enabled", True)


def test_free_plan_index_and_context_pack_flow(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_test"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "mini-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "api.ts").write_text(
        "\n".join(
            [
                "import { readFileSync } from 'node:fs'",
                "",
                "export function buildContextPack(query: string) {",
                "  return readFileSync(query, 'utf-8')",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_dir / "worker.py").write_text(
        "\n".join(
            [
                "from typing import Any",
                "",
                "def index_repo(path: str) -> dict[str, Any]:",
                "    return {'path': path}",
            ]
        ),
        encoding="utf-8",
    )
    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        index_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/mini-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )
        index_payload = parse_result(index_response)
        assert index_payload["ok"] is True
        assert index_payload["result"]["accepted"] is True
        assert index_payload["result"]["index_run_id"].startswith("idx_test_")
        assert index_payload["result"]["job_id"].startswith("job_index_test_")

        search_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "index_repo", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_response)
        assert search_payload["ok"] is True
        assert search_payload["result"]["status"] == "READY"
        assert search_payload["result"]["entities"] == []

        pack_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "3",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )
        pack_payload = parse_result(pack_response)
        assert pack_payload["ok"] is True
        assert pack_payload["result"]["status"] == "READY"
        assert "architecture_map" in pack_payload["result"]
        assert isinstance(pack_payload["result"]["citations"], list)

        status_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "4",
                "method": "tools/call",
                "params": {"name": "viberecall_index_status", "arguments": {}},
            },
        )
        status_payload = parse_result(status_response)
        assert status_payload["ok"] is True
        assert status_payload["result"]["status"] == "READY"
        assert status_payload["result"]["latest_ready_snapshot"]["stats"]["file_count"] >= 2
        assert not (REPO_ROOT / ".viberecall" / f"index-state-{project_id}.json").exists()

    teardown_app()


def test_index_repo_returns_conflict_while_run_is_active(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_conflict"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "conflict-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    class PendingQueue:
        async def enqueue_index_repo(
            self,
            *,
            index_id: str,
            project_id: str,
            request_id: str,
            token_id: str | None,
            operation_id: str | None = None,
        ):
            _ = (index_id, project_id, request_id, token_id, operation_id)
            return "job_index_pending"

    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: PendingQueue())

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        first = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "conflict-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/conflict-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "conflict-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/conflict-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "CONFLICT"


def test_get_index_status_accepts_project_scoped_index_run_id(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_status_by_id"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "status-by-id-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        accepted = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "status-by-id-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/status-by-id-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )
        accepted_payload = parse_result(accepted)
        status = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "status-by-id-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_index_status",
                    "arguments": {"index_run_id": accepted_payload["result"]["index_run_id"]},
                },
            },
        )

    teardown_app()
    status_payload = parse_result(status)
    assert status_payload["ok"] is True
    assert status_payload["result"]["status"] == "READY"
    assert status_payload["result"]["current_run"]["index_run_id"] == accepted_payload["result"]["index_run_id"]
    assert status_payload["result"]["latest_ready_snapshot"]["index_run_id"] == accepted_payload["result"]["index_run_id"]


def test_index_repo_rejects_legacy_repo_path_arguments(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_legacy_args"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "legacy-args-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "legacy-args",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "FULL_SNAPSHOT"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_index_repo_rejects_non_full_snapshot_mode(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_bad_mode"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "bad-mode-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "zero-diff",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/bad-mode-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "DIFF",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_search_and_context_pack_ignore_queued_run(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_latest_ready_only"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    repo_dir = seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)
    (repo_dir / "new-module.ts").write_text("export function futureSymbol() { return 1 }\n", encoding="utf-8")

    class PendingQueue:
        async def enqueue_index_repo(
            self,
            *,
            index_id: str,
            project_id: str,
            request_id: str,
            token_id: str | None,
            operation_id: str | None = None,
        ):
            _ = (index_id, project_id, request_id, token_id, operation_id)
            return "job_index_pending"

    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: PendingQueue())

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        accepted = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-index",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/latest-ready-only.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )
        search_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "futureSymbol", "limit": 10},
                },
            },
        )
        pack_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-pack",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "futureSymbol", "limit": 5},
                },
            },
        )
        status_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-status",
                "method": "tools/call",
                "params": {"name": "viberecall_index_status", "arguments": {}},
            },
        )

    teardown_app()
    accepted_payload = parse_result(accepted)
    search_payload = parse_result(search_response)
    pack_payload = parse_result(pack_response)
    status_payload = parse_result(status_response)
    assert accepted_payload["ok"] is True
    assert accepted_payload["result"]["accepted"] is True
    assert search_payload["result"]["status"] == "READY"
    assert search_payload["result"]["entities"] == []
    assert pack_payload["result"]["status"] == "READY"
    assert pack_payload["result"]["citations"] == []
    assert status_payload["result"]["status"] == "QUEUED"
    assert status_payload["result"]["latest_ready_snapshot"]["stats"]["file_count"] >= 2


def test_failed_index_run_keeps_latest_ready_snapshot(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_failed_keeps_ready"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)

    repo_dir = tmp_path / "broken-index-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    original_build_file_rows = code_index._build_file_rows

    def explode_file_rows(repo_path: Path, file_paths: list[Path]) -> list[dict]:
        if repo_path == repo_dir.resolve():
            raise RuntimeError("boom")
        return original_build_file_rows(repo_path, file_paths)

    monkeypatch.setattr(code_index, "_build_file_rows", explode_file_rows)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "failed-diff",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/broken-index-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )
        status_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "failed-diff-status",
                "method": "tools/call",
                "params": {"name": "viberecall_index_status", "arguments": {}},
            },
        )

    teardown_app()
    payload = parse_result(response)
    status_payload = parse_result(status_response)
    assert payload["ok"] is False
    assert status_payload["result"]["status"] == "FAILED"
    assert status_payload["result"]["current_run"]["error"]
    assert status_payload["result"]["latest_ready_snapshot"]["stats"]["file_count"] >= 2


def test_get_context_pack_rate_limit_enforced(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_context_rate"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_token_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_project_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_window_seconds", 60)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        first = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "context-rate-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "context-rate-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"


def test_index_repo_rate_limit_enforced(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_rate"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_token_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_project_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_window_seconds", 60)

    repo_dir = tmp_path / "rate-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def index_repo(path: str):\n    return path\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        first = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "index-rate-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/rate-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "index-rate-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/rate-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"


def test_get_context_pack_loads_index_state_once(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_context_cache"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "context-cache-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "READY"
    assert payload["result"]["architecture_map"]["summary"]["file_count"] >= 2


def test_get_context_pack_prefers_high_salience_timeline_matches(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def fake_build_context_pack(*, session, project_id: str, query: str, limit: int) -> dict:
        _ = (session, project_id, query, limit)
        return {
            "status": "READY",
            "query": query,
            "architecture_map": {
                "indexed_at": None,
                "repo_path": None,
                "summary": {
                    "file_count": 0,
                    "symbol_count": 0,
                    "entity_count": 0,
                    "relationship_count": 0,
                    "chunk_count": 0,
                },
                "top_modules": [],
                "top_files": [],
            },
            "relevant_symbols": [],
            "citations": [],
        }

    async def fake_list_timeline(session, *, project_id: str, from_time, to_time, limit: int, offset: int) -> list[dict]:
        _ = (session, project_id, from_time, to_time, limit, offset)
        return [
            {
                "episode_id": "ep_warm_newer",
                "reference_time": "2026-03-10T10:00:00Z",
                "ingested_at": "2026-03-10T10:01:00Z",
                "summary": "Auth callback regression triage",
                "metadata": {"type": "note"},
                "salience_score": 0.5,
                "salience_class": "WARM",
            },
            {
                "episode_id": "ep_pinned_older",
                "reference_time": "2026-03-09T10:00:00Z",
                "ingested_at": "2026-03-09T10:01:00Z",
                "summary": "Auth callback regression root cause",
                "metadata": {"type": "decision"},
                "salience_score": 1.0,
                "salience_class": "PINNED",
            },
        ]

    monkeypatch.setattr(tool_handlers, "build_context_pack", fake_build_context_pack)
    monkeypatch.setattr(tool_handlers, "list_timeline_episodes", fake_list_timeline)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "context-salience",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "auth callback", "limit": 2},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["facts_timeline"][0]["episode_id"] == "ep_pinned_older"
    assert payload["result"]["facts_timeline"][1]["episode_id"] == "ep_warm_newer"


def test_index_repo_rejects_paths_outside_allowlist(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_blocked"
    setup_app(monkeypatch, make_token(plan="pro", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(REPO_ROOT))

    repo_dir = tmp_path / "blocked-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def blocked() -> None:\n    return None\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "blocked-index",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_source": {
                            "type": "git",
                            "remote_url": "https://example.com/blocked-repo.git",
                            "ref": "main",
                            "repo_name": str(repo_dir),
                        },
                        "mode": "FULL_SNAPSHOT",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
