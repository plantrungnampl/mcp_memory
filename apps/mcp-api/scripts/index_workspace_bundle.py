from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


SKIP_DIRS = {
    ".git",
    ".next",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _run_git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git command failed").strip())
    return result.stdout


def _is_git_repo(repo_path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _iter_workspace_files(repo_path: Path) -> list[Path]:
    if _is_git_repo(repo_path):
        output = _run_git(repo_path, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
        paths: list[Path] = []
        for raw_path in output.split("\0"):
            if not raw_path:
                continue
            candidate = (repo_path / raw_path).resolve()
            if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
                continue
            paths.append(candidate)
        return sorted(paths)

    files: list[Path] = []
    for root, dir_names, file_names in os.walk(repo_path, topdown=True):
        dir_names[:] = [name for name in dir_names if name not in SKIP_DIRS]
        root_path = Path(root)
        for file_name in file_names:
            candidate = (root_path / file_name).resolve()
            if not candidate.is_file() or candidate.is_symlink():
                continue
            files.append(candidate)
    return sorted(files)


def _git_metadata(repo_path: Path, base_commit: str | None) -> dict[str, Any] | None:
    if not _is_git_repo(repo_path):
        return None
    head_commit = _run_git(repo_path, "rev-parse", "HEAD").strip()
    branch = _run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD").strip()
    status_output = _run_git(repo_path, "status", "--porcelain").strip()
    return {
        "head_commit": head_commit,
        "branch": branch,
        "base_commit": base_commit,
        "is_dirty": bool(status_output),
    }


def _build_manifest(repo_path: Path, repo_name: str | None, base_commit: str | None, files: list[Path]) -> dict[str, Any]:
    manifest_files: list[dict[str, Any]] = []
    for file_path in files:
        rel_path = str(file_path.relative_to(repo_path))
        payload = file_path.read_bytes()
        manifest_files.append(
            {
                "path": rel_path,
                "sha256": _sha256_bytes(payload),
                "size_bytes": len(payload),
                "mode": oct(file_path.stat().st_mode & 0o777),
            }
        )
    return {
        "format_version": 1,
        "repo_name": repo_name or repo_path.name,
        "root_relative": ".",
        "generated_at": _now_iso(),
        "git": _git_metadata(repo_path, base_commit),
        "files": manifest_files,
    }


def _create_bundle(repo_path: Path, manifest: dict[str, Any], files: list[Path]) -> tuple[Path, str, int]:
    temp_dir = Path(tempfile.mkdtemp(prefix="viberecall-workspace-bundle-"))
    archive_path = temp_dir / "workspace-bundle.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, separators=(",", ":"), sort_keys=True))
        for file_path in files:
            archive.write(file_path, arcname=str(file_path.relative_to(repo_path)))
    payload = archive_path.read_bytes()
    return archive_path, _sha256_bytes(payload), len(payload)


def _initialize_mcp_session(client: httpx.Client, base_url: str, project_id: str) -> str:
    response = client.post(
        f"{base_url.rstrip('/')}/p/{project_id}/mcp",
        headers={"accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "index_workspace_bundle.py", "version": "1.0"},
            },
        },
    )
    response.raise_for_status()
    session_id = response.headers.get("mcp-session-id")
    if not session_id:
        raise RuntimeError("MCP initialize response did not return mcp-session-id")
    return session_id


def _parse_mcp_response(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(json.dumps(body["error"]))
    content = body["result"]["content"][0]["text"]
    payload = json.loads(content)
    if not payload.get("ok", False):
        raise RuntimeError(json.dumps(payload.get("error") or {"code": "UNKNOWN"}))
    return payload["result"]


def _call_mcp_tool(
    client: httpx.Client,
    *,
    base_url: str,
    project_id: str,
    session_id: str,
    token: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        f"{base_url.rstrip('/')}/p/{project_id}/mcp",
        headers={
            "accept": "application/json, text/event-stream",
            "authorization": f"Bearer {token}",
            "mcp-session-id": session_id,
        },
        json={
            "jsonrpc": "2.0",
            "id": f"tool-{tool_name}",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    )
    return _parse_mcp_response(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload a workspace bundle and request strict v3 indexing.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--mcp-base-url", required=True)
    parser.add_argument("--mcp-token", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--repo-name")
    parser.add_argument("--base-commit")
    parser.add_argument("--poll", action="store_true")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise SystemExit(f"Repository path does not exist: {repo_path}")

    files = _iter_workspace_files(repo_path)
    if not files:
        raise SystemExit("Workspace bundle has no files to upload")

    manifest = _build_manifest(repo_path, args.repo_name, args.base_commit, files)
    archive_path, bundle_sha, bundle_size = _create_bundle(repo_path, manifest, files)

    with httpx.Client(timeout=120.0) as client:
        with archive_path.open("rb") as bundle_file:
            upload_response = client.post(
                f"{args.mcp_base_url.rstrip('/')}/p/{args.project_id}/index-bundles",
                headers={"authorization": f"Bearer {args.mcp_token}"},
                files={"file": (archive_path.name, bundle_file, "application/zip")},
            )
        upload_response.raise_for_status()
        upload_payload = upload_response.json()["bundle"]
        session_id = _initialize_mcp_session(client, args.mcp_base_url, args.project_id)
        index_result = _call_mcp_tool(
            client,
            base_url=args.mcp_base_url,
            project_id=args.project_id,
            session_id=session_id,
            token=args.mcp_token,
            tool_name="viberecall_index_repo",
            arguments={
                "repo_source": {
                    "type": "workspace_bundle",
                    "bundle_ref": upload_payload["bundle_ref"],
                    "repo_name": manifest["repo_name"],
                    "base_commit": args.base_commit,
                },
                "mode": "FULL_SNAPSHOT",
            },
        )

        output = {
            "bundle": {
                **upload_payload,
                "local_sha256": bundle_sha,
                "local_byte_size": bundle_size,
                "file_count": len(files),
            },
            "index_request": index_result,
        }

        if args.poll:
            index_run_id = str(index_result["index_run_id"])
            while True:
                status_result = _call_mcp_tool(
                    client,
                    base_url=args.mcp_base_url,
                    project_id=args.project_id,
                    session_id=session_id,
                    token=args.mcp_token,
                    tool_name="viberecall_get_index_status",
                    arguments={"index_run_id": index_run_id},
                )
                output["status"] = status_result
                if status_result["status"] not in {"QUEUED", "RUNNING"}:
                    break

        print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
