from __future__ import annotations

from tests.support.mcp_harness import *
from viberecall_mcp import tool_handlers


def test_tool_handlers_facade_exports_runtime_surface() -> None:
    assert hasattr(tool_handlers, "handle_save")
    assert hasattr(tool_handlers, "handle_get_context_pack")
    assert hasattr(tool_handlers, "handle_find_paths")
    assert hasattr(tool_handlers, "settings")
    assert hasattr(tool_handlers, "request_index_repo")
    assert hasattr(tool_handlers, "get_task_queue")
    assert hasattr(tool_handlers, "attach_index_job_id")


def test_tools_list_returns_full_toolset_for_free_plan(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 200
    tools = parse_mcp_event(response)["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]
    assert tool_names == [
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
        "viberecall_get_context_pack",
        "viberecall_working_memory_get",
        "viberecall_working_memory_patch",
    ]
    assert all(tool.get("outputSchema") for tool in tools)


def test_tools_list_filters_tools_by_token_scope(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["memory:read"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "scope-tools", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 200
    tool_names = [tool["name"] for tool in parse_mcp_event(response)["result"]["tools"]]
    assert "viberecall_search_memory" in tool_names
    assert "viberecall_search_entities" in tool_names
    assert "viberecall_resolve_reference" in tool_names
    assert "viberecall_get_neighbors" in tool_names
    assert "viberecall_find_paths" in tool_names
    assert "viberecall_explain_fact" in tool_names
    assert "viberecall_get_context_pack" in tool_names
    assert "viberecall_get_operation" in tool_names
    assert "viberecall_save_episode" not in tool_names
    assert "viberecall_update_fact" not in tool_names
    assert "viberecall_pin_memory" not in tool_names
    assert "viberecall_delete_episode" not in tool_names
    assert "viberecall_index_repo" not in tool_names


def test_tools_list_includes_canonical_entity_search_for_entities_scope(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["entities:read"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "entities-tools", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 200
    tool_names = [tool["name"] for tool in parse_mcp_event(response)["result"]["tools"]]
    assert "viberecall_search_entities" in tool_names
    assert "viberecall_resolve_reference" in tool_names
    assert "viberecall_get_neighbors" not in tool_names
    assert "viberecall_find_paths" not in tool_names
    assert "viberecall_search_memory" not in tool_names


def test_tools_list_includes_graph_neighbors_for_graph_scope(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["graph:read"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "graph-tools", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 200
    tool_names = [tool["name"] for tool in parse_mcp_event(response)["result"]["tools"]]
    assert "viberecall_get_neighbors" in tool_names
    assert "viberecall_find_paths" in tool_names
    assert "viberecall_search_entities" not in tool_names
    assert "viberecall_search_memory" not in tool_names


def test_tools_list_includes_pin_memory_for_facts_write_scope(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["facts:write"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "facts-write-tools", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 200
    tool_names = [tool["name"] for tool in parse_mcp_event(response)["result"]["tools"]]
    assert "viberecall_pin_memory" in tool_names
    assert "viberecall_update_fact" in tool_names
    assert "viberecall_search_memory" not in tool_names


def test_tools_list_includes_resolution_tools_for_resolution_write_scope(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["resolution:write"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "resolution-write-tools", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 200
    tool_names = [tool["name"] for tool in parse_mcp_event(response)["result"]["tools"]]
    assert "viberecall_merge_entities" in tool_names
    assert "viberecall_split_entity" in tool_names
    assert "viberecall_resolve_reference" not in tool_names


def test_streamable_http_get_without_accept_returns_406(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        response = client.get("/p/proj_test/mcp")

    teardown_app()
    assert response.status_code == 406
    body = response.json()
    assert body["error"]["message"] == "Not Acceptable: Client must accept text/event-stream"


def test_streamable_http_unknown_session_returns_404(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        response = client.post(
            "/p/proj_test/mcp",
            headers={
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
                "mcp-session-id": "stale-session-id",
            },
            json={
                "jsonrpc": "2.0",
                "id": "init-stale",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
        )

    teardown_app()
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["message"] == "Session not found"


def test_streamable_http_v2_is_stateless(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        initialize = client.post(
            "/p/proj_test/mcp/v2",
            headers={"accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": "init-v2",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
        )
        tools = client.post(
            "/p/proj_test/mcp/v2",
            headers={
                "accept": "application/json, text/event-stream",
                "authorization": "Bearer test-token",
                "mcp-session-id": "ignored-by-stateless-v2",
            },
            json={"jsonrpc": "2.0", "id": "tools-v2", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert initialize.status_code == 200
    assert "mcp-session-id" not in {key.lower() for key in initialize.headers}
    assert tools.status_code == 200
    assert [tool["name"] for tool in parse_mcp_event(tools)["result"]["tools"]]


def test_streamable_http_v2_get_operation_serializes_datetimes(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def fake_get_operation_record(session, *, project_id: str, operation_id: str) -> dict | None:
        _ = session
        assert project_id == "proj_test"
        assert operation_id == "op_test"
        now = datetime(2026, 3, 8, 16, 0, tzinfo=timezone.utc)
        return {
            "operation_id": operation_id,
            "project_id": project_id,
            "token_id": "tok_test",
            "request_id": "req_test",
            "kind": "save",
            "status": "SUCCEEDED",
            "resource_type": "episode",
            "resource_id": "ep_test",
            "job_id": "job_test",
            "metadata_json": {
                "reference_time": "2026-03-08T15:59:00Z",
                "provider_trace": {"sync_status": "succeeded", "provider": "openai"},
            },
            "result_json": {"episode_id": "ep_test", "status": "SUCCEEDED"},
            "error_json": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": now,
        }

    monkeypatch.setattr(tool_handlers, "get_operation_record", fake_get_operation_record)

    with TestClient(create_app()) as client:
        response = client.post(
            "/p/proj_test/mcp/v2",
            headers={
                "accept": "application/json, text/event-stream",
                "authorization": "Bearer test-token",
            },
            json={
                "jsonrpc": "2.0",
                "id": "op-v2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_operation",
                    "arguments": {"operation_id": "op_test"},
                },
            },
        )

    teardown_app()
    body = parse_mcp_event(response)
    payload = parse_result(response)
    assert payload["ok"] is True
    assert body["result"]["structuredContent"]["result"]["operation"]["operation_type"] == "save"
    operation = payload["result"]["operation"]
    assert operation["request_id"] == "req_test"
    assert operation["operation_type"] == "save"
    assert operation["retryable"] is False
    assert operation["metadata"]["provider_trace"]["sync_status"] == "succeeded"
    assert operation["created_at"] == "2026-03-08T16:00:00+00:00"
    assert operation["completed_at"] == "2026-03-08T16:00:00+00:00"


def test_missing_scope_blocks_get_facts(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=[]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "viberecall_get_facts", "arguments": {}},
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "FORBIDDEN"
    assert payload["error"]["details"]["required_scope"] == "memory:read"
def test_malformed_cursor_returns_invalid_argument(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "6",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "auth", "cursor": "not-a-cursor"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_protocol_version_mismatch_returns_http_400(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"MCP-Protocol-Version": "2024-01-01"}),
            json={"jsonrpc": "2.0", "id": "7", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 400


def test_payload_too_large_returns_http_413(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        monkeypatch.setattr(mcp_transport.settings, "max_payload_bytes", 1)
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "8", "method": "tools/list", "params": {}},
        )

    teardown_app()
    if response.status_code == 413:
        return
    assert response.status_code == 200
    body = parse_mcp_event(response)
    assert "error" in body
    assert "payload" in str(body["error"]).lower()
def test_tool_error_returns_payload_even_when_error_audit_fails(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    async def fake_timeline_failure(*_args, **_kwargs):
        raise ValueError("timeline query failed")

    async def fake_audit_with_error(*_args, **kwargs) -> None:
        if kwargs.get("action") == "tools/call" and kwargs.get("status") == "error":
            raise RuntimeError("audit insert failed")
        return None

    monkeypatch.setattr(tool_handlers, "list_timeline_episodes", fake_timeline_failure)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit_with_error)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "timeline-fail-1",
                "method": "tools/call",
                "params": {"name": "viberecall_timeline", "arguments": {"limit": 20}},
            },
        )

    teardown_app()
    assert response.status_code == 200
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_tool_success_returns_payload_even_when_success_audit_fails(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    async def fake_audit_with_error(*_args, **kwargs) -> None:
        if kwargs.get("action") == "tools/call" and kwargs.get("status") == "ok":
            raise RuntimeError("audit insert failed on success path")
        return None

    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit_with_error)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "timeline-ok-1",
                "method": "tools/call",
                "params": {"name": "viberecall_timeline", "arguments": {"limit": 20}},
            },
        )

    teardown_app()
    assert response.status_code == 200
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["episodes"] == []


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "tool_call_latency_ms" in response.text
