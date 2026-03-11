from __future__ import annotations

from tests.support.mcp_harness import *


def test_search_entities_rate_limit_enforced(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_search_entities_rate"
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
                "id": "entities-rate-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "index_repo", "limit": 10},
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entities-rate-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "index_repo", "limit": 10},
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"
def test_search_entities_prefers_exact_canonical_match(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        for call_id, tag in [("entity-save-1", "auth-service"), ("entity-save-2", "auth")]:
            response = client.post(
                "/p/proj_test/mcp",
                headers=mcp_headers(session_id),
                json={
                    "jsonrpc": "2.0",
                    "id": call_id,
                    "method": "tools/call",
                    "params": {
                        "name": "viberecall_save_episode",
                        "arguments": {
                            "content": f"Track tag {tag}",
                            "metadata": {"tags": [tag]},
                        },
                    },
                },
            )
            assert parse_result(response)["ok"] is True

        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entity-search-exact",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "auth", "entity_kinds": ["Tag"], "limit": 10},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "READY"
    assert payload["result"]["entities"][0]["name"] == "auth"


def test_search_entities_uses_canonical_backend_not_code_index(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def explode_old_search(**kwargs):
        _ = kwargs
        raise AssertionError("old code-index path should not be used")

    monkeypatch.setattr(tool_handlers, "search_entities", explode_old_search)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entity-canonical-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {
                        "content": "Track apps/mcp-api canonical entity",
                        "metadata": {"files": ["apps/mcp-api/src/viberecall_mcp/tool_handlers.py"]},
                    },
                },
            },
        )
        assert parse_result(save_response)["ok"] is True

        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entity-canonical-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "tool_handlers.py", "entity_kinds": ["File"], "limit": 10},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["entities"][0]["entity_kind"] == "File"
    assert payload["result"]["entities"][0]["name"] == "apps/mcp-api/src/viberecall_mcp/tool_handlers.py"
def test_search_entities_boosts_and_filters_by_salience_class(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        first_save = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entity-salience-save-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {
                        "content": "Track tag auth-service",
                        "metadata": {"tags": ["auth-service"]},
                    },
                },
            },
        )
        second_save = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entity-salience-save-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {
                        "content": "Track tag auth-middleware",
                        "metadata": {"tags": ["auth-middleware"]},
                    },
                },
            },
        )
        assert parse_result(first_save)["ok"] is True
        assert parse_result(second_save)["ok"] is True

        pin_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entity-salience-pin",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_pin_memory",
                    "arguments": {
                        "target_kind": "ENTITY",
                        "target_id": "tag::auth-middleware",
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
                "id": "entity-salience-boosted",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "auth", "entity_kinds": ["Tag"], "limit": 10},
                },
            },
        )
        filtered_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entity-salience-filtered",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {
                        "query": "auth",
                        "entity_kinds": ["Tag"],
                        "salience_classes": ["PINNED"],
                        "limit": 10,
                    },
                },
            },
        )

    teardown_app()
    boosted_payload = parse_result(boosted_response)
    filtered_payload = parse_result(filtered_response)
    assert boosted_payload["ok"] is True
    assert filtered_payload["ok"] is True
    assert boosted_payload["result"]["entities"][0]["entity_id"] == "tag::auth-middleware"
    assert boosted_payload["result"]["entities"][0]["salience_class"] == "PINNED"
    assert [entity["entity_id"] for entity in filtered_payload["result"]["entities"]] == ["tag::auth-middleware"]


def test_get_neighbors_rejects_depth_other_than_one(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "neighbors-depth",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_neighbors",
                    "arguments": {"entity_id": "ent_auth", "depth": 2},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert payload["error"]["details"]["depth"] == 2


def test_get_neighbors_returns_structured_canonical_payload(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def fake_neighbors(**kwargs):
        _ = kwargs
        return {
            "anchor": {"entity_id": "ent_auth", "name": "Auth Service", "entity_kind": "Service", "aliases": []},
            "neighbors": [{"entity_id": "ent_api", "name": "API Gateway", "entity_kind": "Service", "aliases": []}],
            "edges": [
                {
                    "fact_version_id": "factv_dep_1",
                    "fact_group_id": "factgrp_dep_1",
                    "direction": "OUT",
                    "subject_entity_id": "ent_auth",
                    "object_entity_id": "ent_api",
                    "relation_type_id": "depends_on",
                    "relation_type": "depends_on",
                    "statement": "Auth Service depends on API Gateway",
                    "recorded_at": "2026-03-10T10:00:00Z",
                    "confidence": 0.91,
                    "salience_score": 0.72,
                    "trust_class": "observed",
                }
            ],
            "truncated": False,
        }

    monkeypatch.setattr(tool_handlers, "get_canonical_neighbors", fake_neighbors)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "neighbors-structured",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_neighbors",
                    "arguments": {"entity_id": "ent_auth", "direction": "OUT", "limit": 10},
                },
            },
        )

    teardown_app()
    body = parse_mcp_event(response)
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["anchor"]["entity_id"] == "ent_auth"
    assert payload["result"]["edges"][0]["relation_type"] == "depends_on"
    assert body["result"]["structuredContent"]["result"]["neighbors"][0]["entity_id"] == "ent_api"


def test_find_paths_rejects_same_source_and_destination(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "find-paths-same",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_find_paths",
                    "arguments": {
                        "src_entity_id": "ent_auth",
                        "dst_entity_id": "ent_auth",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert payload["error"]["details"]["src_entity_id"] == "ent_auth"


def test_find_paths_returns_structured_payload(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def fake_paths(**kwargs):
        _ = kwargs
        return {
            "paths": [
                {
                    "score": 0.91,
                    "hop_count": 2,
                    "entity_ids": ["ent_auth", "ent_api", "ent_db"],
                    "fact_version_ids": ["factv_dep_1", "factv_dep_2"],
                    "steps": [
                        {
                            "step_kind": "entity",
                            "entity_id": "ent_auth",
                            "name": "Auth Service",
                            "entity_kind": "Service",
                        },
                        {
                            "step_kind": "fact",
                            "fact_version_id": "factv_dep_1",
                            "fact_group_id": "factgrp_dep_1",
                            "relation_type_id": "depends_on",
                            "relation_type": "depends_on",
                            "direction": "OUT",
                            "statement": "Auth Service depends on API Gateway",
                            "confidence": 0.92,
                            "salience_score": 0.75,
                            "trust_class": "observed",
                            "recorded_at": "2026-03-10T10:00:00Z",
                        },
                        {
                            "step_kind": "entity",
                            "entity_id": "ent_api",
                            "name": "API Gateway",
                            "entity_kind": "Service",
                        },
                        {
                            "step_kind": "fact",
                            "fact_version_id": "factv_dep_2",
                            "fact_group_id": "factgrp_dep_2",
                            "relation_type_id": "depends_on",
                            "relation_type": "depends_on",
                            "direction": "OUT",
                            "statement": "API Gateway depends on Primary DB",
                            "confidence": 0.9,
                            "salience_score": 0.7,
                            "trust_class": "observed",
                            "recorded_at": "2026-03-10T10:05:00Z",
                        },
                        {
                            "step_kind": "entity",
                            "entity_id": "ent_db",
                            "name": "Primary DB",
                            "entity_kind": "Database",
                        },
                    ],
                }
            ],
            "truncated": False,
            "search_metadata": {
                "src_entity_id": "ent_auth",
                "dst_entity_id": "ent_db",
                "max_depth_applied": 2,
                "limit_paths": 5,
                "relation_types_applied": ["depends_on"],
                "current_only": True,
                "valid_at": None,
                "as_of_system_time": None,
                "engine": "sql_recursive",
            },
        }

    monkeypatch.setattr(tool_handlers, "find_canonical_paths", fake_paths)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "find-paths-structured",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_find_paths",
                    "arguments": {
                        "src_entity_id": "ent_auth",
                        "dst_entity_id": "ent_db",
                        "relation_types": ["depends_on"],
                        "max_depth": 2,
                        "limit_paths": 5,
                    },
                },
            },
        )

    teardown_app()
    body = parse_mcp_event(response)
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["paths"][0]["hop_count"] == 2
    assert payload["result"]["paths"][0]["steps"][1]["fact_version_id"] == "factv_dep_1"
    assert payload["result"]["search_metadata"]["engine"] == "sql_recursive"
    assert body["result"]["structuredContent"]["result"]["paths"][0]["entity_ids"] == [
        "ent_auth",
        "ent_api",
        "ent_db",
    ]


def test_find_paths_returns_not_found_for_missing_entity(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def fake_paths(**kwargs):
        _ = kwargs
        return {"missing_entity_id": "ent_missing"}

    monkeypatch.setattr(tool_handlers, "find_canonical_paths", fake_paths)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "find-paths-missing",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_find_paths",
                    "arguments": {
                        "src_entity_id": "ent_auth",
                        "dst_entity_id": "ent_missing",
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["details"]["entity_id"] == "ent_missing"


def test_explain_fact_returns_lineage_and_supporting_episodes(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    async def fake_explain(**kwargs):
        _ = kwargs
        return {
            "fact": {
                "fact_version_id": "factv_1",
                "fact_group_id": "factgrp_1",
                "statement": "Auth middleware guards /projects",
                "subject_entity": {"entity_id": "ent_auth"},
                "object_entity": None,
                "relation_type": {"relation_type_id": "guards", "name": "guards"},
            },
            "lineage": {
                "fact_group_id": "factgrp_1",
                "current_fact_version_id": "factv_2",
                "versions": [
                    {"fact_version_id": "factv_1", "status": "SUPERSEDED"},
                    {"fact_version_id": "factv_2", "status": "CURRENT"},
                ],
            },
            "supporting_episodes": [
                {
                    "episode_id": "ep_1",
                    "summary": "Validated auth middleware after rollout",
                    "reference_time": "2026-03-10T09:00:00Z",
                }
            ],
            "extraction_details": {
                "relation_type": {"relation_type_id": "guards", "name": "guards"},
                "provenance": [{"source_kind": "episode", "source_id": "ep_1", "role": "supports"}],
                "created_from_episode_id": "ep_1",
                "metadata": {"tags": ["auth"]},
            },
            "confidence_breakdown": {
                "confidence": 0.84,
                "salience_score": 0.61,
                "trust_class": "observed",
                "status": "SUPERSEDED",
                "is_current": False,
            },
        }

    monkeypatch.setattr(tool_handlers, "explain_canonical_fact", fake_explain)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "explain-fact",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_explain_fact",
                    "arguments": {"fact_version_id": "factv_1"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["lineage"]["current_fact_version_id"] == "factv_2"
    assert payload["result"]["supporting_episodes"][0]["episode_id"] == "ep_1"
    assert payload["result"]["confidence_breakdown"]["is_current"] is False


def test_explain_fact_returns_not_found_for_missing_fact(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "explain-fact-missing",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_explain_fact",
                    "arguments": {"fact_version_id": "missing-fact"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["details"]["fact_version_id"] == "missing-fact"


def test_resolve_reference_returns_canonical_match(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["memory:write", "entities:read"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {
                        "content": "Track tag auth-service",
                        "metadata": {"tags": ["auth-service"]},
                    },
                },
            },
        )
        assert parse_result(save_response)["ok"] is True

        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-reference",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "auth-service", "observed_kind": "Tag", "limit": 5},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "RESOLVED"
    assert payload["result"]["best_match"]["entity_id"] == "tag::auth-service"
    assert payload["result"]["best_match"]["entity_kind"] == "Tag"
    assert payload["result"]["unresolved_mention"] is None


def test_resolve_reference_returns_ambiguous_candidates(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["memory:write", "entities:read"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        for request_id, tag in [("resolve-ambig-save-1", "auth-service"), ("resolve-ambig-save-2", "auth-session")]:
            response = client.post(
                "/p/proj_test/mcp",
                headers=mcp_headers(session_id),
                json={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": "viberecall_save_episode",
                        "arguments": {"content": f"Track tag {tag}", "metadata": {"tags": [tag]}},
                    },
                },
            )
            assert parse_result(response)["ok"] is True

        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-ambiguous",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "auth", "observed_kind": "Tag", "limit": 5},
                },
            },
        )
        repeat_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-ambiguous-repeat",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "auth", "observed_kind": "Tag", "limit": 5},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    repeat_payload = parse_result(repeat_response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "AMBIGUOUS"
    assert payload["result"]["needs_disambiguation"] is True
    assert len(payload["result"]["candidates"]) >= 2
    assert payload["result"]["unresolved_mention"]["status"] == "OPEN"
    assert repeat_payload["ok"] is True
    assert repeat_payload["result"]["unresolved_mention"]["status"] == "OPEN"
    assert (
        repeat_payload["result"]["unresolved_mention"]["mention_id"]
        == payload["result"]["unresolved_mention"]["mention_id"]
    )


def test_resolve_reference_no_match_reuses_same_unresolved_mention(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=["entities:read"]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        first_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-no-match-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "missing-tag", "observed_kind": "Tag", "limit": 5},
                },
            },
        )
        second_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-no-match-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "missing-tag", "observed_kind": "Tag", "limit": 5},
                },
            },
        )

    teardown_app()
    first_payload = parse_result(first_response)
    second_payload = parse_result(second_response)
    assert first_payload["ok"] is True
    assert first_payload["result"]["status"] == "NO_MATCH"
    assert first_payload["result"]["unresolved_mention"]["status"] == "OPEN"
    assert second_payload["ok"] is True
    assert second_payload["result"]["status"] == "NO_MATCH"
    assert (
        second_payload["result"]["unresolved_mention"]["mention_id"]
        == first_payload["result"]["unresolved_mention"]["mention_id"]
    )


def test_resolve_reference_closes_unresolved_mention_after_merge(monkeypatch) -> None:
    episode_store = {}
    setup_app(
        monkeypatch,
        make_token(plan="free", scopes=["memory:write", "entities:read", "resolution:write"]),
        episode_store,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        for request_id, tag in [("resolve-close-save-1", "auth-service"), ("resolve-close-save-2", "auth-session")]:
            response = client.post(
                "/p/proj_test/mcp",
                headers=mcp_headers(session_id),
                json={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": "viberecall_save_episode",
                        "arguments": {"content": f"Track tag {tag}", "metadata": {"tags": [tag]}},
                    },
                },
            )
            assert parse_result(response)["ok"] is True

        ambiguous_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-close-ambiguous",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "auth", "observed_kind": "Tag", "limit": 5},
                },
            },
        )
        merge_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-close-merge",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_merge_entities",
                    "arguments": {
                        "target_entity_id": "tag::auth-service",
                        "source_entity_ids": ["tag::auth-session"],
                        "reason": "Collapse duplicate auth mentions",
                    },
                },
            },
        )
        assert parse_result(merge_response)["ok"] is True
        resolved_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "resolve-close-resolved",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "auth", "observed_kind": "Tag", "limit": 5},
                },
            },
        )

    teardown_app()
    ambiguous_payload = parse_result(ambiguous_response)
    resolved_payload = parse_result(resolved_response)
    assert ambiguous_payload["ok"] is True
    assert ambiguous_payload["result"]["status"] == "AMBIGUOUS"
    assert ambiguous_payload["result"]["unresolved_mention"]["status"] == "OPEN"
    assert resolved_payload["ok"] is True
    assert resolved_payload["result"]["status"] == "RESOLVED"
    assert resolved_payload["result"]["unresolved_mention"]["status"] == "RESOLVED"
    assert (
        resolved_payload["result"]["unresolved_mention"]["mention_id"]
        == ambiguous_payload["result"]["unresolved_mention"]["mention_id"]
    )


def test_merge_entities_returns_accepted_and_moves_alias(monkeypatch) -> None:
    episode_store = {}
    setup_app(
        monkeypatch,
        make_token(plan="free", scopes=["memory:write", "entities:read", "resolution:write", "ops:read"]),
        episode_store,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        for request_id, tag in [("merge-save-1", "auth-service"), ("merge-save-2", "auth-api")]:
            response = client.post(
                "/p/proj_test/mcp",
                headers=mcp_headers(session_id),
                json={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": "viberecall_save_episode",
                        "arguments": {"content": f"Track tag {tag}", "metadata": {"tags": [tag]}},
                    },
                },
            )
            assert parse_result(response)["ok"] is True

        merge_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "merge-entities",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_merge_entities",
                    "arguments": {
                        "target_entity_id": "tag::auth-service",
                        "source_entity_ids": ["tag::auth-api"],
                        "reason": "Consolidate duplicate auth tags",
                    },
                },
            },
        )
        merge_payload = parse_result(merge_response)
        assert merge_payload["ok"] is True

        resolve_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "merge-resolve-old-alias",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_resolve_reference",
                    "arguments": {"mention_text": "auth-api", "observed_kind": "Tag", "limit": 5},
                },
            },
        )
        operation_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "merge-operation",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_operation",
                    "arguments": {"operation_id": merge_payload["result"]["operation_id"]},
                },
            },
        )

    teardown_app()
    resolve_payload = parse_result(resolve_response)
    operation_payload = parse_result(operation_response)
    assert resolve_payload["ok"] is True
    assert resolve_payload["result"]["status"] == "RESOLVED"
    assert resolve_payload["result"]["best_match"]["entity_id"] == "tag::auth-service"
    assert operation_payload["ok"] is True
    assert operation_payload["result"]["operation"]["status"] == "SUCCEEDED"
    assert operation_payload["result"]["operation"]["operation_type"] == "ENTITY_RESOLUTION"


def test_split_entity_rejects_duplicate_alias_assignment(monkeypatch) -> None:
    episode_store = {}
    setup_app(
        monkeypatch,
        make_token(plan="free", scopes=["memory:write", "resolution:write"]),
        episode_store,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "split-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save_episode",
                    "arguments": {
                        "content": "Track tag auth-service",
                        "metadata": {"tags": ["auth-service"]},
                    },
                },
            },
        )
        assert parse_result(save_response)["ok"] is True

        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "split-duplicate-alias",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_split_entity",
                    "arguments": {
                        "source_entity_id": "tag::auth-service",
                        "partitions": [
                            {
                                "new_entity": {"entity_kind": "Tag", "canonical_name": "auth-core"},
                                "alias_values": ["auth-service"],
                                "fact_bindings": [],
                            },
                            {
                                "new_entity": {"entity_kind": "Tag", "canonical_name": "auth-edge"},
                                "alias_values": ["auth-service"],
                                "fact_bindings": [],
                            },
                        ],
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "duplicate alias assignment" in payload["error"]["message"]
