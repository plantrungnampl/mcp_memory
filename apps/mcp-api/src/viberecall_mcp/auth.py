from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.config import get_settings
from viberecall_mcp.graph_routing import project_graph_name
from viberecall_mcp.repositories.tokens import get_token_by_hash


settings = get_settings()


@dataclass(slots=True)
class AuthenticatedToken:
    token_id: str
    project_id: str
    scopes: list[str]
    plan: str
    db_name: str


def hash_token(plaintext_token: str) -> str:
    return hmac.new(
        settings.token_pepper.encode("utf-8"),
        plaintext_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def authenticate_bearer_token(
    session: AsyncSession,
    *,
    authorization: str | None,
    project_id: str,
) -> AuthenticatedToken:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token",
        )

    plaintext_token = authorization.removeprefix("Bearer ").strip()
    token = await get_token_by_hash(session, hash_token(plaintext_token))
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not found",
        )

    revoked_at = token["revoked_at"]
    now = datetime.now(timezone.utc)
    if revoked_at is not None and revoked_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
        )

    expires_at = token["expires_at"]
    if expires_at is not None and expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    if token["project_id"] != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token project mismatch",
        )

    return AuthenticatedToken(
        token_id=token["token_id"],
        project_id=token["project_id"],
        scopes=list(token["scopes"] or []),
        plan=token["plan"],
        db_name=project_graph_name(project_id),
    )
