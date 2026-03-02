from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from viberecall_mcp.config import get_settings


settings = get_settings()


class ObjectStorageError(RuntimeError):
    pass


def episode_storage_key(project_id: str, episode_id: str) -> str:
    return f"projects/{project_id}/episodes/{episode_id}.txt"


def _local_storage_root() -> Path:
    return Path(settings.object_local_dir).resolve()


def _resolve_local_key_path(object_key: str) -> Path:
    root = _local_storage_root()
    candidate = (root / object_key.lstrip("/")).resolve()
    if candidate == root or root in candidate.parents:
        return candidate
    raise ObjectStorageError("Invalid object key path")


def _prune_empty_parents(path: Path, root: Path) -> None:
    current = path
    while current != root and root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _require_bucket() -> str:
    bucket = settings.object_bucket.strip()
    if not bucket:
        raise ObjectStorageError("OBJECT_BUCKET is required for object_storage_mode=r2")
    return bucket


@lru_cache
def _r2_client():
    options: dict = {}
    if settings.object_endpoint.strip():
        options["endpoint_url"] = settings.object_endpoint.strip()
    if settings.object_region.strip():
        options["region_name"] = settings.object_region.strip()
    if settings.object_access_key_id.strip():
        options["aws_access_key_id"] = settings.object_access_key_id.strip()
    if settings.object_secret_access_key.strip():
        options["aws_secret_access_key"] = settings.object_secret_access_key.strip()
    if settings.object_force_path_style:
        options["config"] = BotoConfig(s3={"addressing_style": "path"})
    return boto3.client("s3", **options)


async def put_text(*, object_key: str, content: str) -> None:
    if settings.object_storage_mode == "local":
        path = _resolve_local_key_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return
    if settings.object_storage_mode != "r2":
        raise ObjectStorageError(f"Unsupported object storage mode: {settings.object_storage_mode}")

    body = content.encode("utf-8")
    bucket = _require_bucket()
    try:
        await asyncio.to_thread(
            _r2_client().put_object,
            Bucket=bucket,
            Key=object_key,
            Body=body,
            ContentType="text/plain; charset=utf-8",
        )
    except (ClientError, BotoCoreError) as exc:
        raise ObjectStorageError(f"Failed to write object: {object_key}") from exc


async def get_text(*, object_key: str) -> str:
    if settings.object_storage_mode == "local":
        path = _resolve_local_key_path(object_key)
        if not path.exists():
            raise FileNotFoundError(object_key)
        return path.read_text(encoding="utf-8")
    if settings.object_storage_mode != "r2":
        raise ObjectStorageError(f"Unsupported object storage mode: {settings.object_storage_mode}")

    bucket = _require_bucket()
    try:
        response = await asyncio.to_thread(
            _r2_client().get_object,
            Bucket=bucket,
            Key=object_key,
        )
        payload = await asyncio.to_thread(response["Body"].read)
        return payload.decode("utf-8")
    except ClientError as exc:
        code = (exc.response.get("Error") or {}).get("Code")
        if code in {"NoSuchKey", "404"}:
            raise FileNotFoundError(object_key) from exc
        raise ObjectStorageError(f"Failed to read object: {object_key}") from exc
    except (BotoCoreError, UnicodeDecodeError) as exc:
        raise ObjectStorageError(f"Failed to decode object: {object_key}") from exc


async def delete_object(*, object_key: str) -> bool:
    if settings.object_storage_mode == "local":
        path = _resolve_local_key_path(object_key)
        if not path.exists():
            return False
        root = _local_storage_root()
        if path.is_dir():
            return False
        path.unlink(missing_ok=True)
        _prune_empty_parents(path.parent, root)
        return True
    if settings.object_storage_mode != "r2":
        raise ObjectStorageError(f"Unsupported object storage mode: {settings.object_storage_mode}")

    bucket = _require_bucket()
    try:
        await asyncio.to_thread(_r2_client().head_object, Bucket=bucket, Key=object_key)
    except ClientError as exc:
        code = (exc.response.get("Error") or {}).get("Code")
        if code in {"404", "NotFound", "NoSuchKey"}:
            return False
        raise ObjectStorageError(f"Failed to stat object: {object_key}") from exc
    except BotoCoreError as exc:
        raise ObjectStorageError(f"Failed to stat object: {object_key}") from exc

    try:
        await asyncio.to_thread(_r2_client().delete_object, Bucket=bucket, Key=object_key)
    except (ClientError, BotoCoreError) as exc:
        raise ObjectStorageError(f"Failed to delete object: {object_key}") from exc
    return True


async def delete_prefix(prefix: str) -> int:
    if settings.object_storage_mode == "local":
        path = _resolve_local_key_path(prefix)
        if not path.exists():
            return 0
        root = _local_storage_root()
        if path.is_file():
            path.unlink(missing_ok=True)
            _prune_empty_parents(path.parent, root)
            return 1
        files = [item for item in path.rglob("*") if item.is_file()]
        for file_path in files:
            file_path.unlink(missing_ok=True)
        for directory in sorted([item for item in path.rglob("*") if item.is_dir()], reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            path.rmdir()
        except OSError:
            pass
        _prune_empty_parents(path.parent, root)
        return len(files)
    if settings.object_storage_mode != "r2":
        raise ObjectStorageError(f"Unsupported object storage mode: {settings.object_storage_mode}")

    bucket = _require_bucket()
    token: str | None = None
    deleted_count = 0
    while True:
        try:
            list_kwargs = {"Bucket": bucket, "Prefix": prefix}
            if token:
                list_kwargs["ContinuationToken"] = token
            response = await asyncio.to_thread(_r2_client().list_objects_v2, **list_kwargs)
        except (ClientError, BotoCoreError) as exc:
            raise ObjectStorageError(f"Failed to list objects for prefix: {prefix}") from exc

        contents = response.get("Contents") or []
        keys = [entry["Key"] for entry in contents if entry.get("Key")]
        if keys:
            for start in range(0, len(keys), 1000):
                chunk = keys[start : start + 1000]
                try:
                    await asyncio.to_thread(
                        _r2_client().delete_objects,
                        Bucket=bucket,
                        Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
                    )
                except (ClientError, BotoCoreError) as exc:
                    raise ObjectStorageError(f"Failed to delete objects for prefix: {prefix}") from exc
                deleted_count += len(chunk)

        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")
        if not token:
            break
    return deleted_count
