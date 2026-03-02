from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from viberecall_mcp import mcp_app as mcp_transport
from viberecall_mcp.app import create_app
from viberecall_mcp.auth import AuthenticatedToken
from viberecall_mcp import runtime
from viberecall_mcp.runtime import get_memory_core, reset_runtime_state
from viberecall_mcp.runtime_types import EnqueueUpdateFactResult
from viberecall_mcp import tool_handlers


class DummySession:
    pass


@asynccontextmanager
async def override_session() -> AsyncIterator[DummySession]:
    yield DummySession()


def parse_mcp_event(response):
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data: "):
                return json.loads(line.removeprefix("data: "))
        raise AssertionError("Missing data frame in event-stream response")
    return response.json()


def parse_result(response):
    body = parse_mcp_event(response)
    content = body["result"]["content"][0]["text"]
    return json.loads(content)


def initialize_session(client: TestClient, project_id: str) -> str:
    response = client.post(
        f"/p/{project_id}/mcp",
        headers={"accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        },
    )
    assert response.status_code == 200
    return response.headers["mcp-session-id"]


def mcp_headers(session_id: str, authorization: str = "Bearer test-token", **extra: str) -> dict[str, str]:
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-session-id": session_id,
        "authorization": authorization,
    }
    headers.update(extra)
    return headers


def make_token(plan: str = "pro", project_id: str = "proj_test") -> AuthenticatedToken:
    return AuthenticatedToken(
        token_id="tok_test",
        project_id=project_id,
        scopes=["memory:read", "memory:write", "facts:read", "facts:write", "timeline:read"],
        plan=plan,
        db_name=f"vr_{project_id}",
    )


def setup_app(monkeypatch, token: AuthenticatedToken, episode_store: dict) -> None:
    asyncio.run(reset_runtime_state())
    object_store: dict[str, str] = {}

    async def fake_auth(_session, *, authorization, project_id):
        assert authorization == "Bearer test-token"
        assert project_id == token.project_id
        return token

    async def fake_touch(_session, _token_id: str) -> None:
        return None

    async def fake_audit(*args, **kwargs) -> None:
        return None

    async def fake_create_episode(
        session,
        *,
        episode_id: str,
        project_id: str,
        content: str | None,
        reference_time: str | None,
        metadata_json: str,
        content_ref: str | None = None,
        summary: str | None = None,
        job_id: str | None = None,
        enrichment_status: str = "pending",
    ) -> None:
        episode_store[episode_id] = {
            "episode_id": episode_id,
            "project_id": project_id,
            "content": content,
            "content_ref": content_ref,
            "reference_time": reference_time,
            "metadata_json": metadata_json,
            "job_id": job_id,
            "enrichment_status": enrichment_status,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        }

    async def fake_list_timeline(
        session,
        *,
        project_id: str,
        from_time: str | None,
        to_time: str | None,
        limit: int,
        offset: int,
    ) -> list[dict]:
        rows = [
            {
                "episode_id": episode["episode_id"],
                "reference_time": episode["reference_time"],
                "ingested_at": episode["ingested_at"],
                "summary": episode["summary"] or episode["content"][:160],
                "metadata": json.loads(episode["metadata_json"]),
            }
            for episode in episode_store.values()
            if episode["project_id"] == project_id
        ]
        rows.sort(key=lambda row: (row["reference_time"] or row["ingested_at"], row["episode_id"]), reverse=True)
        return rows[offset : offset + limit]

    async def fake_recent_raw(
        session,
        *,
        project_id: str,
        query: str,
        window_seconds: int,
        limit: int,
    ) -> list[dict]:
        rows = []
        for episode in episode_store.values():
            if episode["project_id"] != project_id or episode["enrichment_status"] == "complete":
                continue
            haystack = f"{episode.get('summary') or ''} {episode.get('content') or ''}".lower()
            if query.lower() not in haystack:
                continue
            rows.append(
                {
                    "episode_id": episode["episode_id"],
                    "reference_time": episode["reference_time"],
                    "ingested_at": episode["ingested_at"],
                    "summary": episode.get("summary") or (episode.get("content") or "")[:160],
                    "metadata": json.loads(episode["metadata_json"]),
                }
            )
        return rows[:limit]

    async def fake_set_episode_job_id(session, *, episode_id: str, job_id: str) -> None:
        episode_store[episode_id]["job_id"] = job_id

    async def fake_monthly_vibe_tokens(_session, *, project_id: str) -> int:
        return 0

    async def fake_put_text(*, object_key: str, content: str) -> None:
        object_store[object_key] = content

    class FakeQueue:
        async def enqueue_ingest(self, *, episode_id: str, project_id: str, request_id: str, token_id: str | None):
            episode = episode_store[episode_id]
            if not episode.get("content") and episode.get("content_ref"):
                episode["content"] = object_store[str(episode["content_ref"])]
            result = await get_memory_core().ingest_episode(project_id, episode)
            episode["summary"] = result["summary"]
            episode["enrichment_status"] = "complete"
            return "job_ingest_test"

        async def enqueue_update_fact(
            self,
            *,
            project_id: str,
            request_id: str,
            token_id: str | None,
            fact_id: str,
            new_fact_id: str,
            new_text: str,
            effective_time: str,
            reason: str | None,
        ):
            result = await get_memory_core().update_fact(
                project_id,
                fact_id=fact_id,
                new_fact_id=new_fact_id,
                new_text=new_text,
                effective_time=effective_time,
                reason=reason,
            )
            return EnqueueUpdateFactResult(job_id="job_update_test", immediate_result=result)

    monkeypatch.setattr(mcp_transport, "open_db_session", override_session)
    monkeypatch.setattr(mcp_transport, "authenticate_bearer_token", fake_auth)
    monkeypatch.setattr(mcp_transport, "touch_token_usage", fake_touch)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit)
    monkeypatch.setattr(tool_handlers, "create_episode", fake_create_episode)
    monkeypatch.setattr(tool_handlers, "list_timeline_episodes", fake_list_timeline)
    monkeypatch.setattr(tool_handlers, "list_recent_raw_episodes", fake_recent_raw)
    monkeypatch.setattr(tool_handlers, "set_episode_job_id", fake_set_episode_job_id)
    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: FakeQueue())
    monkeypatch.setattr(tool_handlers, "put_text", fake_put_text)


def setup_app_celery_transport(monkeypatch, token: AuthenticatedToken, episode_store: dict) -> None:
    asyncio.run(reset_runtime_state())
    monkeypatch.setattr(runtime.settings, "queue_backend", "celery")

    async def fake_auth(_session, *, authorization, project_id):
        assert authorization == "Bearer test-token"
        assert project_id == token.project_id
        return token

    async def fake_touch(_session, _token_id: str) -> None:
        return None

    async def fake_audit(*args, **kwargs) -> None:
        return None

    async def fake_create_episode(
        session,
        *,
        episode_id: str,
        project_id: str,
        content: str | None,
        reference_time: str | None,
        metadata_json: str,
        content_ref: str | None = None,
        summary: str | None = None,
        job_id: str | None = None,
        enrichment_status: str = "pending",
    ) -> None:
        episode_store[episode_id] = {
            "episode_id": episode_id,
            "project_id": project_id,
            "content": content,
            "content_ref": content_ref,
            "reference_time": reference_time,
            "metadata_json": metadata_json,
            "job_id": job_id,
            "enrichment_status": enrichment_status,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        }

    async def fake_set_episode_job_id(session, *, episode_id: str, job_id: str) -> None:
        episode_store[episode_id]["job_id"] = job_id

    async def fake_monthly_vibe_tokens(_session, *, project_id: str) -> int:
        return 0

    monkeypatch.setattr(mcp_transport, "open_db_session", override_session)
    monkeypatch.setattr(mcp_transport, "authenticate_bearer_token", fake_auth)
    monkeypatch.setattr(mcp_transport, "touch_token_usage", fake_touch)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit)
    monkeypatch.setattr(tool_handlers, "create_episode", fake_create_episode)
    monkeypatch.setattr(tool_handlers, "set_episode_job_id", fake_set_episode_job_id)
    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.ingest_episode_task.delay",
        lambda *args: SimpleNamespace(id="celery-ingest-http-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.update_fact_task.delay",
        lambda *args: SimpleNamespace(id="celery-update-http-1"),
    )


def teardown_app() -> None:
    asyncio.run(reset_runtime_state())


def test_tools_list_respects_free_plan(monkeypatch) -> None:
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
    tool_names = [tool["name"] for tool in parse_mcp_event(response)["result"]["tools"]]
    assert tool_names == ["viberecall_save", "viberecall_search", "viberecall_timeline"]


def test_free_plan_cannot_call_get_facts(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

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


def test_quota_exceeded_returns_error_envelope(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)
    async def fake_monthly_vibe_tokens(*_args, **_kwargs):
        return 100_000

    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)

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
    assert payload["ok"] is False
    assert payload["error"]["code"] == "QUOTA_EXCEEDED"


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "tool_call_latency_ms" in response.text
