from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone


ASSERTION_AUDIENCE = "viberecall-control-plane"
ASSERTION_ISSUER = "viberecall-web"
ASSERTION_VERSION = "v1"
MAX_CLOCK_SKEW_SECONDS = 5


@dataclass(slots=True)
class ControlPlaneAssertionClaims:
    user_id: str
    user_email: str | None


def _encode_json(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_json(value: str) -> dict[str, object]:
    padding = "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Assertion payload must be an object")
    return decoded


def _sign_assertion(secret: str, message: str) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    ).rstrip(b"=").decode("ascii")


def create_control_plane_assertion(
    *,
    secret: str,
    user_id: str,
    user_email: str | None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    audience: str = ASSERTION_AUDIENCE,
    issuer: str = ASSERTION_ISSUER,
) -> str:
    now = issued_at or datetime.now(timezone.utc)
    expiry = expires_at or now.replace(microsecond=0)
    if expires_at is None:
        expiry = now.replace(microsecond=0).astimezone(timezone.utc)
        expiry = datetime.fromtimestamp(expiry.timestamp() + 60, tz=timezone.utc)

    payload = {
        "aud": audience,
        "email": user_email,
        "exp": int(expiry.timestamp()),
        "iat": int(now.astimezone(timezone.utc).timestamp()),
        "iss": issuer,
        "sub": user_id,
    }
    payload_segment = _encode_json(payload)
    unsigned = f"{ASSERTION_VERSION}.{payload_segment}"
    signature = _sign_assertion(secret, unsigned)
    return f"{unsigned}.{signature}"


def verify_control_plane_assertion(*, assertion: str, secret: str) -> ControlPlaneAssertionClaims:
    parts = assertion.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed assertion")

    version, payload_segment, provided_signature = parts
    if version != ASSERTION_VERSION:
        raise ValueError("Unsupported assertion version")

    expected_signature = _sign_assertion(secret, f"{version}.{payload_segment}")
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid assertion signature")

    payload = _decode_json(payload_segment)
    subject = payload.get("sub")
    audience = payload.get("aud")
    issuer = payload.get("iss")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")

    if not isinstance(subject, str) or not subject:
        raise ValueError("Assertion subject is required")
    if audience != ASSERTION_AUDIENCE:
        raise ValueError("Assertion audience mismatch")
    if issuer != ASSERTION_ISSUER:
        raise ValueError("Assertion issuer mismatch")
    if not isinstance(issued_at, int) or not isinstance(expires_at, int):
        raise ValueError("Assertion timestamps are invalid")

    now = int(datetime.now(timezone.utc).timestamp())
    if issued_at > now + MAX_CLOCK_SKEW_SECONDS:
        raise ValueError("Assertion issued-at is in the future")
    if expires_at <= now - MAX_CLOCK_SKEW_SECONDS:
        raise ValueError("Assertion expired")

    email = payload.get("email")
    if email is not None and not isinstance(email, str):
        raise ValueError("Assertion email is invalid")

    return ControlPlaneAssertionClaims(user_id=subject, user_email=email)
