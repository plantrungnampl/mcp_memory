from __future__ import annotations

import asyncio
import asyncpg
import httpx
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
from redis import asyncio as redis_async

from viberecall_mcp.app import create_app
from viberecall_mcp.auth import hash_token
from viberecall_mcp.config import get_settings
from viberecall_mcp.db import dispose_engine
from viberecall_mcp.ids import new_id
from viberecall_mcp.memory_core.falkordb_admin import FalkorDBGraphManager
from viberecall_mcp import runtime
from viberecall_mcp.workers.celery_app import celery_app


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RUNTIME_E2E_CELERY") != "1",
    reason="Set RUN_RUNTIME_E2E_CELERY=1 to run Celery worker end-to-end integration test.",
)

_DATABASE_URL = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


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


async def _initialize_session(client: httpx.AsyncClient, project_id: str) -> str:
    response = await client.post(
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


async def _call_tool(
    client: httpx.AsyncClient,
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
    response = await client.post(
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


async def _create_project_token(
    project_id: str,
    token_id: str,
    plaintext_token: str,
    *,
    scopes: list[str] | None = None,
) -> None:
    resolved_scopes = scopes or [
        "memory:read",
        "memory:write",
        "facts:read",
        "facts:write",
        "entities:read",
        "graph:read",
        "ops:read",
        "delete:write",
        "timeline:read",
    ]
    connection = await asyncpg.connect(_DATABASE_URL)
    try:
        await connection.execute(
            """
            insert into projects (id, name, owner_id, plan, retention_days, isolation_mode)
            values ($1, $2, $3, $4, $5, $6)
            """,
            project_id,
            "Runtime E2E Celery",
            "runtime-e2e",
            "pro",
            30,
            "falkordb_graph",
        )
        await connection.execute(
            """
            insert into mcp_tokens (token_id, prefix, token_hash, project_id, scopes, plan)
            values ($1, $2, $3, $4, $5, $6)
            """,
            token_id,
            plaintext_token[:16],
            hash_token(plaintext_token),
            project_id,
            resolved_scopes,
            "pro",
        )
    finally:
        await connection.close()


async def _get_episode_status(episode_id: str) -> str | None:
    connection = await asyncpg.connect(_DATABASE_URL)
    try:
        return await connection.fetchval(
            "select enrichment_status from episodes where episode_id = $1",
            episode_id,
        )
    finally:
        await connection.close()


async def _count_usage_events(project_id: str, tool_name: str) -> int:
    connection = await asyncpg.connect(_DATABASE_URL)
    try:
        return int(
            await connection.fetchval(
                """
                select count(*)
                from usage_events
                where project_id = $1
                  and tool = $2
                """,
                project_id,
                tool_name,
            )
            or 0
        )
    finally:
        await connection.close()


async def _count_audit_logs(project_id: str, action: str, status_text: str) -> int:
    connection = await asyncpg.connect(_DATABASE_URL)
    try:
        return int(
            await connection.fetchval(
                """
                select count(*)
                from audit_logs
                where project_id = $1
                  and action = $2
                  and status = $3
                """,
                project_id,
                action,
                status_text,
            )
            or 0
        )
    finally:
        await connection.close()


async def _cleanup_project_data(project_id: str) -> None:
    connection = await asyncpg.connect(_DATABASE_URL)
    try:
        await connection.execute("delete from usage_events where project_id = $1", project_id)
        await connection.execute("delete from audit_logs where project_id = $1", project_id)
        await connection.execute("delete from episodes where project_id = $1", project_id)
        await connection.execute("delete from mcp_tokens where project_id = $1", project_id)
        await connection.execute("delete from webhooks where project_id = $1", project_id)
        await connection.execute("delete from projects where id = $1", project_id)
    finally:
        await connection.close()


def _wait_until(predicate, *, timeout_seconds: float, interval_seconds: float = 0.5) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_seconds)
    return False


async def _wait_until_async(predicate, *, timeout_seconds: float, interval_seconds: float = 0.5) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if await predicate():
            return True
        await asyncio.sleep(interval_seconds)
    return False


@pytest.mark.asyncio
async def test_runtime_e2e_celery_worker_flow(monkeypatch) -> None:
    project_id = new_id("proj")
    token_id = new_id("tok")
    token_plaintext = f"vr_mcp_sk_{secrets.token_urlsafe(24)}"
    admin = FalkorDBGraphManager()
    redis = redis_async.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    try:
        # Connectivity pre-checks for optional e2e mode.
        try:
            await redis.ping()
            probe_project = f"{project_id}_probe"
            await admin.ensure_project_graph(probe_project)
            await admin.reset_graph(probe_project)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Runtime e2e dependencies are unavailable: {exc}")

        monkeypatch.setattr(runtime.settings, "memory_backend", "falkordb")
        monkeypatch.setattr(runtime.settings, "kv_backend", "redis")
        monkeypatch.setattr(runtime.settings, "queue_backend", "celery")
        celery_app.conf.task_always_eager = False

        await _create_project_token(project_id, token_id, token_plaintext)

        worker_env = {
            **os.environ,
            "MEMORY_BACKEND": "falkordb",
            "KV_BACKEND": "redis",
            "QUEUE_BACKEND": "celery",
        }

        with _run_celery_worker(worker_env):
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    session_id = await _initialize_session(client, project_id)

                    save_payload = await _call_tool(
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

                    async def _episode_complete() -> bool:
                        return await _get_episode_status(episode_id) == "complete"

                    completed = await _wait_until_async(_episode_complete, timeout_seconds=25)
                    assert completed, "Episode enrichment did not complete via Celery worker in time"

                    search_payload = await _call_tool(
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

                    facts_payload = await _call_tool(
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

                    update_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="e2e-update",
                        tool_name="viberecall_update_fact",
                        idempotency_key="e2e-celery-update-1",
                        arguments={
                            "fact_id": old_fact_id,
                            "new_text": "Fix callback auth race in celery runtime e2e flow (updated)",
                            "effective_time": datetime.now(timezone.utc).isoformat(),
                            "reason": "integration e2e verification",
                        },
                    )
                    assert update_payload["ok"] is True
                    update_operation_id = update_payload["result"]["operation_id"]
                    assert update_operation_id

                    async def _update_operation_succeeded() -> bool:
                        current = await _call_tool(
                            client,
                            project_id=project_id,
                            session_id=session_id,
                            token=token_plaintext,
                            request_id="e2e-update-operation",
                            tool_name="viberecall_get_operation",
                            arguments={"operation_id": update_operation_id},
                        )
                        operation = current["result"]["operation"]
                        return operation["status"] == "SUCCEEDED"

                    updated = await _wait_until_async(_update_operation_succeeded, timeout_seconds=25)
                    assert updated, "Update operation did not reach SUCCEEDED via Celery processing"

        usage_save = await _count_usage_events(project_id, "viberecall_save")
        audit_ingest = await _count_audit_logs(project_id, "worker/ingest", "complete")
        assert usage_save >= 1
        assert audit_ingest >= 1
    finally:
        await _cleanup_project_data(project_id)
        cleanup_admin = FalkorDBGraphManager()
        try:
            await cleanup_admin.reset_graph(project_id)
        finally:
            await cleanup_admin.close()
        await dispose_engine()
        await redis.aclose()
        await admin.close()


@pytest.mark.asyncio
async def test_runtime_e2e_canonical_and_ops_roundtrip(monkeypatch) -> None:
    project_id = new_id("proj")
    token_id = new_id("tok")
    token_plaintext = f"vr_mcp_sk_{secrets.token_urlsafe(24)}"
    admin = FalkorDBGraphManager()
    redis = redis_async.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    try:
        try:
            await redis.ping()
            probe_project = f"{project_id}_probe"
            await admin.ensure_project_graph(probe_project)
            await admin.reset_graph(probe_project)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Runtime e2e dependencies are unavailable: {exc}")

        monkeypatch.setattr(runtime.settings, "memory_backend", "falkordb")
        monkeypatch.setattr(runtime.settings, "kv_backend", "redis")
        monkeypatch.setattr(runtime.settings, "queue_backend", "celery")
        celery_app.conf.task_always_eager = False

        await _create_project_token(project_id, token_id, token_plaintext)

        worker_env = {
            **os.environ,
            "MEMORY_BACKEND": "falkordb",
            "KV_BACKEND": "redis",
            "QUEUE_BACKEND": "celery",
        }

        with _run_celery_worker(worker_env):
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    session_id = await _initialize_session(client, project_id)
                    marker = f"runtime-canonical-{secrets.token_hex(4)}"
                    task_id = f"task-{marker}"
                    wm_session_id = f"session-{marker}"
                    tag = f"{marker}-tag"

                    save_episode_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-save-episode",
                        tool_name="viberecall_save_episode",
                        idempotency_key=f"runtime-canonical-save:{marker}",
                        arguments={
                            "content": f"Canonical runtime smoke {marker}",
                            "metadata": {"tags": [tag], "type": "runtime-smoke"},
                        },
                    )
                    assert save_episode_payload["ok"] is True
                    fact_group_id = save_episode_payload["result"]["fact_group_id"]
                    fact_version_id = save_episode_payload["result"]["fact_version_id"]
                    operation_id = save_episode_payload["result"]["operation_id"]

                    operation_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-get-operation",
                        tool_name="viberecall_get_operation",
                        arguments={"operation_id": operation_id},
                    )
                    assert operation_payload["ok"] is True
                    assert operation_payload["result"]["operation"]["operation_id"] == operation_id

                    status_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-get-status",
                        tool_name="viberecall_get_status",
                        arguments={},
                    )
                    assert status_payload["ok"] is True
                    assert status_payload["result"]["project_id"] == project_id

                    get_fact_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-get-fact",
                        tool_name="viberecall_get_fact",
                        arguments={"fact_group_id": fact_group_id},
                    )
                    assert get_fact_payload["ok"] is True
                    assert get_fact_payload["result"]["current"]["fact_version_id"] == fact_version_id

                    pin_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-pin-fact",
                        tool_name="viberecall_pin_memory",
                        arguments={
                            "target_kind": "FACT",
                            "target_id": fact_group_id,
                            "pin_action": "PIN",
                        },
                    )
                    assert pin_payload["ok"] is True
                    assert pin_payload["result"]["resolved_target"]["fact_group_id"] == fact_group_id

                    pinned_fact_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-get-fact-pinned",
                        tool_name="viberecall_get_fact",
                        arguments={"fact_group_id": fact_group_id},
                    )
                    assert pinned_fact_payload["ok"] is True
                    assert pinned_fact_payload["result"]["current"]["salience_class"] == "PINNED"

                    search_memory_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-search-memory",
                        tool_name="viberecall_search_memory",
                        arguments={"query": marker, "limit": 10},
                    )
                    assert search_memory_payload["ok"] is True
                    facts_by_group_id = {
                        item.get("fact_group_id"): item for item in search_memory_payload["result"]["facts"]
                    }
                    assert fact_group_id in facts_by_group_id
                    assert facts_by_group_id[fact_group_id]["salience_class"] == "PINNED"

                    search_entities_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-search-entities",
                        tool_name="viberecall_search_entities",
                        arguments={"query": tag, "entity_kinds": ["Tag"], "limit": 10},
                    )
                    assert search_entities_payload["ok"] is True
                    assert search_entities_payload["result"]["entities"][0]["name"] == tag

                    resolve_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-resolve-reference",
                        tool_name="viberecall_resolve_reference",
                        arguments={"mention_text": tag, "observed_kind": "Tag", "limit": 5},
                    )
                    assert resolve_payload["ok"] is True
                    assert resolve_payload["result"]["status"] == "RESOLVED"
                    assert resolve_payload["result"]["best_match"]["entity_id"]

                    wm_patch_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-working-memory-patch",
                        tool_name="viberecall_working_memory_patch",
                        arguments={
                            "task_id": task_id,
                            "session_id": wm_session_id,
                            "patch": {"plan": ["runtime canonical smoke"], "active_constraints": {"marker": marker}},
                            "checkpoint_note": "runtime canonical smoke",
                        },
                    )
                    assert wm_patch_payload["ok"] is True

                    wm_get_payload = await _call_tool(
                        client,
                        project_id=project_id,
                        session_id=session_id,
                        token=token_plaintext,
                        request_id="canonical-working-memory-get",
                        tool_name="viberecall_working_memory_get",
                        arguments={"task_id": task_id, "session_id": wm_session_id},
                    )
                    assert wm_get_payload["ok"] is True
                    assert wm_get_payload["result"]["state"]["active_constraints"]["marker"] == marker
    finally:
        await _cleanup_project_data(project_id)
        cleanup_admin = FalkorDBGraphManager()
        try:
            await cleanup_admin.reset_graph(project_id)
        finally:
            await cleanup_admin.close()
        await dispose_engine()
        await redis.aclose()
        await admin.close()
