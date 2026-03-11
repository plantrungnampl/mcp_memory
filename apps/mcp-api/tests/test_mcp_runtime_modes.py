from __future__ import annotations

from tests.support.mcp_harness import *


def test_celery_queue_path_surfaces_task_ids_over_mcp_http(monkeypatch) -> None:
    episode_store = {}
    setup_app_celery_transport(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-celery-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "celery-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "Queue save through celery transport path",
                        "metadata": {"tags": ["queue", "celery"]},
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        assert save_payload["result"]["enrichment"]["job_id"] == "celery-ingest-http-1"

        episode_id = save_payload["result"]["episode_id"]
        assert episode_store[episode_id]["job_id"] == "celery-ingest-http-1"

        update_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-celery-2"}),
            json={
                "jsonrpc": "2.0",
                "id": "celery-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_update_fact",
                    "arguments": {
                        "fact_id": "fact_existing",
                        "new_text": "Update fact asynchronously with celery",
                        "effective_time": "2026-02-28T15:00:00Z",
                    },
                },
            },
        )
        update_payload = parse_result(update_response)
        assert update_payload["ok"] is True
        assert update_payload["result"]["job_id"] == "celery-update-http-1"
        assert update_payload["result"]["old_fact"]["id"] == "fact_existing"

    teardown_app()
def test_get_status_available_for_free_plan(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "status-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_status",
                    "arguments": {},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["service"] == "viberecall-mcp"
    assert payload["result"]["project_id"] == "proj_test"
    assert "backends" in payload["result"]


def test_get_status_reports_degraded_graph_dependency(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)
    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "graphiti_api_key", "test-key")

    async def fake_graph_dependency_failure_detail() -> str | None:
        return (
            "Graph dependency check failed for memory backend 'graphiti': "
            "Error 111 connecting to localhost:6380. Connection refused."
        )

    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "status-degraded-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_status",
                    "arguments": {},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "degraded"
    assert "localhost:6380" in payload["result"]["graphiti"]["detail"]


def test_save_returns_upstream_error_before_side_effects_when_graph_dependency_unavailable(
    monkeypatch,
) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)
    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "raw_episode_inline_max_bytes", 32)

    async def fake_graph_dependency_failure_detail() -> str | None:
        return (
            "Graph dependency check failed for memory backend 'graphiti': "
            "Error 111 connecting to localhost:6380. Connection refused."
        )

    put_calls = {"count": 0}

    async def fake_put_text(*, object_key: str, content: str) -> None:
        _ = (object_key, content)
        put_calls["count"] += 1

    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )
    monkeypatch.setattr(tool_handlers, "put_text", fake_put_text)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-degraded-save"}),
            json={
                "jsonrpc": "2.0",
                "id": "save-degraded-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "A" * 128,
                        "metadata": {"tags": ["dependency-check"]},
                    },
                },
            },
    )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["accepted"] is True
    assert episode_store != {}
    assert put_calls["count"] == 1


def test_search_returns_upstream_error_when_graph_dependency_unavailable(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)
    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")

    async def fake_graph_dependency_failure_detail() -> str | None:
        return (
            "Graph dependency check failed for memory backend 'graphiti': "
            "Error 111 connecting to localhost:6380. Connection refused."
        )

    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-degraded-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "auth middleware", "limit": 10},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UPSTREAM_ERROR"
    assert "localhost:6380" in payload["error"]["message"]
def test_upstream_bridge_mode_routes_search_facts_timeline(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "graphiti_mcp_bridge_mode", "upstream_bridge")
    monkeypatch.setattr(tool_handlers.settings, "graphiti_api_key", "test-key")

    async def fake_graph_dependency_failure_detail() -> str | None:
        return None

    class FakeBridge:
        async def search_facts(self, *_args, **_kwargs):
            return [
                {
                    "kind": "fact",
                    "fact": {
                        "id": "fact_bridge_1",
                        "text": "Bridge fact result",
                        "valid_at": "2026-03-02T10:00:00Z",
                        "invalid_at": None,
                    },
                    "entities": [{"id": "ent_bridge_1", "type": "Entity", "name": "BridgeEntity"}],
                    "provenance": {
                        "episode_ids": ["ep_bridge_1"],
                        "reference_time": "2026-03-02T10:00:00Z",
                        "ingested_at": "2026-03-02T10:01:00Z",
                    },
                    "score": 0.88,
                }
            ]

        async def list_facts(self, *_args, **_kwargs):
            return [
                {
                    "id": "fact_bridge_1",
                    "text": "Bridge fact result",
                    "valid_at": "2026-03-02T10:00:00Z",
                    "invalid_at": None,
                    "entities": [{"id": "ent_bridge_1", "type": "Entity", "name": "BridgeEntity"}],
                    "provenance": {"episode_ids": ["ep_bridge_1"]},
                    "ingested_at": "2026-03-02T10:01:00Z",
                }
            ]

        async def list_timeline(self, *_args, **_kwargs):
            return [
                {
                    "episode_id": "ep_bridge_1",
                    "reference_time": "2026-03-02T10:00:00Z",
                    "ingested_at": "2026-03-02T10:01:00Z",
                    "summary": "Bridge timeline episode",
                    "metadata": {"source": "text", "source_description": "bridge"},
                }
            ]

    monkeypatch.setattr(tool_handlers, "get_graphiti_upstream_bridge", lambda: FakeBridge())
    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        search_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "bridge-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "bridge", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_response)
        assert search_payload["ok"] is True
        assert search_payload["result"]["results"][0]["fact"]["id"] == "fact_bridge_1"

        facts_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "bridge-facts",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"limit": 10},
                },
            },
        )
        facts_payload = parse_result(facts_response)
        assert facts_payload["ok"] is True
        assert facts_payload["result"]["facts"][0]["id"] == "fact_bridge_1"

        timeline_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "bridge-timeline",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_timeline",
                    "arguments": {"limit": 10},
                },
            },
        )
        timeline_payload = parse_result(timeline_response)
        assert timeline_payload["ok"] is True
        assert timeline_payload["result"]["episodes"][0]["episode_id"] == "ep_bridge_1"

    teardown_app()
