from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from redis import asyncio as redis_async
from sqlalchemy import text

from viberecall_mcp.app import create_app
from viberecall_mcp.auth import hash_token
from viberecall_mcp.db import SessionLocal
from viberecall_mcp.ids import new_id
from viberecall_mcp.memory_core.falkordb_admin import FalkorDBGraphManager
from viberecall_mcp import runtime
from viberecall_mcp.workers.celery_app import celery_app


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RUNTIME_E2E_CELERY") != "1",
    reason="Set RUN_RUNTIME_E2E_CELERY=1 to run Celery worker end-to-end integration test.",
)


def _parse_mcp_event(response):
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data: "):
                return json.loads(line.removeprefix("data: "))
        raise AssertionError("Missing data frame in event-stream response")
    return response.json()


def _parse_result(response):
    payload = _parse_mcp_event(response)
    content = payload["result"]["content"][0]["text"]
    return json.loads(content)


def _initialize_session(client: TestClient, project_id: str) -> str:
    response = client.post(
        f"/p/{project_id}/mcp",
        headers={"accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": "init-e2e",
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


def _mcp_headers(session_id: str, token: str, **extra: str) -> dict[str, str]:
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-session-id": session_id,
        "authorization": f"Bearer {token}",
    }
    headers.update(extra)
    return headers


def _call_tool(
    client: TestClient,
    *,
    project_id: str,
    session_id: str,
    token: str,
    request_id: str,
    tool_name: str,
    arguments: dict,
    idempotency_key: str | None = None,
) -> dict:
    headers = _mcp_headers(session_id, token)
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    response = client.post(
        f"/p/{project_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        },
    )
    assert response.status_code == 200
    return _parse_result(response)


@contextmanager
def _run_celery_worker(env: dict[str, str]) -> Iterator[None]:
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "viberecall_mcp.workers.celery_app",
        "worker",
        "-l",
        "WARNING",
        "-Q",
        "memory",
        "--pool=solo",
        "--concurrency=1",
        "--without-heartbeat",
        "--without-gossip",
        "--without-mingle",
    ]
    process = subprocess.Popen(
        cmd,
        cwd="/Data/VibeRecall_Memory/apps/mcp-api",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(2.0)
        if process.poll() is not None:
            raise AssertionError("Celery worker failed to start for runtime e2e test")
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=8)


async def _create_project_token(project_id: str, token_id: str, plaintext_token: str) -> None:
    async with SessionLocal() as session:
        await session.execute(
            text(
                """
                insert into projects (id, name, owner_id, plan, retention_days, isolation_mode)
                values (:id, :name, :owner_id, :plan, :retention_days, :isolation_mode)
                """
            ),
            {
                "id": project_id,
                "name": "Runtime E2E Celery",
                "owner_id": "runtime-e2e",
                "plan": "pro",
                "retention_days": 30,
                "isolation_mode": "falkordb_graph",
            },
        )
        await session.execute(
            text(
                """
                insert into mcp_tokens (token_id, prefix, token_hash, project_id, scopes, plan)
                values (:token_id, :prefix, :token_hash, :project_id, :scopes, :plan)
                """
            ),
            {
                "token_id": token_id,
                "prefix": plaintext_token[:16],
                "token_hash": hash_token(plaintext_token),
                "project_id": project_id,
                "scopes": ["memory:read", "memory:write", "facts:read", "facts:write", "timeline:read"],
                "plan": "pro",
            },
        )
        await session.commit()


async def _get_episode_status(episode_id: str) -> str | None:
    async with SessionLocal() as session:
        result = await session.execute(
            text("select enrichment_status from episodes where episode_id = :episode_id"),
            {"episode_id": episode_id},
        )
        row = result.first()
        if row is None:
            return None
        return row[0]


async def _count_usage_events(project_id: str, tool_name: str) -> int:
    async with SessionLocal() as session:
        result = await session.execute(
            text(
                """
                select count(*)
                from usage_events
                where project_id = :project_id
                  and tool = :tool
                """
            ),
            {"project_id": project_id, "tool": tool_name},
        )
        row = result.first()
        return int(row[0] if row else 0)


async def _count_audit_logs(project_id: str, action: str, status_text: str) -> int:
    async with SessionLocal() as session:
        result = await session.execute(
            text(
                """
                select count(*)
                from audit_logs
                where project_id = :project_id
                  and action = :action
                  and status = :status
                """
            ),
            {
                "project_id": project_id,
                "action": action,
                "status": status_text,
            },
        )
        row = result.first()
        return int(row[0] if row else 0)


async def _cleanup_project_data(project_id: str) -> None:
    async with SessionLocal() as session:
        await session.execute(text("delete from usage_events where project_id = :project_id"), {"project_id": project_id})
        await session.execute(text("delete from audit_logs where project_id = :project_id"), {"project_id": project_id})
        await session.execute(text("delete from episodes where project_id = :project_id"), {"project_id": project_id})
        await session.execute(text("delete from mcp_tokens where project_id = :project_id"), {"project_id": project_id})
        await session.execute(text("delete from webhooks where project_id = :project_id"), {"project_id": project_id})
        await session.execute(text("delete from projects where id = :project_id"), {"project_id": project_id})
        await session.commit()


def _wait_until(predicate, *, timeout_seconds: float, interval_seconds: float = 0.5) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_seconds)
    return False


def test_runtime_e2e_celery_worker_flow(monkeypatch) -> None:
    project_id = new_id("proj")
    token_id = new_id("tok")
    token_plaintext = f"vr_mcp_sk_{secrets.token_urlsafe(24)}"
    admin = FalkorDBGraphManager()

    try:
        # Connectivity pre-checks for optional e2e mode.
        redis = redis_async.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        try:
            asyncio.run(redis.ping())
            probe_project = f"{project_id}_probe"
            asyncio.run(admin.ensure_project_graph(probe_project))
            asyncio.run(admin.reset_graph(probe_project))
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Runtime e2e dependencies are unavailable: {exc}")
        finally:
            asyncio.run(redis.close())

        # Force runtime selectors to real-service path for this test process.
        monkeypatch.setattr(runtime.settings, "memory_backend", "falkordb")
        monkeypatch.setattr(runtime.settings, "kv_backend", "redis")
        monkeypatch.setattr(runtime.settings, "queue_backend", "celery")
        celery_app.conf.task_always_eager = False

        asyncio.run(_create_project_token(project_id, token_id, token_plaintext))

        worker_env = {
            **os.environ,
            "MEMORY_BACKEND": "falkordb",
            "KV_BACKEND": "redis",
            "QUEUE_BACKEND": "celery",
        }

        with _run_celery_worker(worker_env):
            with TestClient(create_app()) as client:
                session_id = _initialize_session(client, project_id)

                save_payload = _call_tool(
                    client,
                    project_id=project_id,
                    session_id=session_id,
                    token=token_plaintext,
                    request_id="e2e-save",
                    tool_name="viberecall_save",
                    idempotency_key="e2e-celery-save-1",
                    arguments={
                        "content": "Fix callback auth race in celery runtime e2e flow",
                        "metadata": {
                            "repo": "viberecall",
                            "branch": "main",
                            "tags": ["celery-e2e", "auth"],
                            "files": ["apps/mcp-api/src/viberecall_mcp/control_plane.py"],
                            "type": "bugfix",
                        },
                    },
                )
                assert save_payload["ok"] is True
                episode_id = save_payload["result"]["episode_id"]
                assert save_payload["result"]["enrichment"]["job_id"]

                completed = _wait_until(
                    lambda: asyncio.run(_get_episode_status(episode_id)) == "complete",
                    timeout_seconds=25,
                )
                assert completed, "Episode enrichment did not complete via Celery worker in time"

                search_payload = _call_tool(
                    client,
                    project_id=project_id,
                    session_id=session_id,
                    token=token_plaintext,
                    request_id="e2e-search",
                    tool_name="viberecall_search",
                    arguments={"query": "callback auth race", "limit": 10},
                )
                assert search_payload["ok"] is True
                assert search_payload["result"]["results"], "Expected search results after worker ingestion"

                facts_payload = _call_tool(
                    client,
                    project_id=project_id,
                    session_id=session_id,
                    token=token_plaintext,
                    request_id="e2e-facts-before",
                    tool_name="viberecall_get_facts",
                    arguments={"filters": {"tag": "celery-e2e"}, "limit": 20},
                )
                assert facts_payload["ok"] is True
                old_fact = next(
                    fact for fact in facts_payload["result"]["facts"] if fact["invalid_at"] is None
                )
                old_fact_id = old_fact["id"]

                update_text = "Fix callback auth race in celery runtime e2e flow (updated)"
                update_payload = _call_tool(
                    client,
                    project_id=project_id,
                    session_id=session_id,
                    token=token_plaintext,
                    request_id="e2e-update",
                    tool_name="viberecall_update_fact",
                    idempotency_key="e2e-celery-update-1",
                    arguments={
                        "fact_id": old_fact_id,
                        "new_text": update_text,
                        "effective_time": datetime.now(timezone.utc).isoformat(),
                        "reason": "integration e2e verification",
                    },
                )
                assert update_payload["ok"] is True
                assert update_payload["result"]["job_id"]

                def _new_fact_visible() -> bool:
                    current = _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="e2e-facts-after",
                        tool_name="viberecall_get_facts",
                        arguments={"filters": {"tag": "celery-e2e"}, "limit": 50},
                    )
                    facts = current["result"]["facts"]
                    has_old_invalidated = any(
                        fact["id"] == old_fact_id and fact["invalid_at"] is not None for fact in facts
                    )
                    has_new_text = any(fact["text"] == update_text for fact in facts)
                    return has_old_invalidated and has_new_text

                updated = _wait_until(_new_fact_visible, timeout_seconds=25)
                assert updated, "Temporal update did not become visible after Celery processing"

        usage_save = asyncio.run(_count_usage_events(project_id, "viberecall_save"))
        usage_update = asyncio.run(_count_usage_events(project_id, "viberecall_update_fact"))
        audit_ingest = asyncio.run(_count_audit_logs(project_id, "worker/ingest", "complete"))
        audit_update = asyncio.run(_count_audit_logs(project_id, "worker/update_fact", "complete"))

        assert usage_save >= 1
        assert usage_update >= 1
        assert audit_ingest >= 1
        assert audit_update >= 1
    finally:
        asyncio.run(_cleanup_project_data(project_id))
        asyncio.run(admin.reset_graph(project_id))
        asyncio.run(admin.close())
