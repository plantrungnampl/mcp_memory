from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from viberecall_mcp.config import get_settings


settings = get_settings()


@dataclass(slots=True)
class AuthenticatedControlPlaneUser:
    user_id: str
    user_email: str | None = None


async def authenticate_control_plane_request(
    control_plane_secret: str | None = Header(default=None, alias="X-Control-Plane-Secret"),
    user_id: str | None = Header(default=None, alias="X-Control-Plane-User-Id"),
    user_email: str | None = Header(default=None, alias="X-Control-Plane-User-Email"),
) -> AuthenticatedControlPlaneUser:
    if not control_plane_secret or not hmac.compare_digest(
        control_plane_secret,
        settings.control_plane_internal_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid control-plane credentials",
        )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing control-plane user id",
        )

    return AuthenticatedControlPlaneUser(
        user_id=user_id,
        user_email=user_email,
    )
