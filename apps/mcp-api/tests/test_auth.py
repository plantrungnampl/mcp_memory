from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from viberecall_mcp import auth


class DummySession:
    pass


@pytest.mark.asyncio
async def test_auth_accepts_token_in_grace_window(monkeypatch) -> None:
    async def fake_get_token_by_hash(_session, _token_hash: str):
        return {
            "token_id": "tok_1",
            "project_id": "proj_1",
            "scopes": ["memory:read"],
            "plan": "free",
            "revoked_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            "expires_at": None,
        }

    monkeypatch.setattr(auth, "get_token_by_hash", fake_get_token_by_hash)

    token = await auth.authenticate_bearer_token(
        DummySession(),
        authorization="Bearer token_abc",
        project_id="proj_1",
    )
    assert token.token_id == "tok_1"


@pytest.mark.asyncio
async def test_auth_rejects_revoked_token_in_past(monkeypatch) -> None:
    async def fake_get_token_by_hash(_session, _token_hash: str):
        return {
            "token_id": "tok_1",
            "project_id": "proj_1",
            "scopes": ["memory:read"],
            "plan": "free",
            "revoked_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "expires_at": None,
        }

    monkeypatch.setattr(auth, "get_token_by_hash", fake_get_token_by_hash)

    with pytest.raises(HTTPException) as exc:
        await auth.authenticate_bearer_token(
            DummySession(),
            authorization="Bearer token_abc",
            project_id="proj_1",
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token revoked"
