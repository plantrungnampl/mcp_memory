from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from fastapi.testclient import TestClient

from viberecall_mcp import app as app_module
from viberecall_mcp import control_plane
from viberecall_mcp.app import create_app
from viberecall_mcp.auth import AuthenticatedToken
from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane_assertion import (
    ControlPlaneAssertionClaims as AuthenticatedControlPlaneUser,
    create_control_plane_assertion,
)
from viberecall_mcp.db import get_db_session


class DummySession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


async def override_session() -> AsyncIterator[DummySession]:
    yield DummySession()


def auth_headers() -> dict[str, str]:
    return {
        "X-Control-Plane-Assertion": create_control_plane_assertion(
            secret=get_settings().control_plane_internal_secret,
            user_id="user_123",
            user_email="dev@example.com",
        ),
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


def test_runtime_index_bundle_upload_accepts_mcp_token(monkeypatch) -> None:
    stored: dict[str, object] = {}

    async def fake_auth(_session, *, authorization, project_id):
        assert authorization == "Bearer test-token"
        assert project_id == "proj_upload"
        return AuthenticatedToken(
            token_id="tok_test",
            project_id=project_id,
            scopes=["index:run"],
            plan="free",
            db_name=f"vr_{project_id}",
        )

    async def fake_put_bytes(*, object_key: str, content: bytes, content_type: str = "application/octet-stream") -> None:
        stored["object_key"] = object_key
        stored["content"] = content
        stored["content_type"] = content_type

    async def fake_create_index_bundle(_session, **kwargs):
        stored["bundle_kwargs"] = kwargs
        return {
            "bundle_id": kwargs["bundle_id"],
            "filename": kwargs["filename"],
            "byte_size": kwargs["byte_size"],
            "sha256": kwargs["sha256"],
            "created_at": "2026-03-09T12:00:00Z",
            "expires_at": None,
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(app_module, "authenticate_bearer_token", fake_auth)
    monkeypatch.setattr(app_module, "put_bytes", fake_put_bytes)
    monkeypatch.setattr(app_module, "create_index_bundle", fake_create_index_bundle)
    monkeypatch.setattr(app_module, "insert_audit_log", fake_audit)

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session

    with TestClient(app) as client:
        response = client.post(
            "/p/proj_upload/index-bundles",
            headers={"authorization": "Bearer test-token"},
            files={
                "file": (
                    "workspace.zip",
                    _valid_bundle_bytes(),
                    "application/zip",
                )
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["bundle"]["bundle_ref"].startswith("bundle://bundle_")
    assert body["bundle"]["filename"] == "workspace.zip"
    assert stored["content_type"] == "application/zip"


def test_runtime_index_bundle_upload_requires_index_scope(monkeypatch) -> None:
    async def fake_auth(_session, *, authorization, project_id):
        _ = (authorization, project_id)
        return AuthenticatedToken(
            token_id="tok_test",
            project_id="proj_upload",
            scopes=["memory:read"],
            plan="free",
            db_name="vr_proj_upload",
        )

    monkeypatch.setattr(app_module, "authenticate_bearer_token", fake_auth)

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session

    with TestClient(app) as client:
        response = client.post(
            "/p/proj_upload/index-bundles",
            headers={"authorization": "Bearer test-token"},
            files={"file": ("workspace.zip", _valid_bundle_bytes(), "application/zip")},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "Missing required scope: index:run"


def test_runtime_index_bundle_upload_rejects_invalid_manifest(monkeypatch) -> None:
    async def fake_auth(_session, *, authorization, project_id):
        _ = (authorization, project_id)
        return AuthenticatedToken(
            token_id="tok_test",
            project_id="proj_upload",
            scopes=["index:run"],
            plan="free",
            db_name="vr_proj_upload",
        )

    monkeypatch.setattr(app_module, "authenticate_bearer_token", fake_auth)

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session

    with TestClient(app) as client:
        response = client.post(
            "/p/proj_upload/index-bundles",
            headers={"authorization": "Bearer test-token"},
            files={"file": ("workspace.zip", b"not-a-zip", "application/zip")},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 422


def _valid_bundle_bytes() -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format_version": 1,
                    "repo_name": "demo",
                    "root_relative": ".",
                    "generated_at": "2026-03-09T12:00:00Z",
                    "git": None,
                    "files": [{"path": "src/demo.py", "sha256": "x", "size_bytes": 1, "mode": "0644"}],
                }
            ),
        )
        archive.writestr("src/demo.py", "x")
    return buffer.getvalue()


def test_control_plane_echoes_request_id_on_success(monkeypatch) -> None:
    async def fake_list_projects_for_owner(_session, *, owner_id: str, include_unowned: bool):
        assert owner_id == "user_123"
        assert include_unowned is True
        return []

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    monkeypatch.setattr(control_plane, "list_projects_for_owner", fake_list_projects_for_owner)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects",
            headers={
                **auth_headers(),
                "X-Request-Id": "req_trace_success",
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req_trace_success"


def test_control_plane_generates_request_id_for_unauthenticated_failure() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/control-plane/projects")

    assert response.status_code == 401
    assert response.headers["X-Request-Id"].startswith("req_")


def test_healthz_returns_dependency_probe_payload(monkeypatch) -> None:
    async def fake_probe() -> dict:
        return {
            "status": "degraded",
            "runtime": {
                "memory_backend": "falkordb",
                "kv_backend": "local",
                "queue_backend": "eager",
                "falkordb_target": "localhost:6380",
            },
            "checks": {
                "falkordb": {
                    "status": "error",
                    "detail": "Connection refused",
                }
            },
        }

    monkeypatch.setattr(app_module, "probe_runtime_dependencies", fake_probe)
    app = app_module.create_app()

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["service"] == "viberecall-mcp"
    assert body["runtime"]["memory_backend"] == "falkordb"
    assert body["checks"]["falkordb"]["status"] == "error"


def test_build_project_index_summary_reports_stalled_queue() -> None:
    summary = control_plane._build_project_index_summary(
        {
            "status": "QUEUED",
            "current_run": {
                "index_run_id": "idx_queue",
                "queued_at": "2026-03-14T11:55:00Z",
                "started_at": None,
                "completed_at": None,
                "error": None,
            },
            "latest_ready_snapshot": None,
        },
        now=datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert summary["status"] == "stalled"
    assert summary["recommended_action"] == "check_workers"
    assert summary["current_run_id"] == "idx_queue"
    assert summary["age_seconds"] == 300


def test_build_project_index_summary_prefers_latest_ready_snapshot() -> None:
    summary = control_plane._build_project_index_summary(
        {
            "status": "READY",
            "current_run": None,
            "latest_ready_snapshot": {
                "index_run_id": "idx_ready",
                "indexed_at": "2026-03-14T11:58:00Z",
            },
        },
        now=datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert summary["status"] == "ready"
    assert summary["recommended_action"] == "none"
    assert summary["latest_ready_at"] == "2026-03-14T11:58:00Z"
    assert summary["age_seconds"] == 120


def test_control_plane_index_status_route_returns_summary(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_index", "plan": "pro", "owner_id": "user_123"}

    async def fake_index_status(*, session, project_id: str, index_run_id: str | None = None):
        _ = session
        assert project_id == "proj_index"
        assert index_run_id is None
        return {
            "status": "FAILED",
            "current_run": {
                "index_run_id": "idx_failed",
                "queued_at": "2026-03-14T11:57:00Z",
                "started_at": "2026-03-14T11:58:00Z",
                "completed_at": "2026-03-14T11:59:00Z",
                "error": {"code": "INDEX_FAILED", "message": "worker crashed"},
            },
            "latest_ready_snapshot": None,
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "index_status", fake_index_status)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_index/index-status",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["index_summary"]["status"] == "failed"
    assert body["index_summary"]["current_run_id"] == "idx_failed"
    assert body["index_summary"]["error_code"] == "INDEX_FAILED"
    assert body["index_summary"]["recommended_action"] == "retry"


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


def test_default_scopes_for_all_plans_are_full_access() -> None:
    expected = [
        "memory:read",
        "memory:write",
        "facts:write",
        "entities:read",
        "graph:read",
        "index:read",
        "index:run",
        "ops:read",
        "delete:write",
    ]

    assert control_plane._default_scopes_for_plan("free") == expected
    assert control_plane._default_scopes_for_plan("pro") == expected
    assert control_plane._default_scopes_for_plan("team") == expected


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


def test_project_usage_analytics_returns_payload(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_get_usage_analytics(_session, *, project_id: str, range_key: str):
        assert project_id == "proj_1"
        assert range_key == "7d"
        return {
            "range": "7d",
            "window_days": 7,
            "date_range_label": "Feb 23 – Mar 1, 2026",
            "summary": {
                "api_calls": {"value": 342, "change_pct": 18.3},
                "tokens_consumed": {"value": 1724, "change_pct": 11.9},
                "avg_response_time_ms": {"value": None, "change_pct": None},
                "error_rate_pct": {"value": 0.3, "change_pct": -0.1},
            },
            "trend": [],
            "tool_distribution": [],
            "token_breakdown": [],
            "highlights": {
                "peak_hour": "2pm – 3pm",
                "most_active_token": "vr_sk_7x9k...",
                "busiest_day": "Thursday",
            },
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_usage_analytics", fake_get_usage_analytics)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/usage/analytics?range=7d",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "7d"
    assert body["summary"]["api_calls"]["value"] == 342
    assert body["highlights"]["busiest_day"] == "Thursday"


def test_project_graph_returns_nodes_and_edges(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        return None

    async def fake_index_status(*, session, project_id: str, index_run_id: str | None = None):
        assert project_id == "proj_1"
        assert index_run_id is None
        return {"status": "MISSING"}

    async def fake_collect_project_facts(*, project_id: str, max_rows: int):
        assert project_id == "proj_1"
        assert max_rows == 5000
        return [
            {
                "id": "fact_1",
                "text": "Core parser failed in module A and ticket T-19 was filed.",
                "valid_at": "2026-03-01T10:00:00Z",
                "invalid_at": None,
                "ingested_at": "2026-03-01T10:01:00Z",
                "entities": [
                    {"id": "ent_file_a", "type": "File", "name": "src/module-a.ts"},
                    {"id": "ent_ticket", "type": "Event", "name": "T-19"},
                ],
                "provenance": {
                    "episode_ids": ["ep_1"],
                    "reference_time": "2026-03-01T10:00:00Z",
                    "ingested_at": "2026-03-01T10:01:00Z",
                },
            },
            {
                "id": "fact_2",
                "text": "Decision was made to rollback module A.",
                "valid_at": "2026-03-01T11:00:00Z",
                "invalid_at": None,
                "ingested_at": "2026-03-01T11:02:00Z",
                "entities": [
                    {"id": "ent_file_a", "type": "File", "name": "src/module-a.ts"},
                    {"id": "ent_decision", "type": "Decision", "name": "Rollback"},
                ],
                "provenance": {
                    "episode_ids": ["ep_2"],
                    "reference_time": "2026-03-01T11:00:00Z",
                    "ingested_at": "2026-03-01T11:02:00Z",
                },
            },
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(
        control_plane,
        "_ensure_graph_dependencies_ready",
        fake_ensure_graph_dependencies_ready,
    )
    monkeypatch.setattr(control_plane, "index_status", fake_index_status)
    monkeypatch.setattr(control_plane, "_collect_project_facts", fake_collect_project_facts)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/graph",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()["graph"]
    assert body["mode"] == "concepts"
    assert body["empty_reason"] == "none"
    assert body["node_primary_label"] == "Facts"
    assert body["entity_count"] == 2
    assert body["relationship_count"] == 0
    assert all(node["entity_id"] != "ent_file_a" for node in body["nodes"])
    assert body["edges"] == []


def test_project_graph_entity_detail_returns_facts_and_provenance(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        return None

    async def fake_collect_project_facts(*, project_id: str, max_rows: int):
        assert project_id == "proj_1"
        assert max_rows == 5000
        return [
            {
                "id": "fact_1",
                "text": "Parser issue in src/module-a.ts",
                "valid_at": "2026-03-01T10:00:00Z",
                "invalid_at": None,
                "ingested_at": "2026-03-01T10:01:00Z",
                "entities": [
                    {"id": "ent_file_a", "type": "File", "name": "src/module-a.ts"},
                    {"id": "ent_ticket", "type": "Event", "name": "T-19"},
                ],
                "provenance": {
                    "episode_ids": ["ep_1"],
                    "reference_time": "2026-03-01T10:00:00Z",
                    "ingested_at": "2026-03-01T10:01:00Z",
                },
            }
        ]

    async def fake_collect_timeline_episodes_for_ids(_session, **_kwargs):
        return [
            {
                "episode_id": "ep_1",
                "reference_time": "2026-03-01T10:00:00Z",
                "ingested_at": "2026-03-01T10:01:00Z",
                "summary": "Issue detected",
                "metadata": {"tags": ["incident"]},
            }
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(
        control_plane,
        "_ensure_graph_dependencies_ready",
        fake_ensure_graph_dependencies_ready,
    )
    monkeypatch.setattr(control_plane, "_collect_project_facts", fake_collect_project_facts)
    monkeypatch.setattr(
        control_plane,
        "_collect_timeline_episodes_for_ids",
        fake_collect_timeline_episodes_for_ids,
    )
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/graph/entities/ent_file_a",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "concepts"
    assert body["entity"]["entity_id"] == "ent_file_a"
    assert body["entity"]["type"] == "File"
    assert len(body["facts"]) == 1
    assert body["facts"][0]["fact_id"] == "fact_1"
    assert len(body["provenance"]) == 1
    assert body["provenance"][0]["episode_id"] == "ep_1"
    assert body["related_entities"] == []
    assert body["citations"] == []
    assert body["symbols"] == []


def test_project_graph_returns_concepts_unavailable_when_only_code_entities_remain(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        return None

    async def fake_index_status(*, session, project_id: str, index_run_id: str | None = None):
        assert project_id == "proj_1"
        assert index_run_id is None
        return {"status": "MISSING"}

    async def fake_collect_project_facts(*, project_id: str, max_rows: int):
        assert project_id == "proj_1"
        assert max_rows == 5000
        return [
            {
                "id": "fact_1",
                "text": "Parser issue in src/module-a.ts",
                "valid_at": "2026-03-01T10:00:00Z",
                "invalid_at": None,
                "ingested_at": "2026-03-01T10:01:00Z",
                "entities": [
                    {"id": "ent_file_a", "type": "File", "name": "src/module-a.ts"},
                    {"id": "symbol:src/module-a.ts:parse:10", "type": "Symbol", "name": "parse"},
                ],
                "provenance": {
                    "episode_ids": ["ep_1"],
                    "reference_time": "2026-03-01T10:00:00Z",
                    "ingested_at": "2026-03-01T10:01:00Z",
                },
            }
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "_ensure_graph_dependencies_ready", fake_ensure_graph_dependencies_ready)
    monkeypatch.setattr(control_plane, "index_status", fake_index_status)
    monkeypatch.setattr(control_plane, "_collect_project_facts", fake_collect_project_facts)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get("/api/control-plane/projects/proj_1/graph", headers=auth_headers())

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()["graph"]
    assert body["mode"] == "concepts"
    assert body["empty_reason"] == "concepts_unavailable"
    assert body["entity_count"] == 0
    assert body["relationship_count"] == 0


def test_project_graph_returns_code_topology_payload(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        return None

    async def fake_build_code_topology_graph(*, session, project_id: str, query: str | None, max_nodes: int, max_edges: int):
        assert project_id == "proj_1"
        assert query is None
        assert max_nodes == 1500
        assert max_edges == 4000
        return {
            "generated_at": "2026-03-08T10:00:00Z",
            "mode": "code",
            "empty_reason": "none",
            "available_modes": ["concepts", "code"],
            "node_primary_label": "Symbols",
            "node_secondary_label": "Files",
            "edge_support_label": "Importing files",
            "entity_count": 2,
            "relationship_count": 1,
            "truncated": False,
            "nodes": [
                {
                    "entity_id": "module:app.projects",
                    "type": "Module",
                    "name": "app.projects",
                    "fact_count": 12,
                    "episode_count": 2,
                    "reference_time": "2026-03-08T10:00:00Z",
                    "hover_text": [],
                },
                {
                    "entity_id": "module:app.timeline",
                    "type": "Module",
                    "name": "app.timeline",
                    "fact_count": 5,
                    "episode_count": 1,
                    "reference_time": "2026-03-08T10:00:00Z",
                    "hover_text": [],
                },
            ],
            "edges": [
                {
                    "edge_id": "edge:module:app.projects:module:app.timeline",
                    "type": "IMPORTS",
                    "source_entity_id": "module:app.projects",
                    "target_entity_id": "module:app.timeline",
                    "weight": 2,
                    "episode_count": 2,
                    "label": "Imported by 2 files",
                }
            ],
        }

    async def fake_index_status(*, session, project_id: str, index_run_id: str | None = None):
        _ = (session, index_run_id)
        assert project_id == "proj_1"
        return {
            "status": "READY",
            "current_run": None,
            "latest_ready_snapshot": {
                "index_run_id": "idx_ready",
                "indexed_at": "2026-03-08T10:00:00Z",
            },
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "_ensure_graph_dependencies_ready", fake_ensure_graph_dependencies_ready)
    monkeypatch.setattr(control_plane, "index_status", fake_index_status)
    monkeypatch.setattr(control_plane, "build_code_topology_graph", fake_build_code_topology_graph)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get("/api/control-plane/projects/proj_1/graph?mode=code", headers=auth_headers())

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()["graph"]
    assert body["mode"] == "code"
    assert body["node_primary_label"] == "Symbols"
    assert body["entity_count"] == 2
    assert body["edges"][0]["type"] == "IMPORTS"


def test_project_graph_code_entity_detail_returns_module_payload(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        return None

    async def fake_get_code_topology_entity_detail(*, session, project_id: str, entity_id: str):
        assert project_id == "proj_1"
        assert entity_id == "module:app.projects"
        return {
            "mode": "code",
            "entity": {
                "entity_id": "module:app.projects",
                "type": "Module",
                "name": "app.projects",
                "fact_count": 12,
                "episode_count": 2,
                "file_paths": ["src/app/projects/page.tsx"],
                "language": None,
                "kind": None,
            },
            "facts": [],
            "provenance": [],
            "related_entities": [
                {
                    "entity_id": "module:app.timeline",
                    "type": "Module",
                    "name": "app.timeline",
                    "relation_type": "IMPORTS",
                    "support_count": 2,
                }
            ],
            "citations": [
                {
                    "citation_id": "chunk:file:src/app/projects/page.tsx",
                    "source_type": "code_chunk",
                    "entity_id": "file:src/app/projects/page.tsx",
                    "file_path": "src/app/projects/page.tsx",
                    "line_start": 1,
                    "line_end": 10,
                    "snippet": "export default function Page() {}",
                }
            ],
            "symbols": [
                {
                    "entity_id": "symbol:src/app/projects/page.tsx:Page:1",
                    "name": "Page",
                    "kind": "function",
                    "file_path": "src/app/projects/page.tsx",
                    "line_start": 1,
                    "line_end": 10,
                    "language": "typescript",
                }
            ],
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "_ensure_graph_dependencies_ready", fake_ensure_graph_dependencies_ready)
    monkeypatch.setattr(control_plane, "get_code_topology_entity_detail", fake_get_code_topology_entity_detail)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/graph/entities/module%3Aapp.projects?mode=code",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "code"
    assert body["entity"]["entity_id"] == "module:app.projects"
    assert body["related_entities"][0]["relation_type"] == "IMPORTS"
    assert body["symbols"][0]["name"] == "Page"


def test_project_graph_returns_503_when_dependencies_unavailable(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        raise HTTPException(
            status_code=503,
            detail="Graph dependency check failed for memory backend 'graphiti': Connection refused",
        )

    calls = {"collect": 0}

    async def fake_collect_project_facts_for_graph(*, project_id: str, max_rows: int):
        calls["collect"] += 1
        return []

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(
        control_plane,
        "_ensure_graph_dependencies_ready",
        fake_ensure_graph_dependencies_ready,
    )
    monkeypatch.setattr(
        control_plane,
        "_collect_project_facts_for_graph",
        fake_collect_project_facts_for_graph,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/graph",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "Graph dependency check failed" in response.json()["detail"]
    assert calls["collect"] == 0


def test_project_graph_returns_503_when_fact_collection_detects_dependency_failure(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        return None

    async def fake_collect_project_facts_for_graph(*, project_id: str, max_rows: int):
        raise HTTPException(
            status_code=503,
            detail="Graph dependency check failed for memory backend 'graphiti': Error 111 connecting to localhost:6380. Connection refused.",
        )

    async def fake_index_status(*, session, project_id: str, index_run_id: str | None = None):
        _ = (session, project_id, index_run_id)
        return {"status": "EMPTY", "current_run": None, "latest_ready_snapshot": None}

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(
        control_plane,
        "_ensure_graph_dependencies_ready",
        fake_ensure_graph_dependencies_ready,
    )
    monkeypatch.setattr(control_plane, "index_status", fake_index_status)
    monkeypatch.setattr(
        control_plane,
        "_collect_project_facts_for_graph",
        fake_collect_project_facts_for_graph,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/graph",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "localhost:6380" in response.json()["detail"]


def test_project_graph_entity_detail_returns_404_for_unknown_entity(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        return None

    async def fake_collect_project_facts_for_graph(*, project_id: str, max_rows: int):
        return [
            {
                "id": "fact_1",
                "text": "Parser issue in src/module-a.ts",
                "valid_at": "2026-03-01T10:00:00Z",
                "invalid_at": None,
                "ingested_at": "2026-03-01T10:01:00Z",
                "entities": [
                    {"id": "ent_file_a", "type": "File", "name": "src/module-a.ts"},
                ],
                "provenance": {
                    "episode_ids": ["ep_1"],
                    "reference_time": "2026-03-01T10:00:00Z",
                    "ingested_at": "2026-03-01T10:01:00Z",
                },
            }
        ]

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(
        control_plane,
        "_ensure_graph_dependencies_ready",
        fake_ensure_graph_dependencies_ready,
    )
    monkeypatch.setattr(
        control_plane,
        "_collect_project_facts_for_graph",
        fake_collect_project_facts_for_graph,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/graph/entities/ent_missing",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json()["detail"] == "Entity not found"


def test_project_graph_entity_detail_validates_limits_before_dependency_check(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_graph_dependencies_ready() -> None:
        raise AssertionError("dependency check should not run for invalid input")

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(
        control_plane,
        "_ensure_graph_dependencies_ready",
        fake_ensure_graph_dependencies_ready,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/graph/entities/ent_file_a?fact_limit=0",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"] == "fact_limit must be between 1 and 500"


def test_project_timeline_returns_paginated_rows(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_list_timeline_episodes(
        _session,
        *,
        project_id: str,
        from_time: str | None,
        to_time: str | None,
        limit: int,
        offset: int,
    ):
        assert project_id == "proj_1"
        assert from_time is None
        assert to_time is None
        assert limit == 3
        assert offset == 0
        return [
            {
                "episode_id": "ep_3",
                "reference_time": "2026-03-03T10:00:00Z",
                "ingested_at": "2026-03-03T10:00:01Z",
                "summary": "third",
                "metadata": {},
            },
            {
                "episode_id": "ep_2",
                "reference_time": "2026-03-02T10:00:00Z",
                "ingested_at": "2026-03-02T10:00:01Z",
                "summary": "second",
                "metadata": {},
            },
            {
                "episode_id": "ep_1",
                "reference_time": "2026-03-01T10:00:00Z",
                "ingested_at": "2026-03-01T10:00:01Z",
                "summary": "first",
                "metadata": {},
            },
        ]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "list_timeline_episodes", fake_list_timeline_episodes)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/timeline?limit=2&offset=0",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()["timeline"]
    assert len(body["rows"]) == 2
    assert body["rows"][0]["episode_id"] == "ep_3"
    assert body["has_more"] is True
    assert body["next_offset"] == 2


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

    async def fake_list_recent_invoices(_session, **_kwargs):
        return []

    async def fake_get_default_payment_method(_session, **_kwargs):
        return None

    async def fake_get_billing_contact(_session, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_billing_usage_snapshot", fake_get_billing_usage_snapshot)
    monkeypatch.setattr(control_plane, "list_recent_invoices", fake_list_recent_invoices)
    monkeypatch.setattr(control_plane, "get_default_payment_method", fake_get_default_payment_method)
    monkeypatch.setattr(control_plane, "get_billing_contact", fake_get_billing_contact)
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
    assert body["plan_monthly_price_cents"] == 4900
    assert isinstance(body["renews_at"], str)
    assert body["invoices"] == []
    assert body["payment_method"] is None
    assert body["billing_contact"] == {
        "email": None,
        "tax_id": None,
    }


def test_project_billing_overview_returns_billing_entities(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "team", "owner_id": "user_123"}

    async def fake_get_billing_usage_snapshot(_session, *, project_id: str):
        assert project_id == "proj_1"
        return {
            "current_month_vibe_tokens": 9800,
            "current_month_events": 112,
            "last_7d_vibe_tokens": 3150,
        }

    async def fake_list_recent_invoices(_session, **_kwargs):
        return [
            {
                "invoice_id": "inv_2026_03",
                "invoice_date": "2026-03-01T00:00:00Z",
                "description": "Team Plan — Monthly",
                "amount_cents": 19900,
                "currency": "usd",
                "status": "paid",
                "pdf_url": "https://example.com/inv_2026_03.pdf",
            }
        ]

    async def fake_get_default_payment_method(_session, **_kwargs):
        return {
            "payment_method_id": "pm_1",
            "brand": "visa",
            "last4": "4242",
            "exp_month": 12,
            "exp_year": 2027,
            "is_default": True,
        }

    async def fake_get_billing_contact(_session, **_kwargs):
        return {
            "project_id": "proj_1",
            "email": "billing@example.com",
            "tax_id": "US-123456",
        }

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_billing_usage_snapshot", fake_get_billing_usage_snapshot)
    monkeypatch.setattr(control_plane, "list_recent_invoices", fake_list_recent_invoices)
    monkeypatch.setattr(control_plane, "get_default_payment_method", fake_get_default_payment_method)
    monkeypatch.setattr(control_plane, "get_billing_contact", fake_get_billing_contact)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/billing/overview",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "team"
    assert body["plan_monthly_price_cents"] == 19_900
    assert body["invoices"][0]["invoice_id"] == "inv_2026_03"
    assert body["invoices"][0]["status"] == "paid"
    assert body["payment_method"]["last4"] == "4242"
    assert body["payment_method"]["is_default"] is True
    assert body["billing_contact"]["email"] == "billing@example.com"
    assert body["billing_contact"]["tax_id"] == "US-123456"


def test_project_api_logs_returns_paginated_rows(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_list_audit_logs_for_project(
        _session,
        *,
        project_id: str,
        limit: int,
        cursor: int | None = None,
        action_name: str | None = None,
    ):
        assert project_id == "proj_1"
        assert limit == 3
        assert cursor is None
        assert action_name == "tools/call"
        return [
            {
                "id": 200,
                "request_id": "req_200",
                "project_id": "proj_1",
                "token_id": "tok_1",
                "tool_name": "viberecall_save",
                "action": "tools/call",
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
                "action": "tools/call",
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
                "action": "tools/call",
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


def test_project_api_logs_analytics_returns_summary_and_table(monkeypatch) -> None:
    summary_calls = {"count": 0}

    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_get_api_logs_summary(_session, **_kwargs):
        assert _kwargs["action_name"] == "tools/call"
        summary_calls["count"] += 1
        if summary_calls["count"] == 1:
            return {
                "total_requests": 120,
                "success_rate_pct": 99.7,
                "error_count": 4,
                "p95_latency_ms": 287.3,
            }
        return {
            "total_requests": 100,
            "success_rate_pct": 98.0,
            "error_count": 5,
            "p95_latency_ms": 310.0,
        }

    async def fake_count_api_logs_rows(_session, **_kwargs):
        assert _kwargs["action_name"] == "tools/call"
        return 5

    async def fake_list_api_logs_rows(_session, **_kwargs):
        assert _kwargs["action_name"] == "tools/call"
        return [
            {
                "id": 999,
                "created_at": "2026-03-02T12:00:00Z",
                "tool_name": "viberecall_save",
                "status": "ok",
                "latency_ms": 221.2,
                "token_id": "tok_abc",
                "token_prefix": "vr_mcp_sk_abc123",
                "request_id": "req_1",
                "action": "tools/call",
            },
            {
                "id": 998,
                "created_at": "2026-03-02T11:59:00Z",
                "tool_name": "viberecall_search",
                "status": "error",
                "latency_ms": 450.0,
                "token_id": "tok_xyz",
                "token_prefix": "vr_mcp_sk_xyz789",
                "request_id": "req_2",
                "action": "tools/call",
            },
        ]

    async def fake_list_api_logs_tools(_session, **_kwargs):
        assert _kwargs["action_name"] == "tools/call"
        return ["viberecall_save", "viberecall_search"]

    async def fake_audit(*_args, **_kwargs):
        return None

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "get_api_logs_summary", fake_get_api_logs_summary)
    monkeypatch.setattr(control_plane, "count_api_logs_rows", fake_count_api_logs_rows)
    monkeypatch.setattr(control_plane, "list_api_logs_rows", fake_list_api_logs_rows)
    monkeypatch.setattr(control_plane, "list_api_logs_tools", fake_list_api_logs_tools)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/api-logs/analytics?range=30d&limit=2",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "30d"
    assert body["summary"]["total_requests"]["value"] == 120
    assert body["summary"]["success_rate_pct"]["value"] == 99.7
    assert body["summary"]["error_count"]["value"] == 4
    assert body["summary"]["p95_latency_ms"]["value"] == 287.3
    assert body["table"]["pagination"]["showing_from"] == 1
    assert body["table"]["pagination"]["showing_to"] == 2
    assert body["table"]["pagination"]["total_rows"] == 5
    assert body["table"]["pagination"]["prev_cursor"] is None
    assert body["table"]["pagination"]["next_cursor"] is not None
    assert body["table"]["rows"][0]["token_prefix"] == "vr_mcp_sk_abc123"
    assert body["table"]["tool_options"] == ["viberecall_save", "viberecall_search"]


def test_project_api_logs_analytics_rejects_invalid_cursor(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)

    with TestClient(app) as client:
        response = client.get(
            "/api/control-plane/projects/proj_1/api-logs/analytics?cursor=not-a-valid-cursor",
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid cursor:")


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
    captured: dict[str, object] = {}

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

    async def fake_ensure_export_dependencies_ready() -> None:
        return None

    class FakeQueue:
        async def enqueue_export(self, **_kwargs):
            captured.update(_kwargs)
            return "job_export_1"

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "create_export", fake_create_export)
    monkeypatch.setattr(control_plane, "set_export_job_id", fake_set_export_job_id)
    monkeypatch.setattr(control_plane, "get_export", fake_get_export)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)
    monkeypatch.setattr(
        control_plane,
        "_ensure_export_dependencies_ready",
        fake_ensure_export_dependencies_ready,
    )
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
    assert captured["token_id"] is None


def test_create_export_returns_503_when_dependencies_unavailable(monkeypatch) -> None:
    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_ensure_export_dependencies_ready() -> None:
        raise HTTPException(
            status_code=503,
            detail="Export dependency check failed for memory backend 'falkordb': Connection refused",
        )

    calls = {"create_export": 0, "enqueue_export": 0}

    async def fake_create_export(_session, **_kwargs):
        calls["create_export"] += 1
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

    class FakeQueue:
        async def enqueue_export(self, **_kwargs):
            calls["enqueue_export"] += 1
            return "job_export_1"

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(
        control_plane,
        "_ensure_export_dependencies_ready",
        fake_ensure_export_dependencies_ready,
    )
    monkeypatch.setattr(control_plane, "create_export", fake_create_export)
    monkeypatch.setattr(control_plane, "get_task_queue", lambda: FakeQueue())

    with TestClient(app) as client:
        response = client.post(
            "/api/control-plane/projects/proj_1/exports",
            headers=auth_headers() | {"Idempotency-Key": "idem-export-2"},
            json={"format": "json_v1"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "Export dependency check failed" in response.json()["detail"]
    assert calls["create_export"] == 0
    assert calls["enqueue_export"] == 0


def test_create_export_rolls_back_when_enqueue_fails(monkeypatch) -> None:
    events: list[str] = []

    class TrackingSession:
        async def commit(self) -> None:
            events.append("commit")

        async def rollback(self) -> None:
            events.append("rollback")

    async def override_tracking_session() -> AsyncIterator[TrackingSession]:
        yield TrackingSession()

    async def fake_ensure_project_access(_session, **_kwargs):
        return {"id": "proj_1", "plan": "pro", "owner_id": "user_123"}

    async def fake_create_export(_session, **_kwargs):
        events.append("create_export")
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
        events.append("set_job_id")

    async def fake_audit(*_args, **_kwargs):
        events.append("audit")

    async def fake_ensure_export_dependencies_ready() -> None:
        return None

    class FailingQueue:
        async def enqueue_export(self, **_kwargs):
            events.append("enqueue_export")
            raise RuntimeError("queue unavailable")

    app = create_app()
    app.dependency_overrides[get_db_session] = override_tracking_session
    app.dependency_overrides[control_plane.authenticate_control_plane_request] = override_user
    monkeypatch.setattr(control_plane, "_ensure_project_access", fake_ensure_project_access)
    monkeypatch.setattr(control_plane, "create_export", fake_create_export)
    monkeypatch.setattr(control_plane, "set_export_job_id", fake_set_export_job_id)
    monkeypatch.setattr(control_plane, "_audit_control_plane", fake_audit)
    monkeypatch.setattr(
        control_plane,
        "_ensure_export_dependencies_ready",
        fake_ensure_export_dependencies_ready,
    )
    monkeypatch.setattr(control_plane, "get_task_queue", lambda: FailingQueue())

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/control-plane/projects/proj_1/exports",
            headers=auth_headers() | {"Idempotency-Key": "idem-export-fail"},
            json={"format": "json_v1"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 500
    assert events == ["create_export", "enqueue_export", "rollback"]


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
