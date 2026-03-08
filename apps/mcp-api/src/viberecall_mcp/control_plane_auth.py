from __future__ import annotations

import structlog
from fastapi import Header, HTTPException, Request, status

from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane_assertion import (
    ControlPlaneAssertionClaims as AuthenticatedControlPlaneUser,
    verify_control_plane_assertion,
)


settings = get_settings()
logger = structlog.get_logger(__name__)


def _request_id_from_state(request: Request) -> str | None:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) and request_id else None


def _classify_assertion_error(message: str) -> str:
    if message in {"Malformed assertion", "Unsupported assertion version", "Assertion payload must be an object"}:
        return "malformed"
    if message == "Invalid assertion signature":
        return "bad_signature"
    if message == "Assertion expired":
        return "expired"
    if message == "Assertion issuer mismatch":
        return "issuer_mismatch"
    if message == "Assertion audience mismatch":
        return "audience_mismatch"
    if message == "Assertion issued-at is in the future":
        return "issued_at_in_future"
    return "invalid"


async def authenticate_control_plane_request(
    request: Request,
    control_plane_assertion: str | None = Header(default=None, alias="X-Control-Plane-Assertion"),
) -> AuthenticatedControlPlaneUser:
    request_id = _request_id_from_state(request)
    logger.info(
        "control_plane_auth_check",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        assertion_present=bool(control_plane_assertion),
    )

    if not control_plane_assertion:
        logger.warning(
            "control_plane_auth_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            assertion_present=False,
            reason="missing",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing control-plane assertion",
        )

    try:
        claims = verify_control_plane_assertion(
            assertion=control_plane_assertion,
            secret=settings.control_plane_internal_secret,
        )
        logger.info(
            "control_plane_auth_succeeded",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            assertion_present=True,
            user_id=claims.user_id,
        )
        return claims
    except ValueError as error:
        logger.warning(
            "control_plane_auth_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            assertion_present=True,
            reason=_classify_assertion_error(str(error)),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
