from __future__ import annotations

import hashlib
import hmac
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from viberecall_mcp.config import get_settings


settings = get_settings()


def export_storage_key(project_id: str, export_id: str) -> str:
    return f"projects/{project_id}/exports/{export_id}.json"


def local_export_path(object_key: str) -> Path:
    return Path(settings.export_local_dir) / object_key


def _local_storage_root() -> Path:
    return Path(settings.export_local_dir).resolve()


def _resolve_local_key_path(object_key: str) -> Path | None:
    root = _local_storage_root()
    candidate = (root / object_key.lstrip("/")).resolve()
    if candidate == root or root in candidate.parents:
        return candidate
    return None


def _prune_empty_parents(path: Path, root: Path) -> None:
    current = path
    while current != root and root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def write_local_export(*, object_key: str, payload: dict) -> None:
    if settings.export_storage_mode != "local":
        raise RuntimeError(f"Unsupported export storage mode: {settings.export_storage_mode}")

    path = local_export_path(object_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )


def delete_local_object(*, object_key: str) -> bool:
    if settings.export_storage_mode != "local":
        raise RuntimeError(f"Unsupported export storage mode: {settings.export_storage_mode}")

    path = _resolve_local_key_path(object_key)
    if path is None or not path.exists():
        return False

    root = _local_storage_root()
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
        _prune_empty_parents(path.parent, root)
    return True


def delete_local_prefix(prefix: str) -> int:
    if settings.export_storage_mode != "local":
        raise RuntimeError(f"Unsupported export storage mode: {settings.export_storage_mode}")

    path = _resolve_local_key_path(prefix)
    if path is None or not path.exists():
        return 0

    root = _local_storage_root()
    if path.is_file():
        path.unlink(missing_ok=True)
        _prune_empty_parents(path.parent, root)
        return 1

    deleted_files = sum(1 for candidate in path.rglob("*") if candidate.is_file())
    shutil.rmtree(path)
    _prune_empty_parents(path.parent, root)
    return deleted_files


def build_signed_download(
    *,
    project_id: str,
    export_id: str,
    ttl_seconds: int | None = None,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds or settings.export_url_ttl_seconds)
    expires_ts = int(expires_at.timestamp())
    message = f"{project_id}:{export_id}:{expires_ts}"
    signature = hmac.new(
        settings.export_signing_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    query = urlencode({"expires": expires_ts, "sig": signature})
    base = settings.public_mcp_base_url.rstrip("/")
    url = f"{base}/api/control-plane/projects/{project_id}/exports/{export_id}/download?{query}"
    return url, expires_at


def verify_download_signature(
    *,
    project_id: str,
    export_id: str,
    expires: int,
    signature: str,
) -> bool:
    if expires <= int(datetime.now(timezone.utc).timestamp()):
        return False
    message = f"{project_id}:{export_id}:{expires}"
    expected = hmac.new(
        settings.export_signing_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
