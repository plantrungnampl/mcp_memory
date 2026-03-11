from __future__ import annotations

from tests.support.mcp_harness import *


def test_search_rate_limit_enforced(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_token_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_project_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_window_seconds", 60)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        first = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-rate-1",
                "method": "tools/call",
                "params": {"name": "viberecall_search", "arguments": {"query": "missing"}},
            },
        )
        second = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-rate-2",
                "method": "tools/call",
                "params": {"name": "viberecall_search", "arguments": {"query": "missing"}},
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"
def test_save_search_timeline_and_update_fact_flow(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "Fix auth middleware bug in login flow",
                        "metadata": {
                            "type": "bugfix",
                            "repo": "viberecall",
                            "files": ["apps/web/src/proxy.ts"],
                            "tags": ["auth"],
                        },
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        episode_id = save_payload["result"]["episode_id"]
        assert episode_id in episode_store

        search_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "auth middleware", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_response)
        assert search_payload["ok"] is True
        first_result = search_payload["result"]["results"][0]
        assert first_result["kind"] == "fact"
        assert search_payload["result"]["scope_applied"] == "project"
        assert search_payload["result"]["scope_requested"] == "project"
        assert isinstance(search_payload["result"]["seeds"], list)
        assert isinstance(search_payload["result"]["expanded_entities"], list)

        facts_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "3",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"filters": {"tag": "auth"}, "limit": 20},
                },
            },
        )
        facts_payload = parse_result(facts_response)
        assert facts_payload["ok"] is True
        fact_id = facts_payload["result"]["facts"][0]["id"]

        timeline_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "4",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_timeline",
                    "arguments": {"limit": 20},
                },
            },
        )
        timeline_payload = parse_result(timeline_response)
        assert timeline_payload["ok"] is True
        assert timeline_payload["result"]["episodes"][0]["episode_id"] == episode_id

        update_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-2"}),
            json={
                "jsonrpc": "2.0",
                "id": "5",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_update_fact",
                    "arguments": {
                        "fact_id": fact_id,
                        "new_text": "Fix auth middleware race in login callback flow",
                        "effective_time": "2026-02-28T14:00:00Z",
                        "reason": "narrowed root cause",
                    },
                },
            },
        )
        update_payload = parse_result(update_response)
        assert update_payload["ok"] is True
        assert update_payload["result"]["old_fact"]["id"] == fact_id

    teardown_app()


def test_v3_canonical_save_get_fact_search_and_update_flow(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-v3-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "v3-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {
                        "content": "Document Graph Playground rollout constraints",
                        "metadata": {
                            "type": "decision",
                            "repo": "viberecall",
                            "files": ["apps/web/src/components/projects/graph-playground-panel.tsx"],
                            "tags": ["graph", "ui"],
                        },
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        fact_group_id = save_payload["result"]["fact_group_id"]
        fact_version_id = save_payload["result"]["fact_version_id"]
        assert save_payload["result"]["accepted"] is True

        get_fact_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "v3-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_fact",
                    "arguments": {"fact_group_id": fact_group_id},
                },
            },
        )
        get_fact_payload = parse_result(get_fact_response)
        assert get_fact_payload["ok"] is True
        assert get_fact_payload["result"]["current"]["fact_version_id"] == fact_version_id

        search_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "v3-3",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_memory",
                    "arguments": {"query": "Graph Playground", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_response)
        assert search_payload["ok"] is True
        assert search_payload["result"]["facts"][0]["fact_group_id"] == fact_group_id
        assert search_payload["result"]["snapshot_token"]

        update_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-v3-2"}),
            json={
                "jsonrpc": "2.0",
                "id": "v3-4",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_update_fact",
                    "arguments": {
                        "fact_group_id": fact_group_id,
                        "expected_current_version_id": fact_version_id,
                        "statement": "Document Graph Playground rollout constraints and fallback behavior",
                        "effective_time": "2026-03-09T10:00:00Z",
                        "reason": "tightened rollout note",
                    },
                },
            },
        )
        update_payload = parse_result(update_response)
        assert update_payload["ok"] is True
        assert update_payload["result"]["fact_group_id"] == fact_group_id
        assert update_payload["result"]["new_fact_version_id"] != fact_version_id

    teardown_app()
def test_search_memory_prefers_exact_match_over_pinned_fuzzy_match(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        exact_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-exact-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {"content": "auth"},
                },
            },
        )
        fuzzy_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-fuzzy-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {"content": "auth callback regression"},
                },
            },
        )
        exact_payload = parse_result(exact_response)
        fuzzy_payload = parse_result(fuzzy_response)
        assert exact_payload["ok"] is True
        assert fuzzy_payload["ok"] is True

        pin_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-fuzzy-pin",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_pin_memory",
                    "arguments": {
                        "target_kind": "FACT",
                        "target_id": fuzzy_payload["result"]["fact_group_id"],
                        "pin_action": "PIN",
                    },
                },
            },
        )
        assert parse_result(pin_response)["ok"] is True

        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-exact-vs-pinned",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_memory",
                    "arguments": {"query": "auth", "limit": 10},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["facts"][0]["fact_group_id"] == exact_payload["result"]["fact_group_id"]
    assert payload["result"]["facts"][1]["fact_group_id"] == fuzzy_payload["result"]["fact_group_id"]
    assert payload["result"]["facts"][1]["salience_class"] == "PINNED"


def test_search_memory_boosts_and_filters_by_salience_class(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        first_save = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-salience-save-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {"content": "shared salience query"},
                },
            },
        )
        second_save = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-salience-save-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {"content": "shared salience query"},
                },
            },
        )
        first_payload = parse_result(first_save)
        second_payload = parse_result(second_save)
        assert first_payload["ok"] is True
        assert second_payload["ok"] is True

        pin_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-salience-pin",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_pin_memory",
                    "arguments": {
                        "target_kind": "FACT",
                        "target_id": first_payload["result"]["fact_group_id"],
                        "pin_action": "PIN",
                    },
                },
            },
        )
        assert parse_result(pin_response)["ok"] is True

        boosted_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-salience-boosted",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_memory",
                    "arguments": {"query": "shared salience query", "limit": 10},
                },
            },
        )
        filtered_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-salience-filtered",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_memory",
                    "arguments": {
                        "query": "shared salience query",
                        "limit": 10,
                        "filters": {"salience_classes": ["PINNED"]},
                    },
                },
            },
        )

    teardown_app()
    boosted_payload = parse_result(boosted_response)
    filtered_payload = parse_result(filtered_response)
    assert boosted_payload["ok"] is True
    assert filtered_payload["ok"] is True
    assert boosted_payload["result"]["facts"][0]["fact_group_id"] == first_payload["result"]["fact_group_id"]
    assert boosted_payload["result"]["facts"][0]["salience_class"] == "PINNED"
    assert [fact["fact_group_id"] for fact in filtered_payload["result"]["facts"]] == [first_payload["result"]["fact_group_id"]]
    assert all(fact["salience_class"] == "PINNED" for fact in filtered_payload["result"]["facts"])
def test_pin_memory_rejects_invalid_target_kind(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "pin-invalid-kind",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_pin_memory",
                    "arguments": {
                        "target_kind": "THREAD",
                        "target_id": "factgrp_1",
                        "pin_action": "PIN",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert payload["error"]["details"]["target_kind"] == "THREAD"


def test_pin_memory_rejects_invalid_pin_action(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "pin-invalid-action",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_pin_memory",
                    "arguments": {
                        "target_kind": "FACT",
                        "target_id": "factgrp_1",
                        "pin_action": "BOOST",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert payload["error"]["details"]["pin_action"] == "BOOST"


def test_pin_memory_returns_not_found_for_missing_target(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "pin-not-found",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_pin_memory",
                    "arguments": {
                        "target_kind": "FACT",
                        "target_id": "missing-fact",
                        "pin_action": "PIN",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["details"]["target_kind"] == "FACT"
    assert payload["error"]["details"]["target_id"] == "missing-fact"


def test_pin_memory_returns_structured_payload(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def fake_pin(**kwargs):
        _ = kwargs
        return {
            "target_kind": "FACT",
            "target_id": "factgrp_auth",
            "resolved_target": {
                "fact_group_id": "factgrp_auth",
                "fact_version_id": "factv_auth_current",
            },
            "pin_action": "UNPIN",
            "salience_state": {
                "salience_score": 0.5,
                "salience_class": "WARM",
                "manual_override": False,
                "reason": "baseline restored",
                "updated_at": "2026-03-10T11:00:00Z",
            },
            "updated_at": "2026-03-10T11:00:00Z",
        }

    monkeypatch.setattr(tool_handlers, "pin_canonical_memory", fake_pin)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "pin-structured",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_pin_memory",
                    "arguments": {
                        "target_kind": "FACT",
                        "target_id": "factgrp_auth",
                        "pin_action": "UNPIN",
                        "reason": "baseline restored",
                    },
                },
            },
        )

    teardown_app()
    body = parse_mcp_event(response)
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["resolved_target"]["fact_version_id"] == "factv_auth_current"
    assert payload["result"]["salience_state"]["salience_class"] == "WARM"
    assert body["result"]["structuredContent"]["result"]["salience_state"]["manual_override"] is False
def test_working_memory_patch_and_get_flow(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        patch_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "wm-patch-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_working_memory_patch",
                    "arguments": {
                        "task_id": "task_auth_bug",
                        "session_id": "sess_123",
                        "patch": {
                            "plan": ["inspect auth redirect", "verify middleware matcher"],
                            "active_constraints": {"repo": "apps/web"},
                        },
                        "checkpoint_note": "seeded plan",
                    },
                },
            },
        )
        patch_payload = parse_result(patch_response)
        assert patch_payload["ok"] is True
        assert patch_payload["result"]["status"] == "READY"
        assert patch_payload["result"]["state"]["active_constraints"]["repo"] == "apps/web"

        get_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "wm-get-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_working_memory_get",
                    "arguments": {
                        "task_id": "task_auth_bug",
                        "session_id": "sess_123",
                    },
                },
            },
        )
        get_payload = parse_result(get_response)
        assert get_payload["ok"] is True
        assert get_payload["result"]["status"] == "READY"
        assert get_payload["result"]["state"]["plan"] == [
            "inspect auth redirect",
            "verify middleware matcher",
        ]


def test_search_memory_rejects_snapshot_token_mismatch(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "snapshot-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {"content": "Snapshot token test"},
                },
            },
        )
        assert parse_result(save_response)["ok"] is True

        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "snapshot-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_memory",
                    "arguments": {
                        "query": "snapshot",
                        "snapshot_token": "bad-token",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert payload["error"]["details"]["snapshot_token"] == "bad-token"


def test_search_pagination_keeps_mixed_fact_and_episode_results_stable(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    fact_results = [
        {
            "kind": "fact",
            "fact": {"id": "fact_4", "text": "fact 4", "valid_at": "2026-03-06T00:00:04Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:04Z"},
            "score": 0.3,
        },
        {
            "kind": "fact",
            "fact": {"id": "fact_3", "text": "fact 3", "valid_at": "2026-03-06T00:00:03Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:03Z"},
            "score": 0.3,
        },
        {
            "kind": "fact",
            "fact": {"id": "fact_2", "text": "fact 2", "valid_at": "2026-03-06T00:00:02Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:02Z"},
            "score": 0.3,
        },
        {
            "kind": "fact",
            "fact": {"id": "fact_1", "text": "fact 1", "valid_at": "2026-03-06T00:00:01Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:01Z"},
            "score": 0.3,
        },
    ]
    recent_episodes = [
        {
            "episode_id": "ep_recent",
            "reference_time": None,
            "ingested_at": "2026-03-06T00:01:00Z",
            "summary": "repeat me once",
            "metadata": {},
        }
    ]

    class FakeMemoryCore:
        async def search(self, project_id, query, filters, sort, limit, offset):  # noqa: ANN001
            assert project_id == "proj_test"
            return fact_results[offset : offset + limit]

    async def fake_recent_raw(
        session,
        *,
        project_id: str,
        query: str,
        window_seconds: int,
        limit: int,
        offset: int,
    ) -> list[dict]:
        assert project_id == "proj_test"
        return recent_episodes[offset : offset + limit]

    monkeypatch.setattr(tool_handlers, "get_memory_core", lambda: FakeMemoryCore())
    monkeypatch.setattr(tool_handlers, "list_recent_raw_episodes", fake_recent_raw)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        page1 = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-page-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "repeat", "limit": 2},
                },
            },
        )
        page1_payload = parse_result(page1)
        page1_results = page1_payload["result"]["results"]
        assert [item["kind"] for item in page1_results] == ["episode", "fact"]
        assert page1_results[0]["episode"]["episode_id"] == "ep_recent"
        assert page1_results[1]["fact"]["id"] == "fact_4"
        assert page1_payload["result"]["next_cursor"] is not None

        page2 = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-page-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {
                        "query": "repeat",
                        "limit": 2,
                        "cursor": page1_payload["result"]["next_cursor"],
                    },
                },
            },
        )
        page2_payload = parse_result(page2)
        page2_results = page2_payload["result"]["results"]
        assert [item["kind"] for item in page2_results] == ["fact", "fact"]
        assert [item["fact"]["id"] for item in page2_results] == ["fact_3", "fact_2"]

    teardown_app()


def test_save_large_content_uses_content_ref(monkeypatch) -> None:
    episode_store = {}
    setup_app_celery_transport(monkeypatch, make_token(), episode_store)
    monkeypatch.setattr(tool_handlers.settings, "raw_episode_inline_max_bytes", 1024)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        large_content = "A" * 2048
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-large-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "save-large",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {"content": large_content, "metadata": {"tags": ["large"]}},
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        episode_id = save_payload["result"]["episode_id"]
        stored = episode_store[episode_id]
        assert stored["content"] is None
        assert stored["content_ref"] == f"projects/proj_test/episodes/{episode_id}.txt"

    teardown_app()
def test_save_uses_rate_limit_and_keeps_quota_non_blocking(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)
    rate_limit_calls: list[tuple[str, int, int]] = []

    async def fake_monthly_vibe_tokens(*_args, **_kwargs):
        return 100_000

    class FakeLimiter:
        async def check(self, key: str, *, capacity: int, window_seconds: int):
            rate_limit_calls.append((key, capacity, window_seconds))
            return SimpleNamespace(allowed=True, reset_at="2026-03-08T00:00:00Z")

    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(tool_handlers, "get_rate_limiter", lambda: FakeLimiter())

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "9",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {"content": "quota-test"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "ACCEPTED"
    assert len(rate_limit_calls) == 2
    assert rate_limit_calls[0][0].startswith("token:tok_test:viberecall_save")
    assert rate_limit_calls[1][0].startswith("project:proj_test:viberecall_save")
def test_delete_episode_full_delete_and_idempotent(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-del-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "del-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "Episode to delete",
                        "metadata": {"tags": ["cleanup"]},
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        episode_id = save_payload["result"]["episode_id"]

        facts_before = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-facts-before",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"filters": {"tag": "cleanup"}, "limit": 20},
                },
            },
        )
        facts_before_payload = parse_result(facts_before)
        assert facts_before_payload["ok"] is True
        fact_id = facts_before_payload["result"]["facts"][0]["id"]

        update_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-del-update-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "del-update",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_update_fact",
                    "arguments": {
                        "fact_id": fact_id,
                        "new_text": "Episode to delete updated",
                        "effective_time": "2026-03-08T05:00:00Z",
                        "reason": "delete regression coverage",
                    },
                },
            },
        )
        update_payload = parse_result(update_response)
        assert update_payload["ok"] is True

        delete_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": episode_id},
                },
            },
        )
        delete_payload = parse_result(delete_response)
        assert delete_payload["ok"] is True
        assert delete_payload["result"]["status"] == "DELETED"
        assert delete_payload["result"]["deleted"]["postgres"] is True

        timeline_after = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-timeline",
                "method": "tools/call",
                "params": {"name": "viberecall_timeline", "arguments": {"limit": 20}},
            },
        )
        timeline_payload = parse_result(timeline_after)
        assert timeline_payload["ok"] is True
        assert timeline_payload["result"]["episodes"] == []

        search_after = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "Episode to delete", "limit": 20},
                },
            },
        )
        search_payload = parse_result(search_after)
        assert search_payload["ok"] is True
        assert search_payload["result"]["results"] == []

        facts_after = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-facts",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"filters": {"tag": "cleanup"}, "limit": 20},
                },
            },
        )
        facts_payload = parse_result(facts_after)
        assert facts_payload["ok"] is True
        assert facts_payload["result"]["facts"] == []

        delete_again = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": episode_id},
                },
            },
        )
        delete_again_payload = parse_result(delete_again)
        assert delete_again_payload["ok"] is True
        assert delete_again_payload["result"]["status"] == "NOT_FOUND"


def test_free_plan_can_call_delete_episode(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-free-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": "ep_missing"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "NOT_FOUND"


def test_delete_episode_returns_upstream_error_when_canonical_cleanup_incomplete(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    calls = {"delete_row": 0, "delete_object": 0}

    class FakeMemoryCore:
        async def delete_episode(self, project_id: str, *, episode_id: str) -> DeleteEpisodeResult:
            assert project_id == "proj_test"
            assert episode_id == "ep_partial"
            return DeleteEpisodeResult(
                found=True,
                deleted_episode_node=False,
                deleted_fact_count=0,
                updated_fact_count=0,
                remaining_fact_count=2,
            )

    async def fake_get_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        assert project_id == "proj_test"
        assert episode_id == "ep_partial"
        return {
            "episode_id": episode_id,
            "project_id": project_id,
            "content_ref": "objects/ep_partial.txt",
        }

    async def fake_delete_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        calls["delete_row"] += 1
        return None

    async def fake_delete_object(*, object_key: str) -> bool:
        calls["delete_object"] += 1
        return True

    monkeypatch.setattr(tool_handlers, "get_memory_core", lambda: FakeMemoryCore())
    monkeypatch.setattr(tool_handlers, "get_episode_for_project", fake_get_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_episode_for_project", fake_delete_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_object", fake_delete_object)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-partial-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": "ep_partial"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UPSTREAM_ERROR"
    assert payload["error"]["details"]["remaining_fact_count"] == 2
    assert calls["delete_row"] == 0
    assert calls["delete_object"] == 0


def test_delete_episode_succeeds_when_graph_dependency_is_unavailable_but_canonical_cleanup_exists(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    async def fake_graph_dependency_failure_detail() -> str | None:
        return "Error 111 connecting to localhost:6380. Connection refused."

    class UnexpectedMemoryCore:
        async def delete_episode(self, project_id: str, *, episode_id: str) -> DeleteEpisodeResult:
            raise AssertionError("graph cleanup should be skipped when dependency is unavailable")

    monkeypatch.setattr(tool_handlers, "get_graph_dependency_failure_detail", fake_graph_dependency_failure_detail)
    monkeypatch.setattr(tool_handlers, "get_memory_core", lambda: UnexpectedMemoryCore())

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-graph-down-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {
                        "content": "Episode to delete while graph is unavailable",
                        "metadata": {"tags": ["cleanup-graph-down"]},
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        episode_id = save_payload["result"]["episode_id"]

        delete_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-graph-down-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": episode_id},
                },
            },
        )
        delete_payload = parse_result(delete_response)
        assert delete_payload["ok"] is True
        assert delete_payload["result"]["status"] == "DELETED"
        assert delete_payload["result"]["deleted"]["canonical"] is True
        assert delete_payload["result"]["deleted"]["graph"] is False
        assert delete_payload["result"]["deleted"]["graph_skipped"] is True

        search_after = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-graph-down-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_memory",
                    "arguments": {"query": "graph is unavailable", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_after)
        assert search_payload["ok"] is True
        assert search_payload["result"]["results"] == []

    teardown_app()
