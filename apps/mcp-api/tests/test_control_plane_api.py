from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from viberecall_mcp import control_plane
from viberecall_mcp.app import create_app
from viberecall_mcp.control_plane_auth import AuthenticatedControlPlaneUser
from viberecall_mcp.db import get_db_session


class DummySession:
    async def commit(self) -> None:
        return None


async def override_session() -> AsyncIterator[DummySession]:
    yield DummySession()


def auth_headers() -> dict[str, str]:
    return {
        "X-Control-Plane-Secret": "dev-control-plane-secret",
        "X-Control-Plane-User-Id": "user_123",
        "X-Control-Plane-User-Email": "dev@example.com",
    }


def override_user() -> AuthenticatedControlPlaneUser:
    return AuthenticatedControlPlaneUser(user_id="user_123", user_email="dev@example.com")


def test_list_projects_returns_owner_scoped_projects(monkeypatch) -> None:
    async def fake_list_projects_for_owner(_session, *, owner_id: str, include_unowned: bool):
        assert owner_id == "user_123"
        assert include_unowned is True
        return [
            {
                "id": "proj_1",
                "name": "Project A",
                "owner_id": "user_123",
                "plan": "free",
                "created_at": "2026-02-28T10:00:00Z",
            }
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "list_projects_for_owner", fake_list_projects_for_owner)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get("/api/control-plane/projects", headers=auth_headers())

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["projects"] == [
        {
            "id": "proj_1",
            "name": "Project A",
            "plan": "free",
            "created_at": "2026-02-28T10:00:00Z",
        }
    ]


def test_create_project_returns_plaintext_token(monkeypatch) -> None:
    async def fake_create_project(_session, **_kwargs):
        return {
            "id": "proj_abc",
            "name": "New Project",
            "owner_id": "user_123",
            "plan": "free",
            "created_at": "2026-02-28T10:00:00Z",
        }

    async def fake_create_token(_session, **_kwargs):
        return {
            "token_id": "tok_abc",
            "prefix": "vr_mcp_sk_abcd",
            "created_at": "2026-02-28T10:01:00Z",
            "last_used_at": None,
            "revoked_at": None,
            "expires_at": None,
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        control_plane,
        "_build_token_create_payload",
        lambda **_kwargs: (
            "tok_abc",
            "vr_mcp_sk_plaintext",
            "vr_mcp_sk_abcd",
            "hash",
            ["memory:read"],
            "proj_abc",
            None,
        ),
    )

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "create_project", fake_create_project)
    monkeypatch.setattr(control_plane, "create_token", fake_create_token)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/projects",
            headers=auth_headers(),
            json={"name": "New Project", "plan": "free"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["project"]["id"] == "proj_abc"
    assert body["token"]["plaintext"] == "vr_mcp_sk_plaintext"
    assert body["connection"]["endpoint"].endswith("/p/proj_abc/mcp")


def test_rotate_token_sets_grace_and_returns_new_plaintext(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_get_token_for_project(_session, **_kwargs):
        return {
            "token_id": "tok_old",
            "prefix": "vr_mcp_sk_old",
            "created_at": "2026-02-28T09:00:00Z",
            "last_used_at": None,
            "revoked_at": None,
            "expires_at": None,
        }

    async def fake_set_token_revoked_at(_session, **kwargs):
        revoked_at = kwargs["revoked_at"]
        return {
            "token_id": "tok_old",
            "prefix": "vr_mcp_sk_old",
            "created_at": "2026-02-28T09:00:00Z",
            "last_used_at": None,
            "revoked_at": revoked_at,
            "expires_at": None,
        }

    async def fake_create_token(_session, **_kwargs):
        return {
            "token_id": "tok_new",
            "prefix": "vr_mcp_sk_new",
            "created_at": "2026-02-28T10:00:00Z",
            "last_used_at": None,
            "revoked_at": None,
            "expires_at": None,
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        control_plane,
        "_build_token_create_payload",
        lambda **_kwargs: (
            "tok_new",
            "vr_mcp_sk_plaintext_new",
            "vr_mcp_sk_new",
            "hash_new",
            ["facts:write"],
            "proj_1",
            None,
        ),
    )

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_token_for_project", fake_get_token_for_project)
    monkeypatch.setattr(control_plane, "set_token_revoked_at", fake_set_token_revoked_at)
    monkeypatch.setattr(control_plane, "create_token", fake_create_token)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/projects/proj_1/tokens/tok_old/rotate",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["new_token"]["plaintext"] == "vr_mcp_sk_plaintext_new"
    assert body["old_token"]["status"] in {"grace", "revoked"}


def test_control_plane_requires_internal_secret() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/control-plane/projects")
    assert response.status_code == 401


def test_token_status_grace_window() -> None:
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)

    assert control_plane._token_status({"revoked_at": None}) == "active"
    assert control_plane._token_status({"revoked_at": future}) == "grace"
    assert control_plane._token_status({"revoked_at": past}) == "revoked"


def test_project_usage_returns_rollup(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_get_usage_rollup(_session, *, project_id: str, period: str):
        assert project_id == "proj_1"
        assert period == "daily"
        return {
            "period": "daily",
            "vibe_tokens": 33,
            "in_tokens": 100,
            "out_tokens": 200,
            "event_count": 5,
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_usage_rollup", fake_get_usage_rollup)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/usage?period=daily",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["usage"]["vibe_tokens"] == 33


def test_project_usage_series_returns_buckets(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_get_usage_series(_session, *, project_id: str, window_days: int, bucket: str):
        assert project_id == "proj_1"
        assert window_days == 7
        assert bucket == "day"
        return [
            {
                "bucket_start": "2026-03-01T00:00:00Z",
                "vibe_tokens": 7,
                "in_tokens": 70,
                "out_tokens": 14,
                "event_count": 2,
            }
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_usage_series", fake_get_usage_series)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/usage/series?window_days=7&bucket=day",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 7
    assert body["bucket"] == "day"
    assert body["series"][0]["vibe_tokens"] == 7


def test_project_billing_overview_returns_metrics(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_get_billing_usage_snapshot(_session, *, project_id: str):
        assert project_id == "proj_1"
        return {
            "current_month_vibe_tokens": 1200,
            "current_month_events": 12,
            "last_7d_vibe_tokens": 420,
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_billing_usage_snapshot", fake_get_billing_usage_snapshot)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/billing/overview",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "proj_1"
    assert body["plan"] == "pro"
    assert body["current_month_vibe_tokens"] == 1200
    assert body["current_month_events"] == 12
    assert body["last_7d_vibe_tokens"] == 420
    assert body["monthly_quota_vibe_tokens"] == 5_000_000
    assert body["remaining_vibe_tokens"] == 4_998_800
    assert body["projected_month_vibe_tokens"] >= 1200


def test_project_api_logs_returns_paginated_rows(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_list_audit_logs_for_project(
        _session,
        *,
        project_id: str,
        limit: int,
        cursor: int | None = None,
    ):
        assert project_id == "proj_1"
        assert limit == 3
        assert cursor is None
        return [
            {
                "id": 200,
                "request_id": "req_200",
                "project_id": "proj_1",
                "token_id": "tok_1",
                "tool_name": "viberecall_save",
                "action": "worker/save",
                "args_hash": "hash_1",
                "status": "ok",
                "created_at": "2026-03-01T10:00:00Z",
            },
            {
                "id": 199,
                "request_id": "req_199",
                "project_id": "proj_1",
                "token_id": "tok_1",
                "tool_name": "viberecall_search",
                "action": "worker/search",
                "args_hash": "hash_2",
                "status": "ok",
                "created_at": "2026-03-01T09:59:00Z",
            },
            {
                "id": 198,
                "request_id": "req_198",
                "project_id": "proj_1",
                "token_id": "tok_1",
                "tool_name": "viberecall_timeline",
                "action": "worker/timeline",
                "args_hash": "hash_3",
                "status": "ok",
                "created_at": "2026-03-01T09:58:00Z",
            },
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "list_audit_logs_for_project", fake_list_audit_logs_for_project)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/api-logs?limit=2",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert len(body["logs"]) == 2
    assert body["logs"][0]["id"] == 200
    assert body["next_cursor"] == 199


def test_project_api_logs_rejects_invalid_limit(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/api-logs?limit=0",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"] == "limit must be between 1 and 200"


def test_projects_overview_returns_owner_scoped_rows(monkeypatch) -> None:
    async def fake_list_project_overview_for_owner(
        _session,
        *,
        owner_id: str,
        include_unowned: bool,
        window_days: int,
    ):
        assert owner_id == "user_123"
        assert include_unowned is True
        assert window_days == 30
        return [
            {
                "id": "proj_1",
                "name": "Project A",
                "plan": "free",
                "created_at": "2026-03-01T00:00:00Z",
                "last_activity_at": "2026-03-01T10:00:00Z",
                "vibe_tokens_window": 12,
                "token_preview": "vr_mcp_sk_abcd",
                "token_status": "active",
                "health_status": "active",
            }
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(
        control_plane,
        "list_project_overview_for_owner",
        fake_list_project_overview_for_owner,
    )
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/overview?window_days=30",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 30
    assert len(body["projects"]) == 1
    assert body["projects"][0]["token_status"] == "active"


def test_run_retention_enqueues_job(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123", "retention_days": 30}

    async def fake_audit(*_args, **_kwargs):
        return None

    class FakeQueue:
        async def enqueue_retention(self, **_kwargs):
            return "job_retention_1"

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)
    monkeypatch.setattr(control_plane, "get_task_queue", lambda: FakeQueue())

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/projects/proj_1/retention/run",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["job"]["job_id"] == "job_retention_1"
    assert body["job"]["kind"] == "retention"
    assert body["job"]["retention_days"] == 30


def test_purge_project_enqueues_job_with_idempotency(monkeypatch) -> None:
    calls = {"count": 0}

    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_audit(*_args, **_kwargs):
        return None

    class FakeQueue:
        async def enqueue_purge_project(self, **_kwargs):
            calls["count"] += 1
            return "job_purge_1"

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)
    monkeypatch.setattr(control_plane, "get_task_queue", lambda: FakeQueue())

    with TestClient(app) as client:
        first = client.post(
            "/api/control-plane/projects/proj_1/purge",
            headers=auth_headers() | {"Idempotency-Key": "idem-purge-1"},
        )
        second = client.post(
            "/api/control-plane/projects/proj_1/purge",
            headers=auth_headers() | {"Idempotency-Key": "idem-purge-1"},
        )

    app.dependency_overrides.clear()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job"]["job_id"] == "job_purge_1"
    assert second.json()["job"]["job_id"] == "job_purge_1"
    assert calls["count"] == 1


def test_migrate_inline_to_object_enqueues_job_with_idempotency(monkeypatch) -> None:
    calls = {"count": 0}

    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_audit(*_args, **_kwargs):
        return None

    class FakeQueue:
        async def enqueue_migrate_inline_to_object(self, **_kwargs):
            calls["count"] += 1
            return "job_migrate_1"

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)
    monkeypatch.setattr(control_plane, "get_task_queue", lambda: FakeQueue())

    with TestClient(app) as client:
        first = client.post(
            "/api/control-plane/projects/proj_1/migrate-inline-to-object",
            headers=auth_headers() | {"Idempotency-Key": "idem-migrate-1"},
            json={"force": True},
        )
        second = client.post(
            "/api/control-plane/projects/proj_1/migrate-inline-to-object",
            headers=auth_headers() | {"Idempotency-Key": "idem-migrate-1"},
            json={"force": True},
        )

    app.dependency_overrides.clear()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job"]["job_id"] == "job_migrate_1"
    assert first.json()["job"]["kind"] == "migrate_inline_to_object"
    assert first.json()["job"]["force"] is True
    assert calls["count"] == 1


def test_stripe_webhook_updates_project_plan(monkeypatch) -> None:
    async def fake_update_project_plan(_session, *, project_id: str, plan: str):
        assert project_id == "proj_1"
        assert plan == "pro"
        return {
            "id": "proj_1",
            "name": "Project 1",
            "plan": "pro",
        }

    async def fake_insert_audit_log(*_args, **_kwargs):
        return None

    async def fake_begin_webhook_event(_session, **_kwargs):
        return True

    async def fake_mark_webhook_event_status(_session, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    monkeypatch.setattr(control_plane, "update_project_plan", fake_update_project_plan)
    monkeypatch.setattr(control_plane, "insert_audit_log", fake_insert_audit_log)
    monkeypatch.setattr(control_plane, "begin_webhook_event", fake_begin_webhook_event)
    monkeypatch.setattr(control_plane, "mark_webhook_event_status", fake_mark_webhook_event_status)

    payload = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"project_id": "proj_1", "plan": "pro"},
            }
        },
    }
    raw = json.dumps(payload)
    timestamp = int(datetime.now(timezone.utc).timestamp())
    signed_payload = f"{timestamp}.{raw}"
    signature = hmac.new(
        control_plane.settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    header = f"t={timestamp},v1={signature}"

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/stripe/webhook",
            headers={"Stripe-Signature": header, "Content-Type": "application/json"},
            content=raw,
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["received"] is True
    assert body["processed"] is True
    assert body["duplicate"] is False


def test_stripe_webhook_duplicate_event_is_not_reprocessed(monkeypatch) -> None:
    update_calls = 0

    async def fake_update_project_plan(_session, *, project_id: str, plan: str):
        nonlocal update_calls
        update_calls += 1
        return {"id": project_id, "plan": plan}

    async def fake_insert_audit_log(*_args, **_kwargs):
        return None

    async def fake_begin_webhook_event(_session, **_kwargs):
        return False

    payload = {
        "id": "evt_duplicated",
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"project_id": "proj_1", "plan": "pro"}}},
    }
    raw = json.dumps(payload)
    payload_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def fake_get_webhook_event(_session, **_kwargs):
        return {"status": "processed", "payload_hash": payload_hash}

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    monkeypatch.setattr(control_plane, "update_project_plan", fake_update_project_plan)
    monkeypatch.setattr(control_plane, "insert_audit_log", fake_insert_audit_log)
    monkeypatch.setattr(control_plane, "begin_webhook_event", fake_begin_webhook_event)
    monkeypatch.setattr(control_plane, "get_webhook_event", fake_get_webhook_event)

    timestamp = int(datetime.now(timezone.utc).timestamp())
    signed_payload = f"{timestamp}.{raw}"
    signature = hmac.new(
        control_plane.settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    header = f"t={timestamp},v1={signature}"

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/stripe/webhook",
            headers={"Stripe-Signature": header, "Content-Type": "application/json"},
            content=raw,
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["received"] is True
    assert body["processed"] is True
    assert body["duplicate"] is True
    assert update_calls == 0


def test_stripe_webhook_failed_event_is_retried(monkeypatch) -> None:
    update_calls = 0
    marked_statuses: list[str] = []

    async def fake_update_project_plan(_session, *, project_id: str, plan: str):
        nonlocal update_calls
        update_calls += 1
        return {"id": project_id, "plan": plan}

    async def fake_insert_audit_log(*_args, **_kwargs):
        return None

    async def fake_begin_webhook_event(_session, **_kwargs):
        return False

    payload = {
        "id": "evt_retry",
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"project_id": "proj_1", "plan": "pro"}}},
    }
    raw = json.dumps(payload)
    payload_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def fake_get_webhook_event(_session, **_kwargs):
        return {"status": "failed", "payload_hash": payload_hash}

    async def fake_mark_webhook_event_status(_session, *, status: str, **_kwargs):
        marked_statuses.append(status)
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    monkeypatch.setattr(control_plane, "update_project_plan", fake_update_project_plan)
    monkeypatch.setattr(control_plane, "insert_audit_log", fake_insert_audit_log)
    monkeypatch.setattr(control_plane, "begin_webhook_event", fake_begin_webhook_event)
    monkeypatch.setattr(control_plane, "get_webhook_event", fake_get_webhook_event)
    monkeypatch.setattr(control_plane, "mark_webhook_event_status", fake_mark_webhook_event_status)

    timestamp = int(datetime.now(timezone.utc).timestamp())
    signed_payload = f"{timestamp}.{raw}"
    signature = hmac.new(
        control_plane.settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    header = f"t={timestamp},v1={signature}"

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/stripe/webhook",
            headers={"Stripe-Signature": header, "Content-Type": "application/json"},
            content=raw,
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["processed"] is True
    assert body["duplicate"] is False
    assert update_calls == 1
    assert marked_statuses == ["processing", "processed"]


def test_stripe_webhook_duplicate_payload_mismatch_returns_conflict(monkeypatch) -> None:
    async def fake_insert_audit_log(*_args, **_kwargs):
        return None

    async def fake_begin_webhook_event(_session, **_kwargs):
        return False

    async def fake_get_webhook_event(_session, **_kwargs):
        return {"status": "processed", "payload_hash": "different_hash_value"}

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    monkeypatch.setattr(control_plane, "insert_audit_log", fake_insert_audit_log)
    monkeypatch.setattr(control_plane, "begin_webhook_event", fake_begin_webhook_event)
    monkeypatch.setattr(control_plane, "get_webhook_event", fake_get_webhook_event)

    payload = {
        "id": "evt_mismatch",
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"project_id": "proj_1", "plan": "pro"}}},
    }
    raw = json.dumps(payload)
    timestamp = int(datetime.now(timezone.utc).timestamp())
    signed_payload = f"{timestamp}.{raw}"
    signature = hmac.new(
        control_plane.settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    header = f"t={timestamp},v1={signature}"

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/stripe/webhook",
            headers={"Stripe-Signature": header, "Content-Type": "application/json"},
            content=raw,
        )

    app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["detail"] == "Duplicate Stripe event id with different payload"


def test_create_export_enqueues_job_and_returns_record(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_create_export(_session, **_kwargs):
        return {
            "export_id": "exp_1",
            "project_id": "proj_1",
            "status": "pending",
            "format": "json_v1",
            "object_url": None,
            "expires_at": None,
            "error": None,
            "requested_by": "user_123",
            "requested_at": "2026-02-28T10:00:00Z",
            "completed_at": None,
            "job_id": None,
        }

    async def fake_set_export_job_id(_session, **_kwargs):
        return None

    async def fake_get_export(_session, **_kwargs):
        return {
            "export_id": "exp_1",
            "project_id": "proj_1",
            "status": "pending",
            "format": "json_v1",
            "object_url": None,
            "expires_at": None,
            "error": None,
            "requested_by": "user_123",
            "requested_at": "2026-02-28T10:00:00Z",
            "completed_at": None,
            "job_id": "job_export_1",
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    class FakeQueue:
        async def enqueue_export(self, **_kwargs):
            return "job_export_1"

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "create_export", fake_create_export)
    monkeypatch.setattr(control_plane, "set_export_job_id", fake_set_export_job_id)
    monkeypatch.setattr(control_plane, "get_export", fake_get_export)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)
    monkeypatch.setattr(control_plane, "get_task_queue", lambda: FakeQueue())

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/projects/proj_1/exports",
            headers=auth_headers() | {"Idempotency-Key": "idem-export-1"},
            json={"format": "json_v1"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["export"]["export_id"] == "exp_1"
    assert body["export"]["job_id"] == "job_export_1"


def test_get_export_refreshes_signed_url_when_expired(monkeypatch) -> None:
    calls = {"count": 0}

    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_get_export(_session, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "export_id": "exp_1",
                "project_id": "proj_1",
                "status": "complete",
                "format": "json_v1",
                "object_key": "projects/proj_1/exports/exp_1.json",
                "object_url": "http://old",
                "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
                "error": None,
                "requested_by": "user_123",
                "requested_at": "2026-02-28T10:00:00Z",
                "completed_at": "2026-02-28T10:01:00Z",
                "job_id": "job_export_1",
            }
        return {
            "export_id": "exp_1",
            "project_id": "proj_1",
            "status": "complete",
            "format": "json_v1",
            "object_key": "projects/proj_1/exports/exp_1.json",
            "object_url": "http://new",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            "error": None,
            "requested_by": "user_123",
            "requested_at": "2026-02-28T10:00:00Z",
            "completed_at": "2026-02-28T10:01:00Z",
            "job_id": "job_export_1",
        }

    async def fake_refresh_export_url(_session, **_kwargs):
        return None

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(control_plane, "build_signed_download", lambda **_kwargs: ("http://new", datetime.now(timezone.utc) + timedelta(minutes=10)))

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_export", fake_get_export)
    monkeypatch.setattr(control_plane, "refresh_export_url", fake_refresh_export_url)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/exports/exp_1",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["export"]["object_url"] == "http://new"


def test_download_export_returns_json_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(control_plane.settings, "export_local_dir", str(tmp_path))
    object_key = "projects/proj_1/exports/exp_1.json"
    export_path = tmp_path / object_key
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text('{"format":"viberecall-export","version":"1.0"}', encoding="utf-8")

    async def fake_get_export(_session, **_kwargs):
        return {
            "export_id": "exp_1",
            "project_id": "proj_1",
            "status": "complete",
            "object_key": object_key,
        }

    monkeypatch.setattr(control_plane, "verify_download_signature", lambda **_kwargs: True)
    monkeypatch.setattr(control_plane, "get_export", fake_get_export)

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/exports/exp_1/download?expires=9999999999&sig=ok",
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
