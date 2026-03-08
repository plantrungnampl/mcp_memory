from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from viberecall_mcp.control_plane_assertion import create_control_plane_assertion, verify_control_plane_assertion
from viberecall_mcp.control_plane_auth import _classify_assertion_error


TEST_SECRET = "test-control-plane-secret"


def test_verify_control_plane_assertion_accepts_valid_token() -> None:
    claims = verify_control_plane_assertion(
        assertion=create_control_plane_assertion(
            secret=TEST_SECRET,
            user_id="user_123",
            user_email="dev@example.com",
        ),
        secret=TEST_SECRET,
    )

    assert claims.user_id == "user_123"
    assert claims.user_email == "dev@example.com"


def test_verify_control_plane_assertion_rejects_expired_token() -> None:
    issued_at = datetime.now(timezone.utc) - timedelta(minutes=3)
    expires_at = issued_at + timedelta(seconds=30)
    assertion = create_control_plane_assertion(
        secret=TEST_SECRET,
        user_id="user_123",
        user_email="dev@example.com",
        issued_at=issued_at,
        expires_at=expires_at,
    )

    with pytest.raises(ValueError, match="Assertion expired"):
        verify_control_plane_assertion(assertion=assertion, secret=TEST_SECRET)


def test_verify_control_plane_assertion_rejects_invalid_signature() -> None:
    assertion = create_control_plane_assertion(
        secret=TEST_SECRET,
        user_id="user_123",
        user_email="dev@example.com",
    )

    with pytest.raises(ValueError, match="Invalid assertion signature"):
        verify_control_plane_assertion(assertion=assertion, secret="wrong-secret")


def test_verify_control_plane_assertion_rejects_wrong_audience() -> None:
    assertion = create_control_plane_assertion(
        secret=TEST_SECRET,
        user_id="user_123",
        user_email="dev@example.com",
        audience="not-control-plane",
    )

    with pytest.raises(ValueError, match="Assertion audience mismatch"):
        verify_control_plane_assertion(assertion=assertion, secret=TEST_SECRET)


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("Malformed assertion", "malformed"),
        ("Unsupported assertion version", "malformed"),
        ("Invalid assertion signature", "bad_signature"),
        ("Assertion expired", "expired"),
        ("Assertion issuer mismatch", "issuer_mismatch"),
        ("Assertion audience mismatch", "audience_mismatch"),
        ("Assertion issued-at is in the future", "issued_at_in_future"),
        ("Assertion subject is required", "invalid"),
    ],
)
def test_classify_assertion_error(message: str, reason: str) -> None:
    assert _classify_assertion_error(message) == reason
