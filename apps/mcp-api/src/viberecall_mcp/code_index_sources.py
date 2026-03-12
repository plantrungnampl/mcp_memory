from __future__ import annotations

import io
import json
import subprocess
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.code_index_shared import settings
from viberecall_mcp.object_storage import get_bytes
from viberecall_mcp.repositories.index_bundles import get_index_bundle


_INTERNAL_FULL_SNAPSHOT_MODE = "snapshot"


def _normalize_full_snapshot_mode(mode: str | None) -> str:
    value = (mode or "FULL_SNAPSHOT").strip().upper()
    if value != "FULL_SNAPSHOT":
        raise ValueError("mode must be 'FULL_SNAPSHOT'")
    return value


def _normalize_bundle_ref(bundle_ref: str) -> str:
    value = bundle_ref.strip()
    if not value.startswith("bundle://"):
        raise ValueError("workspace_bundle.bundle_ref must start with 'bundle://'")
    bundle_id = value.removeprefix("bundle://").strip()
    if not bundle_id:
        raise ValueError("workspace_bundle.bundle_ref is missing bundle id")
    return f"bundle://{bundle_id}"


def normalize_repo_source(repo_source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(repo_source, dict):
        raise ValueError("repo_source must be an object")

    source_type = str(repo_source.get("type") or "").strip()
    if source_type == "git":
        if not settings.index_remote_git_enabled:
            raise ValueError("remote git indexing is disabled; use repo_source.type='workspace_bundle'")
        remote_url = str(repo_source.get("remote_url") or "").strip()
        ref = str(repo_source.get("ref") or "").strip()
        credential_ref = str(repo_source.get("credential_ref") or "").strip() or None
        if not remote_url:
            raise ValueError("git.repo_source.remote_url is required")
        if not ref:
            raise ValueError("git.repo_source.ref is required")
        split = urlsplit(remote_url)
        if split.scheme.lower() != "https":
            raise ValueError("git.repo_source.remote_url must use https")
        if not split.netloc:
            raise ValueError("git.repo_source.remote_url must include a host")
        if split.username or split.password:
            raise ValueError("git.repo_source.remote_url must not embed credentials")
        if credential_ref is not None:
            credentials = settings.resolved_index_git_credential_refs()
            credential = credentials.get(credential_ref)
            if credential is None:
                raise ValueError(f"Unknown git credential_ref: {credential_ref}")
            host = (split.hostname or "").lower()
            if host not in set(credential.get("allowed_hosts") or []):
                raise ValueError(f"credential_ref '{credential_ref}' is not allowed for host '{host}'")
        repo_name = str(repo_source.get("repo_name") or Path(split.path).stem or split.netloc).strip() or split.netloc
        return {
            "type": "git",
            "remote_url": remote_url,
            "ref": ref,
            "credential_ref": credential_ref,
            "repo_name": repo_name,
            "repo_source_ref": remote_url,
            "base_commit": None,
        }

    if source_type == "workspace_bundle":
        bundle_ref = _normalize_bundle_ref(str(repo_source.get("bundle_ref") or ""))
        repo_name = str(repo_source.get("repo_name") or "").strip() or None
        base_commit = str(repo_source.get("base_commit") or "").strip() or None
        return {
            "type": "workspace_bundle",
            "bundle_ref": bundle_ref,
            "repo_name": repo_name,
            "base_commit": base_commit,
            "repo_source_ref": bundle_ref,
            "credential_ref": None,
            "ref": None,
        }

    raise ValueError("repo_source.type must be either 'git' or 'workspace_bundle'")


def _repo_source_payload(row: dict | None) -> dict[str, Any] | None:
    if row is None:
        return None
    source_type = row.get("repo_source_type")
    source_ref = row.get("repo_source_ref")
    if not source_type or not source_ref:
        repo_path = row.get("repo_path")
        if repo_path:
            if str(repo_path).startswith("bundle://"):
                return {"type": "workspace_bundle", "bundle_ref": repo_path}
            return {"type": "legacy_path", "repo_path": repo_path}
        return None
    if source_type == "git":
        return {
            "type": "git",
            "remote_url": source_ref,
            "ref": row.get("source_ref_value"),
            "credential_ref": row.get("credential_ref"),
            "repo_name": row.get("repo_name"),
        }
    if source_type == "workspace_bundle":
        return {
            "type": "workspace_bundle",
            "bundle_ref": source_ref,
            "base_commit": row.get("base_commit"),
            "repo_name": row.get("repo_name"),
        }
    return {"type": str(source_type), "ref": source_ref}


def _resolve_repo_path(repo_path: str) -> Path:
    if repo_path.startswith("bundle://"):
        raise ValueError("bundle:// sources must be materialized before path resolution")
    path = Path(repo_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Repository path does not exist: {repo_path}")
    allowed_roots = settings.resolved_index_repo_allowed_roots()
    if not any(path == root or root in path.parents for root in allowed_roots):
        raise ValueError("Repository path is not within INDEX_REPO_ALLOWED_ROOTS")
    return path


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def validate_workspace_bundle_archive(payload: bytes) -> dict[str, Any]:
    manifest: dict[str, Any] | None = None
    seen_files: set[str] = set()
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for info in archive.infolist():
                member_path = Path(info.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError("Index bundle contains invalid path entries")
                if info.is_dir():
                    continue
                if _is_zip_symlink(info):
                    raise ValueError("Index bundles may not contain symlinks")
                if len(seen_files) > 100_000:
                    raise ValueError("Index bundle contains too many files")
                seen_files.add(info.filename)
                if info.file_size > settings.index_bundle_max_bytes:
                    raise ValueError("Index bundle contains a file that exceeds size limit")
                if info.filename == "manifest.json":
                    try:
                        manifest = json.loads(archive.read(info).decode("utf-8"))
                    except Exception as exc:  # noqa: BLE001
                        raise ValueError("Index bundle manifest.json is invalid") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError("Index bundle must be a valid .zip archive") from exc

    if manifest is None:
        raise ValueError("Index bundle must include a top-level manifest.json")
    if not isinstance(manifest, dict):
        raise ValueError("Index bundle manifest.json must be an object")
    if int(manifest.get("format_version") or 0) != 1:
        raise ValueError("Index bundle manifest.json must declare format_version=1")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("Index bundle manifest.json must include a files array")
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("Index bundle manifest.json contains an invalid file entry")
        rel_path = str(entry.get("path") or "").strip()
        if not rel_path:
            raise ValueError("Index bundle manifest.json file entry is missing path")
        normalized = Path(rel_path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Index bundle manifest.json contains invalid paths")
        if rel_path not in seen_files:
            raise ValueError(f"Index bundle manifest.json references missing file: {rel_path}")
    return manifest


def _safe_extract_bundle(payload: bytes, destination: Path) -> dict[str, Any]:
    manifest = validate_workspace_bundle_archive(payload)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if _is_zip_symlink(info):
                raise ValueError("Index bundles may not contain symlinks")
            member_path = Path(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("Index bundle contains invalid path entries")
            target = (destination / member_path).resolve()
            if target == destination or destination not in target.parents:
                raise ValueError("Index bundle escapes extraction root")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source:
                target.write_bytes(source.read())
    return manifest


def _git_credential_config(credential_ref: str | None, remote_url: str) -> dict[str, Any] | None:
    if credential_ref is None:
        return None
    credentials = settings.resolved_index_git_credential_refs()
    credential = credentials.get(credential_ref)
    if credential is None:
        raise ValueError(f"Unknown git credential_ref: {credential_ref}")
    split = urlsplit(remote_url)
    host = (split.hostname or "").lower()
    if host not in set(credential.get("allowed_hosts") or []):
        raise ValueError(f"credential_ref '{credential_ref}' is not allowed for host '{host}'")
    return credential


def _authenticated_git_remote_url(remote_url: str, credential_ref: str | None) -> str:
    credential = _git_credential_config(credential_ref, remote_url)
    if credential is None:
        return remote_url
    split = urlsplit(remote_url)
    username = credential.get("username") or "git"
    secret = credential.get("token") or credential.get("password") or ""
    netloc = f"{quote(username, safe='')}:{quote(secret, safe='')}@{split.netloc}"
    return urlunsplit((split.scheme, netloc, split.path, split.query, split.fragment))


def _run_git_command(*args: str, cwd: Path, error_context: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{error_context} failed")


@asynccontextmanager
async def _materialize_git_repo(
    *,
    remote_url: str,
    ref: str,
    credential_ref: str | None,
):
    authenticated_remote = _authenticated_git_remote_url(remote_url, credential_ref)
    with tempfile.TemporaryDirectory(prefix="viberecall-git-index-") as temp_dir:
        root = Path(temp_dir).resolve()
        _run_git_command("init", cwd=root, error_context="git init")
        _run_git_command("remote", "add", "origin", authenticated_remote, cwd=root, error_context="git remote add")
        _run_git_command("fetch", "--depth", "1", "origin", ref, cwd=root, error_context="git fetch")
        _run_git_command("checkout", "--detach", "FETCH_HEAD", cwd=root, error_context="git checkout")
        yield root


@asynccontextmanager
async def _materialize_repo_source(
    session: AsyncSession,
    *,
    project_id: str,
    repo_source_type: str | None,
    repo_source_ref: str,
    source_ref_value: str | None = None,
    credential_ref: str | None = None,
):
    if repo_source_type == "git":
        async with _materialize_git_repo(
            remote_url=repo_source_ref,
            ref=str(source_ref_value or "").strip(),
            credential_ref=credential_ref,
        ) as root:
            yield root
        return

    if repo_source_type not in {None, "workspace_bundle"} and not repo_source_ref.startswith("bundle://"):
        yield _resolve_repo_path(repo_source_ref)
        return

    bundle_id = repo_source_ref.removeprefix("bundle://").strip()
    if not bundle_id:
        raise ValueError("bundle:// source is missing bundle id")

    bundle = await get_index_bundle(session, project_id=project_id, bundle_id=bundle_id)
    if bundle is None:
        raise ValueError(f"Index bundle not found: {bundle_id}")

    payload = await get_bytes(object_key=str(bundle["object_key"]))
    with tempfile.TemporaryDirectory(prefix="viberecall-index-") as temp_dir:
        root = Path(temp_dir).resolve()
        _safe_extract_bundle(payload, root)
        yield root
