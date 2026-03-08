from __future__ import annotations

import asyncio
import json
import subprocess
from copy import deepcopy
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from viberecall_mcp import code_index
from viberecall_mcp import mcp_app as mcp_transport
from viberecall_mcp.app import create_app
from viberecall_mcp.auth import AuthenticatedToken
from viberecall_mcp.config import REPO_ROOT
from viberecall_mcp import runtime
from viberecall_mcp.memory_core.interface import DeleteEpisodeResult
from viberecall_mcp.runtime import get_memory_core, reset_runtime_state
from viberecall_mcp.runtime_types import EnqueueUpdateFactResult
from viberecall_mcp import tool_handlers


class DummySession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@asynccontextmanager
async def override_session() -> AsyncIterator[DummySession]:
    yield DummySession()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bucket_for(index_store: dict, project_id: str) -> dict:
    return index_store.setdefault(project_id, {"runs": {}, "order": [], "snapshots": {}})


def _latest_ready(index_store: dict, project_id: str) -> tuple[dict, dict] | tuple[None, None]:
    bucket = index_store.get(project_id)
    if not bucket:
        return None, None
    for index_id in reversed(bucket["order"]):
        run = bucket["runs"][index_id]
        if run["status"] == "READY":
            snapshot = bucket["snapshots"].get(index_id)
            if snapshot is not None:
                return run, snapshot
    return None, None


def _latest_run(index_store: dict, project_id: str) -> dict | None:
    bucket = index_store.get(project_id)
    if not bucket or not bucket["order"]:
        return None
    return bucket["runs"][bucket["order"][-1]]


def _build_context_from_snapshot(run: dict, snapshot: dict, *, query: str, limit: int) -> dict:
    entity_result = code_index._search_entities_in_state(
        indexed_at=run.get("completed_at"),
        entities=list(snapshot.get("entities") or []),
        query=query,
        entity_types=["Symbol", "File", "Module"],
        limit=max(limit * 3, 25),
    )
    boosted_entity_ids = {str(item.get("entity_id") or "") for item in entity_result.get("entities", [])}
    query_tokens = set(code_index._tokenize(query.strip().lower()))

    ranked_chunks: list[dict] = []
    for chunk in snapshot.get("chunks") or []:
        score = code_index._chunk_score(query_tokens, chunk, boosted_entity_ids)
        if score <= 0:
            continue
        ranked_chunks.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "entity_id": chunk.get("entity_id"),
                "file_path": chunk.get("file_path"),
                "language": chunk.get("language"),
                "line_start": chunk.get("line_start"),
                "line_end": chunk.get("line_end"),
                "snippet": chunk.get("snippet"),
                "score": round(float(score), 4),
            }
        )

    ranked_chunks.sort(
        key=lambda item: (item["score"], str(item.get("file_path") or ""), str(item.get("chunk_id") or "")),
        reverse=True,
    )
    top_chunks = ranked_chunks[: max(limit, 1)]
    relevant_symbols = [item for item in entity_result.get("entities", []) if item.get("type") == "Symbol"][:limit]
    citations = [
        {
            "citation_id": str(chunk.get("chunk_id") or ""),
            "source_type": "code_chunk",
            "entity_id": chunk.get("entity_id"),
            "file_path": chunk.get("file_path"),
            "line_start": chunk.get("line_start"),
            "line_end": chunk.get("line_end"),
            "snippet": chunk.get("snippet"),
            "score": chunk.get("score"),
        }
        for chunk in top_chunks
    ]
    architecture = snapshot.get("architecture") or {}
    return {
        "status": "READY",
        "query": query,
        "architecture_map": {
            "indexed_at": run.get("completed_at"),
            "repo_path": run.get("repo_path"),
            "summary": snapshot.get("stats") or {},
            "top_modules": list(architecture.get("top_modules") or []),
            "top_files": list(architecture.get("top_files") or []),
        },
        "relevant_symbols": relevant_symbols,
        "citations": citations,
        "gaps": [] if citations else ["No high-scoring code citations for this query."],
    }


def _complete_index_run(index_store: dict, *, index_id: str) -> None:
    for project_id, bucket in index_store.items():
        run = bucket["runs"].get(index_id)
        if run is None:
            continue

        repo_root = Path(run["repo_path"])
        mode = str(run["mode"])
        run["status"] = "RUNNING"
        run["phase"] = "discovering"
        run["effective_mode"] = mode
        run["started_at"] = _now_iso()
        previous_run, previous_snapshot = _latest_ready(index_store, project_id)
        previous_snapshot = deepcopy(previous_snapshot) if previous_snapshot is not None else None

        if mode == "snapshot":
            target_paths = code_index._iter_candidate_files(repo_root, int(run["max_files"]))
            scanned_files = len(target_paths)
            changed_files = len(target_paths)
        else:
            rel_paths = code_index._git_changed_files(repo_root, str(run["base_ref"]), str(run["head_ref"]))
            target_paths = code_index._filter_supported_rel_paths(repo_root, rel_paths)[: int(run["max_files"])]
            scanned_files = len(target_paths)
            changed_files = len(target_paths)
            if not target_paths:
                snapshot = previous_snapshot or {
                    "stats": {
                        "file_count": 0,
                        "symbol_count": 0,
                        "entity_count": 0,
                        "relationship_count": 0,
                        "chunk_count": 0,
                    },
                    "architecture": {"top_modules": [], "top_files": []},
                    "files": [],
                    "entities": [],
                    "chunks": [],
                }
                bucket["snapshots"][index_id] = snapshot
                for stale_id, stale_run in list(bucket["runs"].items()):
                    if stale_id != index_id and stale_run["status"] == "READY":
                        bucket["snapshots"].pop(stale_id, None)
                run.update(
                    {
                        "status": "READY",
                        "phase": "ready",
                        "effective_mode": "diff",
                        "processed_files": 0,
                        "total_files": 0,
                        "scanned_files": 0,
                        "changed_files": 0,
                        "completed_at": _now_iso(),
                        **(snapshot.get("stats") or {}),
                        "top_modules_json": list((snapshot.get("architecture") or {}).get("top_modules") or []),
                        "top_files_json": list((snapshot.get("architecture") or {}).get("top_files") or []),
                    }
                )
                return

        run.update(
            {
                "phase": "extracting",
                "total_files": len(target_paths),
                "scanned_files": scanned_files,
                "changed_files": changed_files,
            }
        )
        new_rows = code_index._build_file_rows(repo_root, target_paths)
        run["processed_files"] = len(new_rows)
        run["phase"] = "materializing"

        if mode == "diff":
            if previous_snapshot is None:
                run.update(
                    {
                        "status": "FAILED",
                        "phase": "failed",
                        "error": "Diff indexing requires an existing READY snapshot for this project.",
                        "completed_at": _now_iso(),
                    }
                )
                raise RuntimeError("Diff indexing requires an existing READY snapshot for this project.")
            changed_set = {str(path.relative_to(repo_root)) for path in target_paths}
            previous_rows = [
                row
                for row in (previous_snapshot.get("files") or [])
                if str(row.get("path") or "") not in changed_set
            ]
            merged_rows = previous_rows + new_rows
        else:
            merged_rows = new_rows

        materialized = code_index._materialize_index(
            project_id=project_id,
            repo_path=repo_root,
            indexed_at=_now_iso(),
            mode=mode,
            source="indexing",
            file_rows=merged_rows,
        )
        bucket["snapshots"][index_id] = materialized
        for stale_id, stale_run in list(bucket["runs"].items()):
            if stale_id != index_id and stale_run["status"] == "READY":
                bucket["snapshots"].pop(stale_id, None)
        run.update(
            {
                "status": "READY",
                "phase": "ready",
                "effective_mode": mode,
                "completed_at": _now_iso(),
                **(materialized.get("stats") or {}),
                "top_modules_json": list((materialized.get("architecture") or {}).get("top_modules") or []),
                "top_files_json": list((materialized.get("architecture") or {}).get("top_files") or []),
            }
        )
        return
    raise AssertionError(f"Unknown index run: {index_id}")


def install_fake_index_backend(monkeypatch, index_store: dict) -> None:
    async def fake_request_index_repo(
        *,
        session,
        project_id: str,
        repo_path: str,
        mode: str,
        base_ref: str | None,
        head_ref: str | None,
        max_files: int,
        requested_by_token_id: str | None,
    ) -> dict:
        _ = session
        repo_root = code_index._resolve_repo_path(repo_path)
        if mode == "diff" and (not base_ref or not head_ref):
            raise ValueError("diff mode requires both base_ref and head_ref")
        bucket = _bucket_for(index_store, project_id)
        latest = _latest_run(index_store, project_id)
        if latest is not None and latest["status"] in {"QUEUED", "RUNNING"}:
            raise RuntimeError(
                json.dumps(
                    {
                        "code": "CONFLICT",
                        "index_id": latest["index_id"],
                        "job_id": latest.get("job_id"),
                    }
                )
            )

        index_id = f"idx_test_{len(bucket['order']) + 1}"
        queued_at = _now_iso()
        bucket["order"].append(index_id)
        bucket["runs"][index_id] = {
            "index_id": index_id,
            "project_id": project_id,
            "job_id": None,
            "repo_path": str(repo_root),
            "mode": mode,
            "effective_mode": None,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "max_files": max_files,
            "status": "QUEUED",
            "phase": "queued",
            "processed_files": 0,
            "total_files": 0,
            "scanned_files": 0,
            "changed_files": 0,
            "file_count": 0,
            "symbol_count": 0,
            "entity_count": 0,
            "relationship_count": 0,
            "chunk_count": 0,
            "top_modules_json": [],
            "top_files_json": [],
            "error": None,
            "created_at": queued_at,
            "started_at": None,
            "completed_at": None,
            "requested_by_token_id": requested_by_token_id,
        }
        return {
            "index_id": index_id,
            "project_id": project_id,
            "repo_path": str(repo_root),
            "mode": mode,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "max_files": max_files,
            "queued_at": queued_at,
        }

    async def fake_attach_index_job_id(*, session, index_id: str, job_id: str) -> None:
        _ = session
        for bucket in index_store.values():
            if index_id in bucket["runs"]:
                bucket["runs"][index_id]["job_id"] = job_id
                return
        raise AssertionError(f"Unknown index run: {index_id}")

    async def fake_mark_index_request_failed(*, session, index_id: str, error: str) -> None:
        _ = session
        for bucket in index_store.values():
            if index_id in bucket["runs"]:
                bucket["runs"][index_id].update(
                    {
                        "status": "FAILED",
                        "phase": "failed",
                        "error": error,
                        "completed_at": _now_iso(),
                    }
                )
                bucket["snapshots"].pop(index_id, None)
                return
        raise AssertionError(f"Unknown index run: {index_id}")

    async def fake_index_status(*, session, project_id: str) -> dict:
        _ = session
        latest = _latest_run(index_store, project_id)
        ready_run, _snapshot = _latest_ready(index_store, project_id)
        if latest is None and ready_run is None:
            return {"status": "EMPTY", "project_id": project_id, "current": None, "latest_ready": None}
        if latest is not None and latest["status"] in {"QUEUED", "RUNNING", "FAILED"}:
            return {
                "status": latest["status"],
                "project_id": project_id,
                "current": code_index._current_run_payload(latest),
                "latest_ready": code_index._latest_ready_payload(ready_run),
            }
        return {
            "status": "READY",
            "project_id": project_id,
            "current": None,
            "latest_ready": code_index._latest_ready_payload(ready_run or latest),
        }

    async def fake_search_entities(*, session, project_id: str, query: str, entity_types: list[str] | None, limit: int) -> dict:
        _ = session
        ready_run, snapshot = _latest_ready(index_store, project_id)
        if ready_run is None or snapshot is None:
            return {"entities": [], "total": 0, "status": "EMPTY"}
        return code_index._search_entities_in_state(
            indexed_at=ready_run.get("completed_at"),
            entities=list(snapshot.get("entities") or []),
            query=query,
            entity_types=entity_types,
            limit=limit,
        )

    async def fake_build_context_pack(*, session, project_id: str, query: str, limit: int) -> dict:
        _ = session
        ready_run, snapshot = _latest_ready(index_store, project_id)
        if ready_run is None or snapshot is None:
            return {
                "status": "EMPTY",
                "query": query,
                "architecture_map": {
                    "indexed_at": None,
                    "repo_path": None,
                    "summary": {
                        "file_count": 0,
                        "symbol_count": 0,
                        "entity_count": 0,
                        "relationship_count": 0,
                        "chunk_count": 0,
                    },
                    "top_modules": [],
                    "top_files": [],
                },
                "relevant_symbols": [],
                "citations": [],
            }
        return _build_context_from_snapshot(ready_run, snapshot, query=query, limit=limit)

    monkeypatch.setattr(tool_handlers, "request_index_repo", fake_request_index_repo)
    monkeypatch.setattr(tool_handlers, "attach_index_job_id", fake_attach_index_job_id)
    monkeypatch.setattr(tool_handlers, "mark_index_request_failed", fake_mark_index_request_failed)
    monkeypatch.setattr(tool_handlers, "index_status", fake_index_status)
    monkeypatch.setattr(tool_handlers, "search_entities", fake_search_entities)
    monkeypatch.setattr(tool_handlers, "build_context_pack", fake_build_context_pack)


def parse_mcp_event(response):
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data: "):
                return json.loads(line.removeprefix("data: "))
        raise AssertionError("Missing data frame in event-stream response")
    return response.json()


def parse_result(response):
    body = parse_mcp_event(response)
    content = body["result"]["content"][0]["text"]
    return json.loads(content)


def initialize_session(client: TestClient, project_id: str) -> str:
    response = client.post(
        f"/p/{project_id}/mcp",
        headers={"accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        },
    )
    assert response.status_code == 200
    return response.headers["mcp-session-id"]


def mcp_headers(session_id: str, authorization: str = "Bearer test-token", **extra: str) -> dict[str, str]:
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-session-id": session_id,
        "authorization": authorization,
    }
    headers.update(extra)
    return headers


def make_token(
    plan: str = "pro",
    project_id: str = "proj_test",
    scopes: list[str] | None = None,
) -> AuthenticatedToken:
    return AuthenticatedToken(
        token_id="tok_test",
        project_id=project_id,
        scopes=scopes if scopes is not None else ["memory:read", "memory:write", "facts:read", "facts:write", "timeline:read"],
        plan=plan,
        db_name=f"vr_{project_id}",
    )


def setup_app(monkeypatch, token: AuthenticatedToken, episode_store: dict) -> None:
    asyncio.run(reset_runtime_state())
    monkeypatch.setattr(runtime.settings, "memory_backend", "local")
    monkeypatch.setattr(runtime.settings, "kv_backend", "local")
    monkeypatch.setattr(runtime.settings, "queue_backend", "eager")
    object_store: dict[str, str] = {}
    index_store: dict = {}
    install_fake_index_backend(monkeypatch, index_store)

    async def fake_auth(_session, *, authorization, project_id):
        assert authorization == "Bearer test-token"
        assert project_id == token.project_id
        return token

    async def fake_touch(_session, _token_id: str) -> None:
        return None

    async def fake_audit(*args, **kwargs) -> None:
        return None

    async def fake_create_episode(
        session,
        *,
        episode_id: str,
        project_id: str,
        content: str | None,
        reference_time: str | None,
        metadata_json: str,
        content_ref: str | None = None,
        summary: str | None = None,
        job_id: str | None = None,
        enrichment_status: str = "pending",
    ) -> None:
        episode_store[episode_id] = {
            "episode_id": episode_id,
            "project_id": project_id,
            "content": content,
            "content_ref": content_ref,
            "reference_time": reference_time,
            "metadata_json": metadata_json,
            "job_id": job_id,
            "enrichment_status": enrichment_status,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        }

    async def fake_list_timeline(
        session,
        *,
        project_id: str,
        from_time: str | None,
        to_time: str | None,
        limit: int,
        offset: int,
    ) -> list[dict]:
        rows = [
            {
                "episode_id": episode["episode_id"],
                "reference_time": episode["reference_time"],
                "ingested_at": episode["ingested_at"],
                "summary": episode["summary"] or episode["content"][:160],
                "metadata": json.loads(episode["metadata_json"]),
            }
            for episode in episode_store.values()
            if episode["project_id"] == project_id
        ]
        rows.sort(key=lambda row: (row["reference_time"] or row["ingested_at"], row["episode_id"]), reverse=True)
        return rows[offset : offset + limit]

    async def fake_recent_raw(
        session,
        *,
        project_id: str,
        query: str,
        window_seconds: int,
        limit: int,
        offset: int,
    ) -> list[dict]:
        rows = []
        for episode in episode_store.values():
            if episode["project_id"] != project_id or episode["enrichment_status"] == "complete":
                continue
            haystack = f"{episode.get('summary') or ''} {episode.get('content') or ''}".lower()
            if query.lower() not in haystack:
                continue
            rows.append(
                {
                    "episode_id": episode["episode_id"],
                    "reference_time": episode["reference_time"],
                    "ingested_at": episode["ingested_at"],
                    "summary": episode.get("summary") or (episode.get("content") or "")[:160],
                    "metadata": json.loads(episode["metadata_json"]),
                }
            )
        rows.sort(key=lambda row: (row["ingested_at"], row["episode_id"]), reverse=True)
        return rows[offset : offset + limit]

    async def fake_set_episode_job_id(session, *, episode_id: str, job_id: str) -> None:
        episode_store[episode_id]["job_id"] = job_id

    async def fake_delete_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        row = episode_store.get(episode_id)
        if row is None or row.get("project_id") != project_id:
            return None
        episode_store.pop(episode_id, None)
        return {
            "episode_id": episode_id,
            "project_id": project_id,
            "content_ref": row.get("content_ref"),
        }

    async def fake_get_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        row = episode_store.get(episode_id)
        if row is None or row.get("project_id") != project_id:
            return None
        return {
            "episode_id": episode_id,
            "project_id": project_id,
            "reference_time": row.get("reference_time"),
            "ingested_at": row.get("ingested_at"),
            "content_ref": row.get("content_ref"),
        }

    async def fake_monthly_vibe_tokens(_session, *, project_id: str) -> int:
        return 0

    async def fake_put_text(*, object_key: str, content: str) -> None:
        object_store[object_key] = content

    async def fake_delete_object(*, object_key: str) -> bool:
        return object_store.pop(object_key, None) is not None

    class FakeQueue:
        async def enqueue_ingest(self, *, episode_id: str, project_id: str, request_id: str, token_id: str | None):
            episode = episode_store[episode_id]
            if not episode.get("content") and episode.get("content_ref"):
                episode["content"] = object_store[str(episode["content_ref"])]
            result = await get_memory_core().ingest_episode(project_id, episode)
            episode["summary"] = result["summary"]
            episode["enrichment_status"] = "complete"
            return "job_ingest_test"

        async def enqueue_update_fact(
            self,
            *,
            project_id: str,
            request_id: str,
            token_id: str | None,
            fact_id: str,
            new_fact_id: str,
            new_text: str,
            effective_time: str,
            reason: str | None,
        ):
            result = await get_memory_core().update_fact(
                project_id,
                fact_id=fact_id,
                new_fact_id=new_fact_id,
                new_text=new_text,
                effective_time=effective_time,
                reason=reason,
            )
            return EnqueueUpdateFactResult(job_id="job_update_test", immediate_result=result)

        async def enqueue_index_repo(self, *, index_id: str, project_id: str, request_id: str, token_id: str | None):
            _ = (request_id, token_id)
            job_id = f"job_index_test_{len(_bucket_for(index_store, project_id)['order'])}"
            _complete_index_run(index_store, index_id=index_id)
            return job_id

    monkeypatch.setattr(mcp_transport, "open_db_session", override_session)
    monkeypatch.setattr(mcp_transport, "authenticate_bearer_token", fake_auth)
    monkeypatch.setattr(mcp_transport, "touch_token_usage", fake_touch)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit)
    monkeypatch.setattr(tool_handlers, "create_episode", fake_create_episode)
    monkeypatch.setattr(tool_handlers, "get_episode_for_project", fake_get_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_episode_for_project", fake_delete_episode_for_project)
    monkeypatch.setattr(tool_handlers, "list_timeline_episodes", fake_list_timeline)
    monkeypatch.setattr(tool_handlers, "list_recent_raw_episodes", fake_recent_raw)
    monkeypatch.setattr(tool_handlers, "set_episode_job_id", fake_set_episode_job_id)
    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: FakeQueue())
    monkeypatch.setattr(tool_handlers, "put_text", fake_put_text)
    monkeypatch.setattr(tool_handlers, "delete_object", fake_delete_object)
    return index_store


def setup_app_celery_transport(monkeypatch, token: AuthenticatedToken, episode_store: dict) -> None:
    asyncio.run(reset_runtime_state())
    monkeypatch.setattr(runtime.settings, "memory_backend", "local")
    monkeypatch.setattr(runtime.settings, "kv_backend", "local")
    monkeypatch.setattr(runtime.settings, "queue_backend", "celery")
    object_store: dict[str, str] = {}

    async def fake_auth(_session, *, authorization, project_id):
        assert authorization == "Bearer test-token"
        assert project_id == token.project_id
        return token

    async def fake_touch(_session, _token_id: str) -> None:
        return None

    async def fake_audit(*args, **kwargs) -> None:
        return None

    async def fake_create_episode(
        session,
        *,
        episode_id: str,
        project_id: str,
        content: str | None,
        reference_time: str | None,
        metadata_json: str,
        content_ref: str | None = None,
        summary: str | None = None,
        job_id: str | None = None,
        enrichment_status: str = "pending",
    ) -> None:
        episode_store[episode_id] = {
            "episode_id": episode_id,
            "project_id": project_id,
            "content": content,
            "content_ref": content_ref,
            "reference_time": reference_time,
            "metadata_json": metadata_json,
            "job_id": job_id,
            "enrichment_status": enrichment_status,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        }

    async def fake_set_episode_job_id(session, *, episode_id: str, job_id: str) -> None:
        episode_store[episode_id]["job_id"] = job_id

    async def fake_delete_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        row = episode_store.get(episode_id)
        if row is None or row.get("project_id") != project_id:
            return None
        episode_store.pop(episode_id, None)
        return {
            "episode_id": episode_id,
            "project_id": project_id,
            "content_ref": row.get("content_ref"),
        }

    async def fake_get_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        row = episode_store.get(episode_id)
        if row is None or row.get("project_id") != project_id:
            return None
        return {
            "episode_id": episode_id,
            "project_id": project_id,
            "reference_time": row.get("reference_time"),
            "ingested_at": row.get("ingested_at"),
            "content_ref": row.get("content_ref"),
        }

    async def fake_monthly_vibe_tokens(_session, *, project_id: str) -> int:
        return 0

    async def fake_put_text(*, object_key: str, content: str) -> None:
        object_store[object_key] = content

    async def fake_delete_object(*, object_key: str) -> bool:
        return object_store.pop(object_key, None) is not None

    monkeypatch.setattr(mcp_transport, "open_db_session", override_session)
    monkeypatch.setattr(mcp_transport, "authenticate_bearer_token", fake_auth)
    monkeypatch.setattr(mcp_transport, "touch_token_usage", fake_touch)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit)
    monkeypatch.setattr(tool_handlers, "create_episode", fake_create_episode)
    monkeypatch.setattr(tool_handlers, "get_episode_for_project", fake_get_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_episode_for_project", fake_delete_episode_for_project)
    monkeypatch.setattr(tool_handlers, "set_episode_job_id", fake_set_episode_job_id)
    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(tool_handlers, "put_text", fake_put_text)
    monkeypatch.setattr(tool_handlers, "delete_object", fake_delete_object)
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.ingest_episode_task.delay",
        lambda *args: SimpleNamespace(id="celery-ingest-http-1"),
    )
    monkeypatch.setattr(
        "viberecall_mcp.workers.tasks.update_fact_task.delay",
        lambda *args: SimpleNamespace(id="celery-update-http-1"),
    )


def teardown_app() -> None:
    asyncio.run(reset_runtime_state())


def seed_repo_index(monkeypatch, tmp_path: Path, *, project_id: str, index_store: dict) -> Path:
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))
    repo_dir = tmp_path / f"{project_id}-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "api.ts").write_text(
        "\n".join(
            [
                "import { readFileSync } from 'node:fs'",
                "",
                "export function buildContextPack(query: string) {",
                "  return readFileSync(query, 'utf-8')",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_dir / "worker.py").write_text(
        "\n".join(
            [
                "from typing import Any",
                "",
                "def index_repo(path: str) -> dict[str, Any]:",
                "    return {'path': path}",
            ]
        ),
        encoding="utf-8",
    )
    request = asyncio.run(
        tool_handlers.request_index_repo(
            session=DummySession(),
            project_id=project_id,
            repo_path=str(repo_dir),
            mode="snapshot",
            base_ref=None,
            head_ref=None,
            max_files=5000,
            requested_by_token_id="tok_test",
        )
    )
    asyncio.run(
        tool_handlers.attach_index_job_id(
            session=DummySession(),
            index_id=str(request["index_id"]),
            job_id="job_index_seed",
        )
    )
    _complete_index_run(index_store, index_id=str(request["index_id"]))
    return repo_dir


def test_tools_list_returns_full_toolset_for_free_plan(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 200
    tool_names = [tool["name"] for tool in parse_mcp_event(response)["result"]["tools"]]
    assert tool_names == [
        "viberecall_save",
        "viberecall_search",
        "viberecall_get_facts",
        "viberecall_update_fact",
        "viberecall_timeline",
        "viberecall_get_status",
        "viberecall_delete_episode",
        "viberecall_index_repo",
        "viberecall_index_status",
        "viberecall_search_entities",
        "viberecall_get_context_pack",
    ]


def test_streamable_http_get_without_accept_returns_406(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        response = client.get("/p/proj_test/mcp")

    teardown_app()
    assert response.status_code == 406
    body = response.json()
    assert body["error"]["message"] == "Not Acceptable: Client must accept text/event-stream"


def test_streamable_http_unknown_session_returns_404(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        response = client.post(
            "/p/proj_test/mcp",
            headers={
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
                "mcp-session-id": "stale-session-id",
            },
            json={
                "jsonrpc": "2.0",
                "id": "init-stale",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
        )

    teardown_app()
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["message"] == "Session not found"


def test_missing_scope_blocks_get_facts(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free", scopes=[]), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "viberecall_get_facts", "arguments": {}},
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "FORBIDDEN"
    assert payload["error"]["details"]["required_scope"] == "facts:read"


def test_free_plan_index_and_context_pack_flow(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_test"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "mini-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "api.ts").write_text(
        "\n".join(
            [
                "import { readFileSync } from 'node:fs'",
                "",
                "export function buildContextPack(query: string) {",
                "  return readFileSync(query, 'utf-8')",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_dir / "worker.py").write_text(
        "\n".join(
            [
                "from typing import Any",
                "",
                "def index_repo(path: str) -> dict[str, Any]:",
                "    return {'path': path}",
            ]
        ),
        encoding="utf-8",
    )
    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        index_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "snapshot"},
                },
            },
        )
        index_payload = parse_result(index_response)
        assert index_payload["ok"] is True
        assert index_payload["result"]["status"] == "ACCEPTED"
        assert index_payload["result"]["index_id"].startswith("idx_test_")
        assert index_payload["result"]["job_id"].startswith("job_index_test_")

        search_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "index_repo", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_response)
        assert search_payload["ok"] is True
        assert any(item["type"] == "Symbol" for item in search_payload["result"]["entities"])

        pack_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "3",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )
        pack_payload = parse_result(pack_response)
        assert pack_payload["ok"] is True
        assert pack_payload["result"]["status"] == "READY"
        assert "architecture_map" in pack_payload["result"]
        assert isinstance(pack_payload["result"]["citations"], list)

        status_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "4",
                "method": "tools/call",
                "params": {"name": "viberecall_index_status", "arguments": {}},
            },
        )
        status_payload = parse_result(status_response)
        assert status_payload["ok"] is True
        assert status_payload["result"]["status"] == "READY"
        assert status_payload["result"]["latest_ready"]["stats"]["file_count"] >= 2
        assert not (REPO_ROOT / ".viberecall" / f"index-state-{project_id}.json").exists()

    teardown_app()


def test_index_repo_returns_conflict_while_run_is_active(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_conflict"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "conflict-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    class PendingQueue:
        async def enqueue_index_repo(self, *, index_id: str, project_id: str, request_id: str, token_id: str | None):
            _ = (index_id, project_id, request_id, token_id)
            return "job_index_pending"

    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: PendingQueue())

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        first = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "conflict-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "snapshot"},
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "conflict-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "snapshot"},
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "CONFLICT"


def test_index_repo_diff_requires_refs(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_diff_refs"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))

    repo_dir = tmp_path / "diff-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "diff-missing-refs",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "diff"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_diff_zero_changes_preserves_latest_ready_snapshot(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_zero_diff"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    repo_dir = seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "dev@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Dev"], cwd=repo_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True, capture_output=True, text=True)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "zero-diff",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_path": str(repo_dir),
                        "mode": "diff",
                        "base_ref": head_sha,
                        "head_ref": head_sha,
                    },
                },
            },
        )
        status_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "zero-diff-status",
                "method": "tools/call",
                "params": {"name": "viberecall_index_status", "arguments": {}},
            },
        )

    teardown_app()
    payload = parse_result(response)
    status_payload = parse_result(status_response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "ACCEPTED"
    assert status_payload["result"]["status"] == "READY"
    assert status_payload["result"]["latest_ready"]["effective_mode"] == "diff"
    assert status_payload["result"]["latest_ready"]["stats"]["file_count"] >= 2


def test_search_and_context_pack_ignore_queued_run(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_latest_ready_only"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    repo_dir = seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)
    (repo_dir / "new-module.ts").write_text("export function futureSymbol() { return 1 }\n", encoding="utf-8")

    class PendingQueue:
        async def enqueue_index_repo(self, *, index_id: str, project_id: str, request_id: str, token_id: str | None):
            _ = (index_id, project_id, request_id, token_id)
            return "job_index_pending"

    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: PendingQueue())

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        accepted = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-index",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "snapshot"},
                },
            },
        )
        search_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "futureSymbol", "limit": 10},
                },
            },
        )
        pack_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-pack",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "futureSymbol", "limit": 5},
                },
            },
        )
        status_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "queued-status",
                "method": "tools/call",
                "params": {"name": "viberecall_index_status", "arguments": {}},
            },
        )

    teardown_app()
    accepted_payload = parse_result(accepted)
    search_payload = parse_result(search_response)
    pack_payload = parse_result(pack_response)
    status_payload = parse_result(status_response)
    assert accepted_payload["ok"] is True
    assert accepted_payload["result"]["status"] == "ACCEPTED"
    assert search_payload["result"]["status"] == "READY"
    assert search_payload["result"]["entities"] == []
    assert pack_payload["result"]["status"] == "READY"
    assert pack_payload["result"]["citations"] == []
    assert status_payload["result"]["status"] == "QUEUED"
    assert status_payload["result"]["latest_ready"]["stats"]["file_count"] >= 2


def test_failed_index_run_keeps_latest_ready_snapshot(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_failed_keeps_ready"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)

    repo_dir = tmp_path / "broken-diff-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "failed-diff",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {
                        "repo_path": str(repo_dir),
                        "mode": "diff",
                        "base_ref": "HEAD~1",
                        "head_ref": "HEAD",
                    },
                },
            },
        )
        status_response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "failed-diff-status",
                "method": "tools/call",
                "params": {"name": "viberecall_index_status", "arguments": {}},
            },
        )

    teardown_app()
    payload = parse_result(response)
    status_payload = parse_result(status_response)
    assert payload["ok"] is False
    assert status_payload["result"]["status"] == "FAILED"
    assert status_payload["result"]["current"]["error"]
    assert status_payload["result"]["latest_ready"]["stats"]["file_count"] >= 2


def test_search_rate_limit_enforced(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_token_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_project_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_window_seconds", 60)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        first = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-rate-1",
                "method": "tools/call",
                "params": {"name": "viberecall_search", "arguments": {"query": "missing"}},
            },
        )
        second = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-rate-2",
                "method": "tools/call",
                "params": {"name": "viberecall_search", "arguments": {"query": "missing"}},
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"


def test_search_entities_rate_limit_enforced(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_search_entities_rate"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_token_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_project_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_window_seconds", 60)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        first = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entities-rate-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "index_repo", "limit": 10},
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "entities-rate-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search_entities",
                    "arguments": {"query": "index_repo", "limit": 10},
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"


def test_get_context_pack_rate_limit_enforced(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_context_rate"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_token_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_project_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_window_seconds", 60)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        first = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "context-rate-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "context-rate-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"


def test_index_repo_rate_limit_enforced(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_rate"
    setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(tmp_path))
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_token_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_project_capacity", 3)
    monkeypatch.setattr(tool_handlers.settings, "rate_limit_window_seconds", 60)

    repo_dir = tmp_path / "rate-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def index_repo(path: str):\n    return path\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        first = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "index-rate-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "snapshot"},
                },
            },
        )
        second = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "index-rate-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "snapshot"},
                },
            },
        )

    teardown_app()
    assert parse_result(first)["ok"] is True
    payload = parse_result(second)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"


def test_get_context_pack_loads_index_state_once(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_context_cache"
    index_store = setup_app(monkeypatch, make_token(plan="free", project_id=project_id), episode_store)
    seed_repo_index(monkeypatch, tmp_path, project_id=project_id, index_store=index_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "context-cache-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_context_pack",
                    "arguments": {"query": "context pack", "limit": 5},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "READY"
    assert payload["result"]["architecture_map"]["summary"]["file_count"] >= 2


def test_index_repo_rejects_paths_outside_allowlist(monkeypatch, tmp_path: Path) -> None:
    episode_store = {}
    project_id = "proj_index_blocked"
    setup_app(monkeypatch, make_token(plan="pro", project_id=project_id), episode_store)
    monkeypatch.setattr(code_index.settings, "index_repo_allowed_roots", str(REPO_ROOT))

    repo_dir = tmp_path / "blocked-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "worker.py").write_text("def blocked() -> None:\n    return None\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, project_id)
        response = client.post(
            f"/p/{project_id}/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "blocked-index",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_index_repo",
                    "arguments": {"repo_path": str(repo_dir), "mode": "snapshot"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_save_search_timeline_and_update_fact_flow(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "Fix auth middleware bug in login flow",
                        "metadata": {
                            "type": "bugfix",
                            "repo": "viberecall",
                            "files": ["apps/web/src/proxy.ts"],
                            "tags": ["auth"],
                        },
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        episode_id = save_payload["result"]["episode_id"]
        assert episode_id in episode_store

        search_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "auth middleware", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_response)
        assert search_payload["ok"] is True
        first_result = search_payload["result"]["results"][0]
        assert first_result["kind"] == "fact"

        facts_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "3",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"filters": {"tag": "auth"}, "limit": 20},
                },
            },
        )
        facts_payload = parse_result(facts_response)
        assert facts_payload["ok"] is True
        fact_id = facts_payload["result"]["facts"][0]["id"]

        timeline_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "4",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_timeline",
                    "arguments": {"limit": 20},
                },
            },
        )
        timeline_payload = parse_result(timeline_response)
        assert timeline_payload["ok"] is True
        assert timeline_payload["result"]["episodes"][0]["episode_id"] == episode_id

        update_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-2"}),
            json={
                "jsonrpc": "2.0",
                "id": "5",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_update_fact",
                    "arguments": {
                        "fact_id": fact_id,
                        "new_text": "Fix auth middleware race in login callback flow",
                        "effective_time": "2026-02-28T14:00:00Z",
                        "reason": "narrowed root cause",
                    },
                },
            },
        )
        update_payload = parse_result(update_response)
        assert update_payload["ok"] is True
        assert update_payload["result"]["old_fact"]["id"] == fact_id

    teardown_app()


def test_search_pagination_keeps_mixed_fact_and_episode_results_stable(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    fact_results = [
        {
            "kind": "fact",
            "fact": {"id": "fact_4", "text": "fact 4", "valid_at": "2026-03-06T00:00:04Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:04Z"},
            "score": 0.3,
        },
        {
            "kind": "fact",
            "fact": {"id": "fact_3", "text": "fact 3", "valid_at": "2026-03-06T00:00:03Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:03Z"},
            "score": 0.3,
        },
        {
            "kind": "fact",
            "fact": {"id": "fact_2", "text": "fact 2", "valid_at": "2026-03-06T00:00:02Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:02Z"},
            "score": 0.3,
        },
        {
            "kind": "fact",
            "fact": {"id": "fact_1", "text": "fact 1", "valid_at": "2026-03-06T00:00:01Z", "invalid_at": None},
            "entities": [],
            "provenance": {"ingested_at": "2026-03-06T00:00:01Z"},
            "score": 0.3,
        },
    ]
    recent_episodes = [
        {
            "episode_id": "ep_recent",
            "reference_time": None,
            "ingested_at": "2026-03-06T00:01:00Z",
            "summary": "repeat me once",
            "metadata": {},
        }
    ]

    class FakeMemoryCore:
        async def search(self, project_id, query, filters, sort, limit, offset):  # noqa: ANN001
            assert project_id == "proj_test"
            return fact_results[offset : offset + limit]

    async def fake_recent_raw(
        session,
        *,
        project_id: str,
        query: str,
        window_seconds: int,
        limit: int,
        offset: int,
    ) -> list[dict]:
        assert project_id == "proj_test"
        return recent_episodes[offset : offset + limit]

    monkeypatch.setattr(tool_handlers, "get_memory_core", lambda: FakeMemoryCore())
    monkeypatch.setattr(tool_handlers, "list_recent_raw_episodes", fake_recent_raw)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        page1 = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-page-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "repeat", "limit": 2},
                },
            },
        )
        page1_payload = parse_result(page1)
        page1_results = page1_payload["result"]["results"]
        assert [item["kind"] for item in page1_results] == ["episode", "fact"]
        assert page1_results[0]["episode"]["episode_id"] == "ep_recent"
        assert page1_results[1]["fact"]["id"] == "fact_4"
        assert page1_payload["result"]["next_cursor"] is not None

        page2 = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-page-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {
                        "query": "repeat",
                        "limit": 2,
                        "cursor": page1_payload["result"]["next_cursor"],
                    },
                },
            },
        )
        page2_payload = parse_result(page2)
        page2_results = page2_payload["result"]["results"]
        assert [item["kind"] for item in page2_results] == ["fact", "fact"]
        assert [item["fact"]["id"] for item in page2_results] == ["fact_3", "fact_2"]

    teardown_app()


def test_save_large_content_uses_content_ref(monkeypatch) -> None:
    episode_store = {}
    setup_app_celery_transport(monkeypatch, make_token(), episode_store)
    monkeypatch.setattr(tool_handlers.settings, "raw_episode_inline_max_bytes", 1024)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        large_content = "A" * 2048
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-large-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "save-large",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {"content": large_content, "metadata": {"tags": ["large"]}},
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        episode_id = save_payload["result"]["episode_id"]
        stored = episode_store[episode_id]
        assert stored["content"] is None
        assert stored["content_ref"] == f"projects/proj_test/episodes/{episode_id}.txt"

    teardown_app()


def test_celery_queue_path_surfaces_task_ids_over_mcp_http(monkeypatch) -> None:
    episode_store = {}
    setup_app_celery_transport(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-celery-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "celery-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "Queue save through celery transport path",
                        "metadata": {"tags": ["queue", "celery"]},
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        assert save_payload["result"]["enrichment"]["job_id"] == "celery-ingest-http-1"

        episode_id = save_payload["result"]["episode_id"]
        assert episode_store[episode_id]["job_id"] == "celery-ingest-http-1"

        update_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-celery-2"}),
            json={
                "jsonrpc": "2.0",
                "id": "celery-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_update_fact",
                    "arguments": {
                        "fact_id": "fact_existing",
                        "new_text": "Update fact asynchronously with celery",
                        "effective_time": "2026-02-28T15:00:00Z",
                    },
                },
            },
        )
        update_payload = parse_result(update_response)
        assert update_payload["ok"] is True
        assert update_payload["result"]["job_id"] == "celery-update-http-1"
        assert update_payload["result"]["old_fact"]["id"] == "fact_existing"

    teardown_app()


def test_malformed_cursor_returns_invalid_argument(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "6",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "auth", "cursor": "not-a-cursor"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_protocol_version_mismatch_returns_http_400(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"MCP-Protocol-Version": "2024-01-01"}),
            json={"jsonrpc": "2.0", "id": "7", "method": "tools/list", "params": {}},
        )

    teardown_app()
    assert response.status_code == 400


def test_payload_too_large_returns_http_413(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        monkeypatch.setattr(mcp_transport.settings, "max_payload_bytes", 1)
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={"jsonrpc": "2.0", "id": "8", "method": "tools/list", "params": {}},
        )

    teardown_app()
    if response.status_code == 413:
        return
    assert response.status_code == 200
    body = parse_mcp_event(response)
    assert "error" in body
    assert "payload" in str(body["error"]).lower()


def test_save_uses_rate_limit_and_keeps_quota_non_blocking(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)
    rate_limit_calls: list[tuple[str, int, int]] = []

    async def fake_monthly_vibe_tokens(*_args, **_kwargs):
        return 100_000

    class FakeLimiter:
        async def check(self, key: str, *, capacity: int, window_seconds: int):
            rate_limit_calls.append((key, capacity, window_seconds))
            return SimpleNamespace(allowed=True, reset_at="2026-03-08T00:00:00Z")

    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(tool_handlers, "get_rate_limiter", lambda: FakeLimiter())

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "9",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {"content": "quota-test"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "ACCEPTED"
    assert len(rate_limit_calls) == 2
    assert rate_limit_calls[0][0].startswith("token:tok_test:viberecall_save")
    assert rate_limit_calls[1][0].startswith("project:proj_test:viberecall_save")


def test_get_status_available_for_free_plan(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "status-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_status",
                    "arguments": {},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["service"] == "viberecall-mcp"
    assert payload["result"]["project_id"] == "proj_test"
    assert "backends" in payload["result"]


def test_get_status_reports_degraded_graph_dependency(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)
    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "graphiti_api_key", "test-key")

    async def fake_graph_dependency_failure_detail() -> str | None:
        return (
            "Graph dependency check failed for memory backend 'graphiti': "
            "Error 111 connecting to localhost:6380. Connection refused."
        )

    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "status-degraded-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_status",
                    "arguments": {},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "degraded"
    assert "localhost:6380" in payload["result"]["graphiti"]["detail"]


def test_save_returns_upstream_error_before_side_effects_when_graph_dependency_unavailable(
    monkeypatch,
) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)
    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "raw_episode_inline_max_bytes", 32)

    async def fake_graph_dependency_failure_detail() -> str | None:
        return (
            "Graph dependency check failed for memory backend 'graphiti': "
            "Error 111 connecting to localhost:6380. Connection refused."
        )

    put_calls = {"count": 0}

    async def fake_put_text(*, object_key: str, content: str) -> None:
        _ = (object_key, content)
        put_calls["count"] += 1

    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )
    monkeypatch.setattr(tool_handlers, "put_text", fake_put_text)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-degraded-save"}),
            json={
                "jsonrpc": "2.0",
                "id": "save-degraded-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "A" * 128,
                        "metadata": {"tags": ["dependency-check"]},
                    },
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UPSTREAM_ERROR"
    assert "localhost:6380" in payload["error"]["message"]
    assert episode_store == {}
    assert put_calls["count"] == 0


def test_search_returns_upstream_error_when_graph_dependency_unavailable(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)
    monkeypatch.setattr(runtime.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")

    async def fake_graph_dependency_failure_detail() -> str | None:
        return (
            "Graph dependency check failed for memory backend 'graphiti': "
            "Error 111 connecting to localhost:6380. Connection refused."
        )

    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "search-degraded-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "auth middleware", "limit": 10},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UPSTREAM_ERROR"
    assert "localhost:6380" in payload["error"]["message"]


def test_delete_episode_full_delete_and_idempotent(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        save_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-del-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "del-save",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_save",
                    "arguments": {
                        "content": "Episode to delete",
                        "metadata": {"tags": ["cleanup"]},
                    },
                },
            },
        )
        save_payload = parse_result(save_response)
        assert save_payload["ok"] is True
        episode_id = save_payload["result"]["episode_id"]

        facts_before = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-facts-before",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"filters": {"tag": "cleanup"}, "limit": 20},
                },
            },
        )
        facts_before_payload = parse_result(facts_before)
        assert facts_before_payload["ok"] is True
        fact_id = facts_before_payload["result"]["facts"][0]["id"]

        update_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id, **{"Idempotency-Key": "idem-del-update-1"}),
            json={
                "jsonrpc": "2.0",
                "id": "del-update",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_update_fact",
                    "arguments": {
                        "fact_id": fact_id,
                        "new_text": "Episode to delete updated",
                        "effective_time": "2026-03-08T05:00:00Z",
                        "reason": "delete regression coverage",
                    },
                },
            },
        )
        update_payload = parse_result(update_response)
        assert update_payload["ok"] is True

        delete_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": episode_id},
                },
            },
        )
        delete_payload = parse_result(delete_response)
        assert delete_payload["ok"] is True
        assert delete_payload["result"]["status"] == "DELETED"
        assert delete_payload["result"]["deleted"]["postgres"] is True

        timeline_after = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-timeline",
                "method": "tools/call",
                "params": {"name": "viberecall_timeline", "arguments": {"limit": 20}},
            },
        )
        timeline_payload = parse_result(timeline_after)
        assert timeline_payload["ok"] is True
        assert timeline_payload["result"]["episodes"] == []

        search_after = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "Episode to delete", "limit": 20},
                },
            },
        )
        search_payload = parse_result(search_after)
        assert search_payload["ok"] is True
        assert search_payload["result"]["results"] == []

        facts_after = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-facts",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"filters": {"tag": "cleanup"}, "limit": 20},
                },
            },
        )
        facts_payload = parse_result(facts_after)
        assert facts_payload["ok"] is True
        assert facts_payload["result"]["facts"] == []

        delete_again = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-2",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": episode_id},
                },
            },
        )
        delete_again_payload = parse_result(delete_again)
        assert delete_again_payload["ok"] is True
        assert delete_again_payload["result"]["status"] == "NOT_FOUND"


def test_free_plan_can_call_delete_episode(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="free"), episode_store)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-free-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": "ep_missing"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "NOT_FOUND"


def test_delete_episode_returns_upstream_error_when_canonical_cleanup_incomplete(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    calls = {"delete_row": 0, "delete_object": 0}

    class FakeMemoryCore:
        async def delete_episode(self, project_id: str, *, episode_id: str) -> DeleteEpisodeResult:
            assert project_id == "proj_test"
            assert episode_id == "ep_partial"
            return DeleteEpisodeResult(
                found=True,
                deleted_episode_node=False,
                deleted_fact_count=0,
                updated_fact_count=0,
                remaining_fact_count=2,
            )

    async def fake_get_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        assert project_id == "proj_test"
        assert episode_id == "ep_partial"
        return {
            "episode_id": episode_id,
            "project_id": project_id,
            "content_ref": "objects/ep_partial.txt",
        }

    async def fake_delete_episode_for_project(_session, *, project_id: str, episode_id: str) -> dict | None:
        calls["delete_row"] += 1
        return None

    async def fake_delete_object(*, object_key: str) -> bool:
        calls["delete_object"] += 1
        return True

    monkeypatch.setattr(tool_handlers, "get_memory_core", lambda: FakeMemoryCore())
    monkeypatch.setattr(tool_handlers, "get_episode_for_project", fake_get_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_episode_for_project", fake_delete_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_object", fake_delete_object)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "del-partial-1",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_delete_episode",
                    "arguments": {"episode_id": "ep_partial"},
                },
            },
        )

    teardown_app()
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UPSTREAM_ERROR"
    assert payload["error"]["details"]["remaining_fact_count"] == 2
    assert calls["delete_row"] == 0
    assert calls["delete_object"] == 0


def test_tool_error_returns_payload_even_when_error_audit_fails(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    async def fake_timeline_failure(*_args, **_kwargs):
        raise ValueError("timeline query failed")

    async def fake_audit_with_error(*_args, **kwargs) -> None:
        if kwargs.get("action") == "tools/call" and kwargs.get("status") == "error":
            raise RuntimeError("audit insert failed")
        return None

    monkeypatch.setattr(tool_handlers, "list_timeline_episodes", fake_timeline_failure)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit_with_error)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "timeline-fail-1",
                "method": "tools/call",
                "params": {"name": "viberecall_timeline", "arguments": {"limit": 20}},
            },
        )

    teardown_app()
    assert response.status_code == 200
    payload = parse_result(response)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


def test_tool_success_returns_payload_even_when_success_audit_fails(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(plan="pro"), episode_store)

    async def fake_audit_with_error(*_args, **kwargs) -> None:
        if kwargs.get("action") == "tools/call" and kwargs.get("status") == "ok":
            raise RuntimeError("audit insert failed on success path")
        return None

    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit_with_error)

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")
        response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "timeline-ok-1",
                "method": "tools/call",
                "params": {"name": "viberecall_timeline", "arguments": {"limit": 20}},
            },
        )

    teardown_app()
    assert response.status_code == 200
    payload = parse_result(response)
    assert payload["ok"] is True
    assert payload["result"]["episodes"] == []


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "tool_call_latency_ms" in response.text


def test_upstream_bridge_mode_routes_search_facts_timeline(monkeypatch) -> None:
    episode_store = {}
    setup_app(monkeypatch, make_token(), episode_store)
    monkeypatch.setattr(tool_handlers.settings, "memory_backend", "graphiti")
    monkeypatch.setattr(tool_handlers.settings, "graphiti_mcp_bridge_mode", "upstream_bridge")
    monkeypatch.setattr(tool_handlers.settings, "graphiti_api_key", "test-key")

    async def fake_graph_dependency_failure_detail() -> str | None:
        return None

    class FakeBridge:
        async def search_facts(self, *_args, **_kwargs):
            return [
                {
                    "kind": "fact",
                    "fact": {
                        "id": "fact_bridge_1",
                        "text": "Bridge fact result",
                        "valid_at": "2026-03-02T10:00:00Z",
                        "invalid_at": None,
                    },
                    "entities": [{"id": "ent_bridge_1", "type": "Entity", "name": "BridgeEntity"}],
                    "provenance": {
                        "episode_ids": ["ep_bridge_1"],
                        "reference_time": "2026-03-02T10:00:00Z",
                        "ingested_at": "2026-03-02T10:01:00Z",
                    },
                    "score": 0.88,
                }
            ]

        async def list_facts(self, *_args, **_kwargs):
            return [
                {
                    "id": "fact_bridge_1",
                    "text": "Bridge fact result",
                    "valid_at": "2026-03-02T10:00:00Z",
                    "invalid_at": None,
                    "entities": [{"id": "ent_bridge_1", "type": "Entity", "name": "BridgeEntity"}],
                    "provenance": {"episode_ids": ["ep_bridge_1"]},
                    "ingested_at": "2026-03-02T10:01:00Z",
                }
            ]

        async def list_timeline(self, *_args, **_kwargs):
            return [
                {
                    "episode_id": "ep_bridge_1",
                    "reference_time": "2026-03-02T10:00:00Z",
                    "ingested_at": "2026-03-02T10:01:00Z",
                    "summary": "Bridge timeline episode",
                    "metadata": {"source": "text", "source_description": "bridge"},
                }
            ]

    monkeypatch.setattr(tool_handlers, "get_graphiti_upstream_bridge", lambda: FakeBridge())
    monkeypatch.setattr(
        tool_handlers,
        "get_graph_dependency_failure_detail",
        fake_graph_dependency_failure_detail,
    )

    with TestClient(create_app()) as client:
        session_id = initialize_session(client, "proj_test")

        search_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "bridge-search",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_search",
                    "arguments": {"query": "bridge", "limit": 10},
                },
            },
        )
        search_payload = parse_result(search_response)
        assert search_payload["ok"] is True
        assert search_payload["result"]["results"][0]["fact"]["id"] == "fact_bridge_1"

        facts_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "bridge-facts",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_get_facts",
                    "arguments": {"limit": 10},
                },
            },
        )
        facts_payload = parse_result(facts_response)
        assert facts_payload["ok"] is True
        assert facts_payload["result"]["facts"][0]["id"] == "fact_bridge_1"

        timeline_response = client.post(
            "/p/proj_test/mcp",
            headers=mcp_headers(session_id),
            json={
                "jsonrpc": "2.0",
                "id": "bridge-timeline",
                "method": "tools/call",
                "params": {
                    "name": "viberecall_timeline",
                    "arguments": {"limit": 10},
                },
            },
        )
        timeline_payload = parse_result(timeline_response)
        assert timeline_payload["ok"] is True
        assert timeline_payload["result"]["episodes"][0]["episode_id"] == "ep_bridge_1"

    teardown_app()
