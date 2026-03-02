from __future__ import annotations

import base64
import hashlib
import json


def make_seed(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def encode_cursor(offset: int, seed: str) -> str:
    raw = json.dumps({"offset": offset, "seed": seed}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def decode_cursor(cursor: str | None, expected_seed: str) -> int:
    if cursor is None:
        return 0
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Malformed cursor") from exc

    if payload.get("seed") != expected_seed:
        raise ValueError("Cursor seed mismatch")

    offset = payload.get("offset")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("Cursor offset invalid")
    return offset
