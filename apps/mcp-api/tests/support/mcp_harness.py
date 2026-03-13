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


def _salience_rank_for_test(value: str | None) -> int:
    normalized = str(value or "WARM").upper()
    if normalized == "PINNED":
        return 5
    if normalized == "HOT":
        return 4
    if normalized == "WARM":
        return 3
    if normalized == "COLD":
        return 2
    if normalized == "ARCHIVED":
        return 1
    return 0


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
    relevant_entities = list(entity_result.get("entities") or [])
    relevant_symbols = [item for item in relevant_entities if item.get("type") == "Symbol"][:limit]
    related_modules = [item for item in relevant_entities if item.get("type") == "Module"][:limit]
    related_files = [item for item in relevant_entities if item.get("type") == "File"][:limit]
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
    summary = snapshot.get("stats") or {}
    top_modules = list(architecture.get("top_modules") or [])
    top_files = list(architecture.get("top_files") or [])
    module_names = ", ".join(str(item.get("module") or "") for item in top_modules[:3] if item.get("module"))
    file_names = ", ".join(str(item.get("file_path") or "") for item in top_files[:3] if item.get("file_path"))
    related_module_names = ", ".join(str(item.get("name") or "") for item in related_modules[:3] if item.get("name"))
    related_file_names = ", ".join(
        str(item.get("file_path") or item.get("name") or "") for item in related_files[:3] if item.get("name")
    )
    overview_parts = [
        (
            f"Snapshot covers {int(summary.get('file_count') or 0)} files, "
            f"{int(summary.get('symbol_count') or 0)} symbols, "
            f"{int(summary.get('entity_count') or 0)} entities, and "
            f"{int(summary.get('relationship_count') or 0)} relationships."
        )
    ]
    if module_names:
        overview_parts.append(f"Top modules: {module_names}.")
    if file_names:
        overview_parts.append(f"Top files: {file_names}.")
    if related_module_names:
        overview_parts.append(f"Query-matched modules: {related_module_names}.")
    if related_file_names:
        overview_parts.append(f"Query-matched files: {related_file_names}.")
    return {
        "status": "READY",
        "context_mode": "code_augmented",
        "index_status": "READY",
        "index_hint": None,
        "query": query,
        "architecture_overview": " ".join(overview_parts),
        "architecture_map": {
            "indexed_at": run.get("completed_at"),
            "repo_path": run.get("repo_path"),
            "summary": summary,
            "top_modules": top_modules,
            "top_files": top_files,
        },
        "relevant_symbols": relevant_symbols,
        "related_modules": related_modules,
        "related_files": related_files,
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


def _install_fake_operation_backend(
    monkeypatch,
    *,
    episode_store: dict,
    index_store: dict,
    queue_getter,
    queue_mode: str,
) -> dict[str, dict]:
    operation_store: dict[str, dict] = {}
    outbox_store: dict[str, list[dict]] = {}

    async def fake_create_operation(
        session,
        *,
        operation_id: str,
        project_id: str,
        token_id: str | None,
        request_id: str,
        kind: str,
        status: str = "PENDING",
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        _ = session
        timestamp = _now_iso()
        operation_store[operation_id] = {
            "operation_id": operation_id,
            "project_id": project_id,
            "token_id": token_id,
            "request_id": request_id,
            "kind": kind,
            "status": status,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "job_id": None,
            "metadata_json": deepcopy(metadata) if metadata is not None else None,
            "result_json": None,
            "error_json": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "completed_at": None,
        }

    async def fake_create_outbox_event(
        session,
        *,
        event_id: str,
        operation_id: str,
        project_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        _ = session
        outbox_store.setdefault(operation_id, []).append(
            {
                "event_id": event_id,
                "operation_id": operation_id,
                "project_id": project_id,
                "event_type": event_type,
                "payload_json": deepcopy(payload),
                "status": "PENDING",
                "attempts": 0,
            }
        )

    async def fake_get_operation_record(session, *, project_id: str, operation_id: str) -> dict | None:
        _ = session
        row = operation_store.get(operation_id)
        if row is None or row.get("project_id") != project_id:
            return None
        return deepcopy(row)

    async def fake_complete_operation(session, *, operation_id: str, result_payload: dict | None = None) -> None:
        _ = session
        row = operation_store[operation_id]
        timestamp = _now_iso()
        row["status"] = "SUCCEEDED"
        row["result_json"] = deepcopy(result_payload)
        row["updated_at"] = timestamp
        row["completed_at"] = timestamp

    async def fake_dispatch_outbox_events(
        session,
        *,
        operation_id: str | None = None,
        limit: int = 10,
    ) -> list[str]:
        _ = session
        queue = queue_getter()
        target_ids = [operation_id] if operation_id is not None else list(outbox_store)
        dispatched: list[str] = []
        processed = 0

        for current_operation_id in target_ids:
            events = outbox_store.get(current_operation_id, [])
            for event in events:
                if processed >= limit or event["status"] == "DISPATCHED":
                    continue

                payload = event["payload_json"]
                operation = operation_store[current_operation_id]
                timestamp = _now_iso()
                try:
                    if event["event_type"] == "save.ingest":
                        job_id = await queue.enqueue_ingest(
                            episode_id=str(payload["episode_id"]),
                            project_id=str(event["project_id"]),
                            request_id=str(payload["request_id"]),
                            token_id=payload.get("token_id"),
                            operation_id=current_operation_id,
                        )
                        episode_store[str(payload["episode_id"])]["job_id"] = job_id
                        operation["job_id"] = job_id
                        if queue_mode == "eager":
                            operation["status"] = "SUCCEEDED"
                            operation["completed_at"] = timestamp
                    elif event["event_type"] == "update_fact.apply":
                        result = await queue.enqueue_update_fact(
                            project_id=str(event["project_id"]),
                            request_id=str(payload["request_id"]),
                            token_id=payload.get("token_id"),
                            fact_id=str(payload["fact_id"]),
                            new_fact_id=str(payload["new_fact_id"]),
                            new_text=str(payload["new_text"]),
                            effective_time=str(payload["effective_time"]),
                            reason=payload.get("reason"),
                            operation_id=current_operation_id,
                        )
                        operation["job_id"] = result.job_id
                        if result.immediate_result is not None:
                            operation["status"] = "SUCCEEDED"
                            operation["result_json"] = deepcopy(result.immediate_result)
                            operation["completed_at"] = timestamp
                    elif event["event_type"] == "index_repo.run":
                        job_id = await queue.enqueue_index_repo(
                            index_id=str(payload["index_id"]),
                            project_id=str(event["project_id"]),
                            request_id=str(payload["request_id"]),
                            token_id=payload.get("token_id"),
                            operation_id=current_operation_id,
                        )
                        operation["job_id"] = job_id
                        for bucket in index_store.values():
                            run = bucket["runs"].get(str(payload["index_id"]))
                            if run is not None:
                                run["job_id"] = job_id
                                if queue_mode == "eager":
                                    operation["status"] = "SUCCEEDED"
                                    operation["result_json"] = {
                                        "status": run["status"],
                                        "project_id": run["project_id"],
                                        "index_id": run["index_id"],
                                        "scanned_files": run["scanned_files"],
                                        "changed_files": run["changed_files"],
                                    }
                                    operation["completed_at"] = timestamp
                                break
                    elif event["event_type"] == "entity_resolution.search_reproject":
                        operation["status"] = "RUNNING"
                    elif event["event_type"] == "entity_resolution.graph_reproject":
                        operation["status"] = "SUCCEEDED"
                        operation["result_json"] = deepcopy(payload.get("result_payload"))
                        operation["completed_at"] = timestamp
                    else:
                        raise AssertionError(f"Unknown event type: {event['event_type']}")

                    operation["updated_at"] = timestamp
                    event["status"] = "DISPATCHED"
                    event["attempts"] += 1
                    dispatched.append(str(event["event_id"]))
                    processed += 1
                except Exception as exc:
                    event["status"] = "FAILED"
                    event["attempts"] += 1
                    operation["status"] = "FAILED_TERMINAL"
                    operation["error_json"] = {"code": "DISPATCH_FAILED", "message": str(exc)}
                    operation["updated_at"] = timestamp
                    operation["completed_at"] = timestamp
                    if event["event_type"] == "index_repo.run":
                        for bucket in index_store.values():
                            run = bucket["runs"].get(str(payload["index_id"]))
                            if run is not None:
                                run.update(
                                    {
                                        "status": "FAILED",
                                        "phase": "failed",
                                        "error": str(exc),
                                        "completed_at": timestamp,
                                    }
                                )
                                break
                    raise

        return dispatched

    monkeypatch.setattr(tool_handlers, "create_operation", fake_create_operation)
    monkeypatch.setattr(tool_handlers, "create_outbox_event", fake_create_outbox_event)
    monkeypatch.setattr(tool_handlers, "get_operation_record", fake_get_operation_record)
    monkeypatch.setattr(tool_handlers, "complete_operation", fake_complete_operation)
    monkeypatch.setattr(tool_handlers, "dispatch_outbox_events", fake_dispatch_outbox_events)
    return operation_store


def install_fake_index_backend(monkeypatch, index_store: dict) -> None:
    async def fake_request_index_repo(
        *,
        session,
        project_id: str,
        repo_source: dict,
        mode: str,
        max_files: int,
        requested_by_token_id: str | None,
        commit: bool = True,
    ) -> dict:
        _ = (session, commit)
        normalized_mode = code_index._normalize_full_snapshot_mode(mode)
        normalized_source = code_index.normalize_repo_source(repo_source)
        if normalized_source["type"] == "workspace_bundle":
            raise AssertionError("workspace_bundle path should be tested with the real route, not fake index backend")
        local_repo_path = str(normalized_source.get("repo_name") or "").strip()
        if not local_repo_path:
            raise AssertionError("fake git index backend requires repo_name to carry a local repo path")
        repo_root = code_index._resolve_repo_path(local_repo_path)
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
            "repo_source_type": normalized_source["type"],
            "repo_source_ref": normalized_source["repo_source_ref"],
            "source_ref_value": normalized_source.get("ref"),
            "repo_name": normalized_source.get("repo_name"),
            "base_commit": normalized_source.get("base_commit"),
            "credential_ref": normalized_source.get("credential_ref"),
            "mode": "snapshot",
            "effective_mode": None,
            "base_ref": None,
            "head_ref": None,
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
            "index_run_id": index_id,
            "index_id": index_id,
            "project_id": project_id,
            "repo_source": code_index._repo_source_payload(bucket["runs"][index_id]),
            "mode": normalized_mode,
            "max_files": max_files,
            "queued_at": queued_at,
        }

    async def fake_attach_index_job_id(*, session, index_id: str, job_id: str, commit: bool = True) -> None:
        _ = (session, commit)
        for bucket in index_store.values():
            if index_id in bucket["runs"]:
                bucket["runs"][index_id]["job_id"] = job_id
                return
        raise AssertionError(f"Unknown index run: {index_id}")

    async def fake_mark_index_request_failed(*, session, index_id: str, error: str, commit: bool = True) -> None:
        _ = (session, commit)
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

    async def fake_index_status(*, session, project_id: str, index_run_id: str | None = None) -> dict:
        _ = session
        ready_run, _snapshot = _latest_ready(index_store, project_id)
        if index_run_id is not None:
            requested = _bucket_for(index_store, project_id)["runs"].get(index_run_id)
            if requested is None:
                raise ValueError("Index run not found")
            return {
                "status": requested["status"],
                "project_id": project_id,
                "current_run": code_index._current_run_payload(requested),
                "latest_ready_snapshot": code_index._latest_ready_payload(ready_run),
                "stats": code_index._stats_payload(requested if requested["status"] == "READY" else ready_run),
            }
        latest = _latest_run(index_store, project_id)
        if latest is None and ready_run is None:
            return {
                "status": "EMPTY",
                "project_id": project_id,
                "current_run": None,
                "latest_ready_snapshot": None,
                "stats": code_index._stats_payload(None),
            }
        if latest is not None and latest["status"] in {"QUEUED", "RUNNING", "FAILED"}:
            return {
                "status": latest["status"],
                "project_id": project_id,
                "current_run": code_index._current_run_payload(latest),
                "latest_ready_snapshot": code_index._latest_ready_payload(ready_run),
                "stats": code_index._stats_payload(ready_run or latest),
            }
        return {
            "status": "READY",
            "project_id": project_id,
            "current_run": None,
            "latest_ready_snapshot": code_index._latest_ready_payload(ready_run or latest),
            "stats": code_index._stats_payload(ready_run or latest),
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
                "context_mode": "empty",
                "index_status": "MISSING",
                "index_hint": None,
                "query": query,
                "architecture_overview": None,
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
                "related_modules": [],
                "related_files": [],
                "citations": [],
            }
        return _build_context_from_snapshot(ready_run, snapshot, query=query, limit=limit)

    monkeypatch.setattr(tool_handlers, "request_index_repo", fake_request_index_repo)
    monkeypatch.setattr(tool_handlers, "attach_index_job_id", fake_attach_index_job_id, raising=False)
    monkeypatch.setattr(tool_handlers, "mark_index_request_failed", fake_mark_index_request_failed, raising=False)
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
        scopes=(
            scopes
            if scopes is not None
            else [
                "memory:read",
                "memory:write",
                "facts:write",
                "entities:read",
                "graph:read",
                "index:read",
                "index:run",
                "ops:read",
                "delete:write",
            ]
        ),
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
    working_memory_store: dict[tuple[str, str, str], dict] = {}
    canonical_store: dict[str, dict] = {
        "groups": {},
        "versions": {},
        "search_docs": [],
        "entity_salience": {},
        "entities": {},
        "redirects": {},
        "resolution_events": {},
        "unresolved_mentions": {},
    }
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
        commit: bool = True,
    ) -> None:
        _ = (session, commit)
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
            "salience_score": 0.5,
            "salience_class": "WARM",
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
                "salience_score": episode.get("salience_score", 0.5),
                "salience_class": episode.get("salience_class", "WARM"),
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
                    "salience_score": episode.get("salience_score", 0.5),
                    "salience_class": episode.get("salience_class", "WARM"),
                }
            )
        rows.sort(key=lambda row: (row["ingested_at"], row["episode_id"]), reverse=True)
        return rows[offset : offset + limit]

    async def fake_set_episode_job_id(session, *, episode_id: str, job_id: str, commit: bool = True) -> None:
        _ = (session, commit)
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

    async def fake_delete_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
    ) -> dict:
        _ = (session, project_id)
        fact_group_ids = []
        fact_version_ids = []
        for fact_group_id, group in list(canonical_store["groups"].items()):
            lineage = list(group.get("lineage") or [])
            versions = [canonical_store["versions"].get(version_id) for version_id in lineage]
            versions = [version for version in versions if version is not None]
            if not any(version.get("created_from_episode_id") == episode_id for version in versions):
                continue
            fact_group_ids.append(fact_group_id)
            fact_version_ids.extend(lineage)
            canonical_store["groups"].pop(fact_group_id, None)
            for version_id in lineage:
                canonical_store["versions"].pop(version_id, None)

        canonical_store["search_docs"] = [
            item
            for item in canonical_store["search_docs"]
            if episode_id not in json.dumps(item, sort_keys=True)
            and all(version_id not in json.dumps(item, sort_keys=True) for version_id in fact_version_ids)
        ]
        return {
            "fact_group_ids": fact_group_ids,
            "fact_version_ids": fact_version_ids,
            "fact_groups_deleted": len(fact_group_ids),
            "fact_versions_deleted": len(fact_version_ids),
            "provenance_deleted": len(fact_group_ids) + len(fact_version_ids),
            "search_docs_deleted": 0,
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

    async def fake_get_working_memory(session, *, project_id: str, task_id: str, session_id: str) -> dict | None:
        _ = session
        row = working_memory_store.get((project_id, task_id, session_id))
        return deepcopy(row) if row is not None else None

    async def fake_patch_working_memory(
        session,
        *,
        project_id: str,
        task_id: str,
        session_id: str,
        patch: dict,
        checkpoint_note: str | None = None,
        expires_at: str | None = None,
        commit: bool = True,
    ) -> dict:
        _ = (session, commit)
        key = (project_id, task_id, session_id)
        current = deepcopy(working_memory_store.get(key) or {})
        state = current.get("state") or {}

        def merge(base: dict, incoming: dict) -> dict:
            merged = dict(base)
            for merge_key, merge_value in incoming.items():
                if isinstance(merged.get(merge_key), dict) and isinstance(merge_value, dict):
                    merged[merge_key] = merge(merged[merge_key], merge_value)
                else:
                    merged[merge_key] = merge_value
            return merged

        timestamp = _now_iso()
        row = {
            "project_id": project_id,
            "task_id": task_id,
            "session_id": session_id,
            "state": merge(state, patch),
            "checkpoint_note": checkpoint_note if checkpoint_note is not None else current.get("checkpoint_note"),
            "created_at": current.get("created_at") or timestamp,
            "updated_at": timestamp,
            "expires_at": expires_at if expires_at is not None else current.get("expires_at"),
        }
        working_memory_store[key] = deepcopy(row)
        return row

    async def fake_save_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
        content: str,
        reference_time: str | None,
        metadata: dict | None,
    ):
        _ = (session, project_id, episode_id, content, reference_time, metadata)
        return SimpleNamespace(
            observation_doc_id="doc_celery",
            fact_group_id="factgrp_celery",
            fact_version_id="factv_celery",
            entities=[],
        )

    async def fake_search_canonical_memory(
        session,
        *,
        project_id: str,
        query: str,
        filters: dict | None,
        sort: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        _ = (session, project_id, query, filters, sort, limit, offset)
        return []

    async def fake_list_canonical_facts(session, *, project_id: str, filters: dict | None, limit: int, offset: int) -> list[dict]:
        _ = (session, project_id, filters, limit, offset)
        return []

    async def fake_get_current_fact_by_version_or_group(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id, fact_group_id)
        return None

    async def fake_get_canonical_fact(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id, fact_group_id)
        return None

    async def fake_update_canonical_fact(
        session,
        *,
        project_id: str,
        fact_group_id: str,
        expected_current_version_id: str,
        statement: str,
        effective_time: str,
        reason: str | None,
        metadata: dict | None = None,
    ) -> dict:
        _ = (session, project_id, fact_group_id, expected_current_version_id, statement, effective_time, reason, metadata)
        raise AssertionError("canonical fact update should not be used in celery transport tests")

    async def fake_pin_canonical_memory(
        session,
        *,
        project_id: str,
        target_kind: str,
        target_id: str,
        pin_action: str,
        reason: str | None,
    ) -> dict | None:
        _ = (session, project_id, target_kind, target_id, pin_action, reason)
        return None

    async def fake_delete_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
    ) -> dict:
        _ = (session, project_id, episode_id)
        return {
            "fact_group_ids": [],
            "fact_version_ids": [],
            "fact_groups_deleted": 0,
            "fact_versions_deleted": 0,
            "provenance_deleted": 0,
            "search_docs_deleted": 0,
        }

    async def fake_search_canonical_entities(
        session,
        *,
        project_id: str,
        query: str,
        entity_kinds: list[str] | None,
        salience_classes: list[str] | None,
        limit: int,
    ) -> dict:
        _ = (session, project_id, query, entity_kinds, salience_classes, limit)
        return {"status": "READY", "query": query, "entities": [], "total": 0}

    async def fake_resolve_reference(
        session,
        *,
        project_id: str,
        mention_text: str,
        observed_kind: str | None,
        repo_scope: str | None,
        include_code_index: bool,
        limit: int,
    ) -> dict:
        _ = (session, project_id, mention_text, observed_kind, repo_scope, include_code_index, limit)
        return {
            "status": "NO_MATCH",
            "best_match": None,
            "candidates": [],
            "needs_disambiguation": False,
            "latest_ready_index": None,
            "unresolved_mention": None,
        }

    async def fake_merge_canonical_entities(
        session,
        *,
        project_id: str,
        operation_id: str | None,
        resolution_event_id: str,
        target_entity_id: str,
        source_entity_ids: list[str],
        reason: str | None,
    ) -> dict:
        _ = (session, project_id, operation_id, resolution_event_id, target_entity_id, source_entity_ids, reason)
        return {
            "resolution_event_id": resolution_event_id,
            "canonical_target_entity_id": target_entity_id,
            "redirected_entity_ids": list(source_entity_ids),
        }

    async def fake_split_canonical_entity(
        session,
        *,
        project_id: str,
        operation_id: str | None,
        resolution_event_id: str,
        source_entity_id: str,
        partitions: list[dict],
        reason: str | None,
    ) -> dict:
        _ = (session, project_id, operation_id, resolution_event_id, source_entity_id, partitions, reason)
        return {
            "resolution_event_id": resolution_event_id,
            "created_entity_ids": [],
            "reassigned_aliases": 0,
            "reassigned_facts": 0,
        }

    async def fake_get_canonical_neighbors(
        session,
        *,
        project_id: str,
        entity_id: str,
        direction: str,
        relation_types: list[str] | None,
        current_only: bool,
        valid_at: str | None,
        as_of_system_time: str | None,
        limit: int,
        ) -> dict | None:
        _ = (session, project_id, entity_id, direction, relation_types, current_only, valid_at, as_of_system_time, limit)
        return None

    async def fake_find_canonical_paths(
        session,
        *,
        project_id: str,
        src_entity_id: str,
        dst_entity_id: str,
        relation_types: list[str] | None,
        max_depth: int,
        current_only: bool,
        valid_at: str | None,
        as_of_system_time: str | None,
        limit_paths: int,
    ) -> dict:
        _ = (
            session,
            project_id,
            src_entity_id,
            dst_entity_id,
            relation_types,
            max_depth,
            current_only,
            valid_at,
            as_of_system_time,
            limit_paths,
        )
        return {
            "paths": [],
            "truncated": False,
            "search_metadata": {
                "src_entity_id": src_entity_id,
                "dst_entity_id": dst_entity_id,
                "max_depth_applied": max_depth,
                "limit_paths": limit_paths,
                "relation_types_applied": list(relation_types or []),
                "current_only": current_only,
                "valid_at": valid_at,
                "as_of_system_time": as_of_system_time,
                "engine": "sql_recursive",
            },
        }

    async def fake_explain_canonical_fact(
        session,
        *,
        project_id: str,
        fact_version_id: str,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id)
        return None

    async def fake_delete_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
    ) -> dict:
        _ = (session, project_id)
        fact_group_ids = []
        fact_version_ids = []
        for fact_group_id, group in list(canonical_store["groups"].items()):
            lineage = list(group.get("lineage") or [])
            versions = [canonical_store["versions"].get(version_id) for version_id in lineage]
            versions = [version for version in versions if version is not None]
            if not any(version.get("created_from_episode_id") == episode_id for version in versions):
                continue
            fact_group_ids.append(fact_group_id)
            fact_version_ids.extend(lineage)
            canonical_store["groups"].pop(fact_group_id, None)
            for version_id in lineage:
                canonical_store["versions"].pop(version_id, None)

        canonical_store["search_docs"] = [
            item
            for item in canonical_store["search_docs"]
            if episode_id not in json.dumps(item, sort_keys=True)
            and all(version_id not in json.dumps(item, sort_keys=True) for version_id in fact_version_ids)
        ]
        return {
            "fact_group_ids": fact_group_ids,
            "fact_version_ids": fact_version_ids,
            "fact_groups_deleted": len(fact_group_ids),
            "fact_versions_deleted": len(fact_version_ids),
            "provenance_deleted": len(fact_group_ids) + len(fact_version_ids),
            "search_docs_deleted": 0,
        }

    async def fake_save_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
        content: str,
        reference_time: str | None,
        metadata: dict | None,
    ):
        _ = (session, project_id, episode_id, content, reference_time, metadata)
        return SimpleNamespace(
            observation_doc_id="doc_celery",
            fact_group_id="factgrp_celery",
            fact_version_id="factv_celery",
            entities=[],
        )

    async def fake_search_canonical_memory(
        session,
        *,
        project_id: str,
        query: str,
        filters: dict | None,
        sort: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        _ = (session, project_id, query, filters, sort, limit, offset)
        return []

    async def fake_list_canonical_facts(session, *, project_id: str, filters: dict | None, limit: int, offset: int) -> list[dict]:
        _ = (session, project_id, filters, limit, offset)
        return []

    async def fake_get_current_fact_by_version_or_group(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id, fact_group_id)
        return None

    async def fake_get_canonical_fact(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id, fact_group_id)
        return None

    async def fake_update_canonical_fact(
        session,
        *,
        project_id: str,
        fact_group_id: str,
        expected_current_version_id: str,
        statement: str,
        effective_time: str,
        reason: str | None,
        metadata: dict | None = None,
    ) -> dict:
        _ = (session, project_id, fact_group_id, expected_current_version_id, statement, effective_time, reason, metadata)
        raise AssertionError("canonical fact update should not be used in celery transport tests")

    async def fake_save_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
        content: str,
        reference_time: str | None,
        metadata: dict | None,
    ):
        _ = session
        metadata = metadata or {}
        fact_group_id = f"factgrp_{len(canonical_store['groups']) + 1}"
        fact_version_id = f"factv_{len(canonical_store['versions']) + 1}"
        observation_doc_id = f"doc_{len(canonical_store['search_docs']) + 1}"
        entities = []
        if metadata.get("repo"):
            entities.append({"entity_id": f"repo::{metadata['repo']}", "name": metadata["repo"], "type": "Repository"})
        else:
            entities.append({"entity_id": f"project::{project_id}", "name": project_id, "type": "Project"})
        for file_path in metadata.get("files") or []:
            entities.append({"entity_id": f"file::{file_path}", "name": file_path, "type": "File"})
        for tag in metadata.get("tags") or []:
            entities.append({"entity_id": f"tag::{tag}", "name": tag, "type": "Tag"})
        for entity in entities:
            salience = canonical_store["entity_salience"].get(entity["entity_id"]) or {}
            entity["salience_score"] = float(salience.get("salience_score", 0.5))
            entity["salience_class"] = str(salience.get("salience_class", "WARM"))
            canonical_store["entities"][entity["entity_id"]] = {
                "entity_id": entity["entity_id"],
                "canonical_name": str(entity["name"]).lower(),
                "display_name": entity["name"],
                "entity_kind": entity["type"],
                "aliases": [entity["name"]],
                "salience_score": entity["salience_score"],
                "salience_class": entity["salience_class"],
                "state": "ACTIVE",
                "metadata": {},
            }

        fact = {
            "fact_version_id": fact_version_id,
            "fact_group_id": fact_group_id,
            "statement": content,
            "normalized_statement": content.lower(),
            "subject_entity_id": entities[0]["entity_id"],
            "relation_type_id": "observation_captured",
            "object_entity_id": None,
            "value_json": {"metadata": metadata},
            "valid_from": reference_time,
            "valid_to": None,
            "recorded_at": _now_iso(),
            "superseded_at": None,
            "status": "CURRENT",
            "confidence": 0.75,
            "salience_score": 0.5,
            "salience_class": "WARM",
            "trust_class": "observed",
            "created_from_episode_id": episode_id,
            "replaces_fact_version_id": None,
            "metadata": metadata,
        }
        canonical_store["groups"][fact_group_id] = {
            "current_fact_version_id": fact_version_id,
            "lineage": [fact_version_id],
            "provenance": [{"source_kind": "episode", "source_id": episode_id, "role": "supports"}],
        }
        canonical_store["versions"][fact_version_id] = deepcopy(fact)
        canonical_store["search_docs"].append(
            {
                "kind": "fact",
                "fact": {
                    "id": fact_version_id,
                    "fact_version_id": fact_version_id,
                    "fact_group_id": fact_group_id,
                    "text": content,
                    "statement": content,
                    "valid_at": reference_time,
                    "invalid_at": None,
                    "salience_score": 0.5,
                    "salience_class": "WARM",
                },
                "entities": deepcopy(entities),
                "provenance": {
                    "episode_ids": [episode_id],
                    "reference_time": reference_time,
                    "ingested_at": None,
                },
                "summary": content[:160],
            }
        )
        canonical_store["search_docs"].append(
            {
                "kind": "episode",
                "episode": {
                    "episode_id": episode_id,
                    "reference_time": reference_time,
                    "summary": content[:160],
                    "metadata": metadata,
                    "salience_score": 0.5,
                    "salience_class": "WARM",
                },
            }
        )
        return SimpleNamespace(
            observation_doc_id=observation_doc_id,
            fact_group_id=fact_group_id,
            fact_version_id=fact_version_id,
            entities=entities,
        )

    async def fake_search_canonical_memory(
        session,
        *,
        project_id: str,
        query: str,
        filters: dict | None,
        sort: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        _ = (session, project_id)
        query_lower = query.lower()
        matches = []
        for item in canonical_store["search_docs"]:
            haystack = json.dumps(item, sort_keys=True).lower()
            if query_lower not in haystack:
                continue
            row = deepcopy(item)
            score = 0.9 if item["kind"] == "fact" else 0.45
            payload = row.get("fact") or row.get("episode") or {}
            exact_match = 1 if str(payload.get("text") or payload.get("statement") or payload.get("summary") or "").lower() == query_lower else 0
            row["score"] = score
            row["_exact_match_rank"] = exact_match
            row["_salience_score"] = float(payload.get("salience_score") or 0.5)
            row["_salience_rank"] = _salience_rank_for_test(payload.get("salience_class"))
            matches.append(row)
        if filters and filters.get("salience_classes"):
            allowed = {str(item).upper() for item in (filters.get("salience_classes") or [])}
            matches = [
                item
                for item in matches
                if str((item.get("fact") or item.get("episode") or {}).get("salience_class", "WARM")).upper() in allowed
            ]
        matches.sort(
            key=lambda item: (
                int(item.get("_exact_match_rank") or 0),
                float(item.get("score") or 0.0),
                int(item.get("_salience_rank") or 0),
                float(item.get("_salience_score") or 0.5),
                str((item.get("fact") or {}).get("fact_version_id") or (item.get("episode") or {}).get("episode_id") or ""),
            ),
            reverse=True,
        )
        for item in matches:
            item.pop("_exact_match_rank", None)
            item.pop("_salience_score", None)
            item.pop("_salience_rank", None)
        return matches[offset : offset + limit]

    async def fake_list_canonical_facts(session, *, project_id: str, filters: dict | None, limit: int, offset: int) -> list[dict]:
        _ = (session, project_id)
        rows = []
        for fact in canonical_store["versions"].values():
            if fact["status"] != "CURRENT" or fact["superseded_at"] is not None:
                continue
            if filters and filters.get("tag"):
                if filters["tag"] not in (fact.get("metadata") or {}).get("tags", []):
                    continue
            rows.append(deepcopy(fact))
        rows.sort(key=lambda item: (item.get("valid_from") or "", item["fact_version_id"]), reverse=True)
        return rows[offset : offset + limit]

    async def fake_get_current_fact_by_version_or_group(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id)
        if fact_version_id is not None:
            current = canonical_store["versions"].get(fact_version_id)
            if current and current["status"] == "CURRENT" and current["superseded_at"] is None:
                return deepcopy(current)
            for group in canonical_store["groups"].values():
                if group["current_fact_version_id"] == fact_version_id:
                    current = canonical_store["versions"].get(fact_version_id)
                    return deepcopy(current) if current else None
        if fact_group_id is not None:
            group = canonical_store["groups"].get(fact_group_id)
            if group is None:
                return None
            current = canonical_store["versions"].get(group["current_fact_version_id"])
            return deepcopy(current) if current else None
        return None

    async def fake_get_canonical_fact(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id)
        current = await fake_get_current_fact_by_version_or_group(
            session,
            project_id=project_id,
            fact_version_id=fact_version_id,
            fact_group_id=fact_group_id,
        )
        if current is None:
            return None
        group = canonical_store["groups"][current["fact_group_id"]]
        return {
            "current": deepcopy(current),
            "lineage": [deepcopy(canonical_store["versions"][version_id]) for version_id in reversed(group["lineage"])],
            "provenance": deepcopy(group["provenance"]),
            "related_entities": [current["subject_entity_id"], current.get("object_entity_id")],
        }

    async def fake_update_canonical_fact(
        session,
        *,
        project_id: str,
        fact_group_id: str,
        expected_current_version_id: str,
        statement: str,
        effective_time: str,
        reason: str | None,
        metadata: dict | None = None,
    ) -> dict:
        _ = (session, project_id)
        group = canonical_store["groups"][fact_group_id]
        if group["current_fact_version_id"] != expected_current_version_id:
            raise RuntimeError(json.dumps({"code": "CONFLICT", "expected_current_version_id": group["current_fact_version_id"]}))
        current = canonical_store["versions"][expected_current_version_id]
        current["status"] = "SUPERSEDED"
        current["superseded_at"] = effective_time
        new_fact_version_id = f"factv_{len(canonical_store['versions']) + 1}"
        new_fact = deepcopy(current)
        new_fact.update(
            {
                "fact_version_id": new_fact_version_id,
                "statement": statement,
                "normalized_statement": statement.lower(),
                "valid_from": effective_time,
                "valid_to": None,
                "status": "CURRENT",
                "superseded_at": None,
                "replaces_fact_version_id": expected_current_version_id,
                "metadata": {**(current.get("metadata") or {}), **(metadata or {}), **({"reason": reason} if reason else {})},
            }
        )
        canonical_store["versions"][new_fact_version_id] = new_fact
        group["current_fact_version_id"] = new_fact_version_id
        group["lineage"].append(new_fact_version_id)
        return {
            "old_fact_version_id": expected_current_version_id,
            "new_fact_version_id": new_fact_version_id,
            "fact_group_id": fact_group_id,
            "committed_at": effective_time,
            "old_fact": {"id": expected_current_version_id, "invalid_at": effective_time},
            "new_fact": {
                "id": new_fact_version_id,
                "valid_at": effective_time,
                "salience_score": new_fact["salience_score"],
                "salience_class": new_fact["salience_class"],
            },
        }

    async def fake_pin_canonical_memory(
        session,
        *,
        project_id: str,
        target_kind: str,
        target_id: str,
        pin_action: str,
        reason: str | None,
    ) -> dict | None:
        _ = (session, project_id, reason)
        normalized_target_kind = str(target_kind).upper()
        normalized_action = str(pin_action).upper()

        def apply_action(current_class: str, current_score: float) -> tuple[str, float]:
            if normalized_action == "PIN":
                return "PINNED", 1.0
            if normalized_action == "DEMOTE":
                return "COLD", 0.2
            return "WARM", 0.5 if current_score in {1.0, 0.2} else current_score

        if normalized_target_kind == "FACT":
            fact = canonical_store["versions"].get(target_id)
            if fact is None:
                for group in canonical_store["groups"].values():
                    if target_id in {group.get("current_fact_version_id"), next(iter(group.get("lineage") or []), "")}:
                        fact = canonical_store["versions"].get(group["current_fact_version_id"])
                        break
                if fact is None and target_id in canonical_store["groups"]:
                    fact = canonical_store["versions"].get(canonical_store["groups"][target_id]["current_fact_version_id"])
            if fact is None:
                return None
            next_class, next_score = apply_action(str(fact.get("salience_class") or "WARM"), float(fact.get("salience_score") or 0.5))
            fact["salience_class"] = next_class
            fact["salience_score"] = next_score
            for item in canonical_store["search_docs"]:
                fact_payload = item.get("fact")
                if fact_payload and fact_payload.get("fact_version_id") == fact["fact_version_id"]:
                    fact_payload["salience_class"] = next_class
                    fact_payload["salience_score"] = next_score
            return {
                "target_kind": "FACT",
                "target_id": target_id,
                "resolved_target": {
                    "fact_group_id": fact["fact_group_id"],
                    "fact_version_id": fact["fact_version_id"],
                },
                "pin_action": normalized_action,
                "salience_state": {
                    "salience_score": next_score,
                    "salience_class": next_class,
                    "manual_override": normalized_action != "UNPIN",
                    "reason": reason,
                    "updated_at": _now_iso(),
                },
                "updated_at": _now_iso(),
            }

        if normalized_target_kind == "EPISODE":
            for item in canonical_store["search_docs"]:
                episode_payload = item.get("episode")
                if not episode_payload or episode_payload.get("episode_id") != target_id:
                    continue
                next_class, next_score = apply_action(
                    str(episode_payload.get("salience_class") or "WARM"),
                    float(episode_payload.get("salience_score") or 0.5),
                )
                episode_payload["salience_class"] = next_class
                episode_payload["salience_score"] = next_score
                if target_id in episode_store:
                    episode_store[target_id]["salience_class"] = next_class
                    episode_store[target_id]["salience_score"] = next_score
                return {
                    "target_kind": "EPISODE",
                    "target_id": target_id,
                    "resolved_target": {"episode_id": target_id},
                    "pin_action": normalized_action,
                    "salience_state": {
                        "salience_score": next_score,
                        "salience_class": next_class,
                        "manual_override": normalized_action != "UNPIN",
                        "reason": reason,
                        "updated_at": _now_iso(),
                    },
                    "updated_at": _now_iso(),
                }
            return None

        if normalized_target_kind == "ENTITY":
            seen = False
            next_class, next_score = apply_action("WARM", 0.5)
            current = canonical_store["entity_salience"].get(target_id)
            if current is not None:
                next_class, next_score = apply_action(
                    str(current.get("salience_class") or "WARM"),
                    float(current.get("salience_score") or 0.5),
                )
            canonical_store["entity_salience"][target_id] = {
                "salience_class": next_class,
                "salience_score": next_score,
            }
            if target_id in canonical_store["entities"]:
                canonical_store["entities"][target_id]["salience_class"] = next_class
                canonical_store["entities"][target_id]["salience_score"] = next_score
            for item in canonical_store["search_docs"]:
                for entity_payload in item.get("entities") or []:
                    if entity_payload.get("entity_id") != target_id:
                        continue
                    entity_payload["salience_class"] = next_class
                    entity_payload["salience_score"] = next_score
                    seen = True
            if not seen:
                return None
            return {
                "target_kind": "ENTITY",
                "target_id": target_id,
                "resolved_target": {"entity_id": target_id},
                "pin_action": normalized_action,
                "salience_state": {
                    "salience_score": next_score,
                    "salience_class": next_class,
                    "manual_override": normalized_action != "UNPIN",
                    "reason": reason,
                    "updated_at": _now_iso(),
                },
                "updated_at": _now_iso(),
            }

        return None

    async def fake_search_canonical_entities(
        session,
        *,
        project_id: str,
        query: str,
        entity_kinds: list[str] | None,
        salience_classes: list[str] | None,
        limit: int,
    ) -> dict:
        _ = (session, project_id)
        query_lower = query.lower()
        kinds = set(entity_kinds or [])
        allowed_salience = {str(item).upper() for item in (salience_classes or [])}
        support: dict[str, list[dict]] = {}
        for fact in canonical_store["versions"].values():
            if fact.get("status") != "CURRENT" or fact.get("superseded_at") is not None:
                continue
            for entity_id in [fact.get("subject_entity_id"), fact.get("object_entity_id")]:
                if not entity_id:
                    continue
                support.setdefault(str(entity_id), []).append(deepcopy(fact))
        rows = []
        for entity_id, entity in canonical_store["entities"].items():
            if str(entity.get("state") or "ACTIVE") != "ACTIVE":
                continue
            entity_kind = entity.get("entity_kind")
            if kinds and entity_kind not in kinds:
                continue
            haystack = " ".join(
                [
                    str(entity.get("display_name") or ""),
                    str(entity.get("canonical_name") or ""),
                    str(entity_id),
                    " ".join(str(alias) for alias in (entity.get("aliases") or [])),
                    str(entity_kind or ""),
                ]
            ).lower()
            if query_lower not in haystack:
                continue
            payload = {
                "entity_id": entity_id,
                "name": entity.get("display_name") or entity_id,
                "canonical_name": entity.get("canonical_name") or str(entity.get("display_name") or entity_id).lower(),
                "display_name": entity.get("display_name") or entity_id,
                "type": entity_kind,
                "entity_kind": entity_kind,
                "aliases": list(entity.get("aliases") or []),
                "summary_snippet": None,
                "support_count": 0,
                "latest_support_time": None,
                "latest_supporting_fact": None,
                "confidence": 0.75,
                "salience": float(entity.get("salience_score") or 0.5),
                "salience_score": float(entity.get("salience_score") or 0.5),
                "salience_class": str(entity.get("salience_class") or "WARM"),
                "state": str(entity.get("state") or "ACTIVE"),
                "metadata": deepcopy(entity.get("metadata") or {}),
            }
            facts = support.get(entity_id) or []
            payload["support_count"] = len(facts)
            if facts:
                facts.sort(key=lambda item: ((item.get("valid_from") or item.get("recorded_at") or ""), item["fact_version_id"]), reverse=True)
                latest_fact = facts[0]
                payload["latest_support_time"] = latest_fact.get("valid_from") or latest_fact.get("recorded_at")
                payload["latest_supporting_fact"] = {
                    "fact_version_id": latest_fact.get("fact_version_id"),
                    "fact_group_id": latest_fact.get("fact_group_id"),
                    "statement": latest_fact.get("statement"),
                }
                payload["summary_snippet"] = latest_fact.get("statement")
            if allowed_salience and str(payload.get("salience_class") or "WARM").upper() not in allowed_salience:
                continue
            rows.append(payload)
        rows.sort(
            key=lambda item: (
                query_lower != item["name"].lower(),
                item["name"].lower().startswith(query_lower) is False,
                -(float(item.get("salience_score") or 0.5)),
                item["name"].lower(),
            )
        )
        rows = rows[:limit]
        return {
            "status": "READY",
            "query": query,
            "entities": deepcopy(rows),
            "total": len(rows),
        }

    async def fake_resolve_reference(
        session,
        *,
        project_id: str,
        mention_text: str,
        observed_kind: str | None,
        repo_scope: str | None,
        include_code_index: bool,
        limit: int,
    ) -> dict:
        _ = (session, project_id, repo_scope, include_code_index)
        normalized = mention_text.strip().lower()
        identity_key = (
            normalized,
            str(observed_kind or "").strip().lower(),
            str(repo_scope or "").strip().lower(),
        )
        candidates = []
        for entity in canonical_store["entities"].values():
            if str(entity.get("state") or "ACTIVE") != "ACTIVE":
                continue
            if observed_kind and entity.get("entity_kind") != observed_kind:
                continue
            aliases = [str(alias) for alias in (entity.get("aliases") or [])]
            haystack = [str(entity.get("canonical_name") or ""), str(entity.get("display_name") or ""), *aliases]
            if not any(normalized and normalized in str(value).lower() for value in haystack):
                continue
            candidates.append(
                {
                    "candidate_type": "canonical_entity",
                    "entity_id": entity["entity_id"],
                    "name": entity.get("display_name") or entity["entity_id"],
                    "display_name": entity.get("display_name") or entity["entity_id"],
                    "canonical_name": entity.get("canonical_name"),
                    "entity_kind": entity.get("entity_kind"),
                    "aliases": aliases,
                    "support_count": 0,
                    "salience_score": entity.get("salience_score"),
                    "salience_class": entity.get("salience_class"),
                    "score": entity.get("salience_score") or 0.5,
                    "provisional": False,
                    "match": {
                        "rank": 0 if normalized in [value.lower() for value in haystack if value] else 2,
                        "source": "alias" if normalized in [alias.lower() for alias in aliases] else "canonical_name",
                        "exact": normalized in [value.lower() for value in haystack if value],
                    },
                    "snapshot_ref": None,
                }
            )
        candidates.sort(
            key=lambda item: (
                int(item["match"]["rank"]),
                -float(item.get("score") or 0.0),
                str(item.get("display_name") or ""),
            )
        )
        candidates = candidates[:limit]
        if not candidates:
            record = canonical_store["unresolved_mentions"].get(identity_key)
            if record is None or record.get("status") != "OPEN":
                record = {
                    "mention_id": f"mention_{len(canonical_store['unresolved_mentions']) + 1}",
                    "status": "OPEN",
                    "created_at": _now_iso(),
                }
                canonical_store["unresolved_mentions"][identity_key] = record
            record["updated_at"] = _now_iso()
            return {
                "status": "NO_MATCH",
                "best_match": None,
                "candidates": [],
                "needs_disambiguation": False,
                "latest_ready_index": None,
                "unresolved_mention": {
                    "mention_id": record["mention_id"],
                    "status": record["status"],
                },
            }
        best_match = candidates[0]
        same_rank = [item for item in candidates if int(item["match"]["rank"]) == int(best_match["match"]["rank"])]
        status_value = "RESOLVED" if len(same_rank) == 1 else "AMBIGUOUS"
        unresolved_mention = None
        if status_value == "RESOLVED":
            record = canonical_store["unresolved_mentions"].get(identity_key)
            if record is not None and record.get("status") == "OPEN":
                record["status"] = "RESOLVED"
                record["updated_at"] = _now_iso()
                unresolved_mention = {
                    "mention_id": record["mention_id"],
                    "status": record["status"],
                }
        else:
            record = canonical_store["unresolved_mentions"].get(identity_key)
            if record is None or record.get("status") != "OPEN":
                record = {
                    "mention_id": f"mention_{len(canonical_store['unresolved_mentions']) + 1}",
                    "status": "OPEN",
                    "created_at": _now_iso(),
                }
                canonical_store["unresolved_mentions"][identity_key] = record
            record["updated_at"] = _now_iso()
            unresolved_mention = {
                "mention_id": record["mention_id"],
                "status": record["status"],
            }
        return {
            "status": status_value,
            "best_match": deepcopy(best_match),
            "candidates": deepcopy(candidates),
            "needs_disambiguation": status_value == "AMBIGUOUS",
            "latest_ready_index": None,
            "unresolved_mention": unresolved_mention,
        }

    async def fake_merge_canonical_entities(
        session,
        *,
        project_id: str,
        operation_id: str | None,
        resolution_event_id: str,
        target_entity_id: str,
        source_entity_ids: list[str],
        reason: str | None,
    ) -> dict:
        _ = (session, project_id, operation_id)
        if target_entity_id not in canonical_store["entities"]:
            raise KeyError(target_entity_id)
        if canonical_store["entities"][target_entity_id].get("state") != "ACTIVE":
            raise ValueError("target entity must be ACTIVE")
        redirected_ids = []
        for source_entity_id in source_entity_ids:
            entity = canonical_store["entities"].get(source_entity_id)
            if entity is None:
                raise KeyError(source_entity_id)
            if entity.get("state") != "ACTIVE":
                raise ValueError(f"source entity is not ACTIVE: {source_entity_id}")
            redirected_ids.append(source_entity_id)
            canonical_store["redirects"][source_entity_id] = {
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id,
                "resolution_event_id": resolution_event_id,
            }
            canonical_store["entities"][source_entity_id]["state"] = "REDIRECTED"
            target_aliases = canonical_store["entities"][target_entity_id].setdefault("aliases", [])
            for alias_value in canonical_store["entities"][source_entity_id].get("aliases") or []:
                if alias_value not in target_aliases:
                    target_aliases.append(alias_value)
            for alias_value in [
                canonical_store["entities"][source_entity_id].get("canonical_name"),
                canonical_store["entities"][source_entity_id].get("display_name"),
            ]:
                if alias_value and alias_value not in target_aliases:
                    target_aliases.append(alias_value)
        for fact in canonical_store["versions"].values():
            if fact.get("subject_entity_id") in redirected_ids:
                fact["subject_entity_id"] = target_entity_id
            if fact.get("object_entity_id") in redirected_ids:
                fact["object_entity_id"] = target_entity_id
        for item in canonical_store["search_docs"]:
            for entity in item.get("entities") or []:
                if entity.get("entity_id") in redirected_ids:
                    entity["entity_id"] = target_entity_id
                    entity["name"] = canonical_store["entities"][target_entity_id].get("display_name") or target_entity_id
                    entity["type"] = canonical_store["entities"][target_entity_id].get("entity_kind")
        canonical_store["resolution_events"][resolution_event_id] = {
            "event_kind": "MERGE",
            "target_entity_id": target_entity_id,
            "source_entity_ids": list(redirected_ids),
            "reason": reason,
        }
        return {
            "resolution_event_id": resolution_event_id,
            "canonical_target_entity_id": target_entity_id,
            "redirected_entity_ids": redirected_ids,
        }

    async def fake_split_canonical_entity(
        session,
        *,
        project_id: str,
        operation_id: str | None,
        resolution_event_id: str,
        source_entity_id: str,
        partitions: list[dict],
        reason: str | None,
    ) -> dict:
        _ = (session, project_id, operation_id)
        if source_entity_id not in canonical_store["entities"]:
            raise KeyError(source_entity_id)
        created_entity_ids = []
        reassigned_aliases = 0
        reassigned_facts = 0
        assigned_aliases: set[str] = set()
        assigned_facts: set[tuple[str, str]] = set()
        for partition in partitions:
            target_entity_id = partition.get("target_entity_id")
            if target_entity_id:
                if target_entity_id not in canonical_store["entities"]:
                    raise KeyError(str(target_entity_id))
            else:
                new_entity = dict(partition.get("new_entity") or {})
                target_entity_id = str(new_entity.get("entity_id") or f"ent_split_{len(canonical_store['entities']) + len(created_entity_ids) + 1}")
                canonical_store["entities"][target_entity_id] = {
                    "entity_id": target_entity_id,
                    "canonical_name": str(new_entity["canonical_name"]).lower(),
                    "display_name": str(new_entity.get("display_name") or new_entity["canonical_name"]),
                    "entity_kind": new_entity["entity_kind"],
                    "aliases": [str(new_entity.get("display_name") or new_entity["canonical_name"])],
                    "salience_score": 0.5,
                    "salience_class": "WARM",
                    "state": "ACTIVE",
                    "metadata": {},
                }
                created_entity_ids.append(target_entity_id)
            for alias_value in partition.get("alias_values") or []:
                normalized_alias = str(alias_value).strip().lower()
                if normalized_alias in assigned_aliases:
                    raise ValueError(f"duplicate alias assignment: {alias_value}")
                assigned_aliases.add(normalized_alias)
                source_aliases = canonical_store["entities"][source_entity_id].setdefault("aliases", [])
                if alias_value not in source_aliases:
                    raise ValueError(f"unknown alias_values for source entity: {[alias_value]}")
                source_aliases.remove(alias_value)
                target_aliases = canonical_store["entities"][target_entity_id].setdefault("aliases", [])
                if alias_value not in target_aliases:
                    target_aliases.append(alias_value)
                reassigned_aliases += 1
            for binding in partition.get("fact_bindings") or []:
                key = (str(binding["fact_version_id"]), str(binding["slot"]))
                if key in assigned_facts:
                    raise ValueError(f"duplicate fact binding assignment: {binding['fact_version_id']}:{binding['slot']}")
                assigned_facts.add(key)
                fact = canonical_store["versions"].get(str(binding["fact_version_id"]))
                if fact is None:
                    raise KeyError(str(binding["fact_version_id"]))
                slot = str(binding["slot"])
                if slot == "subject":
                    if fact.get("subject_entity_id") != source_entity_id:
                        raise ValueError(f"fact_version_id is not bound on subject slot: {binding['fact_version_id']}")
                    fact["subject_entity_id"] = target_entity_id
                    reassigned_facts += 1
                elif slot == "object":
                    if fact.get("object_entity_id") != source_entity_id:
                        raise ValueError(f"fact_version_id is not bound on object slot: {binding['fact_version_id']}")
                    fact["object_entity_id"] = target_entity_id
                    reassigned_facts += 1
                elif slot == "both":
                    changed = False
                    if fact.get("subject_entity_id") == source_entity_id:
                        fact["subject_entity_id"] = target_entity_id
                        reassigned_facts += 1
                        changed = True
                    if fact.get("object_entity_id") == source_entity_id:
                        fact["object_entity_id"] = target_entity_id
                        reassigned_facts += 1
                        changed = True
                    if not changed:
                        raise ValueError(f"fact_version_id is not bound to source entity: {binding['fact_version_id']}")
                else:
                    raise ValueError(f"invalid fact binding slot: {slot}")
        canonical_store["resolution_events"][resolution_event_id] = {
            "event_kind": "SPLIT",
            "source_entity_id": source_entity_id,
            "created_entity_ids": list(created_entity_ids),
            "reason": reason,
        }
        return {
            "resolution_event_id": resolution_event_id,
            "created_entity_ids": created_entity_ids,
            "reassigned_aliases": reassigned_aliases,
            "reassigned_facts": reassigned_facts,
        }

    async def fake_get_canonical_neighbors(
        session,
        *,
        project_id: str,
        entity_id: str,
        direction: str,
        relation_types: list[str] | None,
        current_only: bool,
        valid_at: str | None,
        as_of_system_time: str | None,
        limit: int,
    ) -> dict | None:
        _ = (session, project_id, current_only, valid_at, as_of_system_time)
        entity_id = canonical_store["redirects"].get(entity_id, {}).get("target_entity_id", entity_id)
        edges = []
        entity_lookup: dict[str, dict] = {}
        allowed_relations = set(relation_types or [])
        for fact in canonical_store["versions"].values():
            if fact.get("object_entity_id") is None:
                continue
            if allowed_relations and fact.get("relation_type_id") not in allowed_relations:
                continue
            if direction == "OUT" and fact.get("subject_entity_id") != entity_id:
                continue
            if direction == "IN" and fact.get("object_entity_id") != entity_id:
                continue
            if direction == "BOTH" and entity_id not in {fact.get("subject_entity_id"), fact.get("object_entity_id")}:
                continue
            if fact.get("subject_entity_id") == entity_id:
                neighbor_id = fact.get("object_entity_id")
                edge_direction = "OUT"
            elif fact.get("object_entity_id") == entity_id:
                neighbor_id = fact.get("subject_entity_id")
                edge_direction = "IN"
            else:
                continue
            entity_lookup.setdefault(
                neighbor_id,
                {
                    "entity_id": neighbor_id,
                    "name": (canonical_store["entities"].get(neighbor_id) or {}).get("display_name") or neighbor_id,
                    "canonical_name": (canonical_store["entities"].get(neighbor_id) or {}).get("canonical_name") or neighbor_id.lower(),
                    "display_name": (canonical_store["entities"].get(neighbor_id) or {}).get("display_name") or neighbor_id,
                    "type": (canonical_store["entities"].get(neighbor_id) or {}).get("entity_kind") or "Entity",
                    "entity_kind": (canonical_store["entities"].get(neighbor_id) or {}).get("entity_kind") or "Entity",
                    "aliases": list((canonical_store["entities"].get(neighbor_id) or {}).get("aliases") or []),
                    "summary_snippet": fact.get("statement"),
                    "support_count": 1,
                    "latest_support_time": fact.get("recorded_at"),
                    "latest_supporting_fact": {
                        "fact_version_id": fact.get("fact_version_id"),
                        "fact_group_id": fact.get("fact_group_id"),
                        "statement": fact.get("statement"),
                    },
                    "confidence": fact.get("confidence"),
                    "salience": fact.get("salience_score"),
                    "state": "ACTIVE",
                    "metadata": {},
                },
            )
            edges.append(
                {
                    "fact_version_id": fact.get("fact_version_id"),
                    "fact_group_id": fact.get("fact_group_id"),
                    "direction": edge_direction,
                    "subject_entity_id": fact.get("subject_entity_id"),
                    "object_entity_id": fact.get("object_entity_id"),
                    "relation_type_id": fact.get("relation_type_id"),
                    "relation_type": fact.get("relation_type_id"),
                    "inverse_relation_type": None,
                    "relation_class": "test",
                    "statement": fact.get("statement"),
                    "status": fact.get("status"),
                    "valid_from": fact.get("valid_from"),
                    "valid_to": fact.get("valid_to"),
                    "recorded_at": fact.get("recorded_at"),
                    "confidence": fact.get("confidence"),
                    "salience_score": fact.get("salience_score"),
                    "trust_class": fact.get("trust_class"),
                    "metadata": fact.get("metadata") or {},
                    "relation_metadata": {},
                    "neighbor_entity_id": neighbor_id,
                }
            )
        if entity_id not in {edge["subject_entity_id"] for edge in edges} | {edge["object_entity_id"] for edge in edges}:
            return None
        return {
            "anchor": {
                "entity_id": entity_id,
                "name": (canonical_store["entities"].get(entity_id) or {}).get("display_name") or entity_id,
                "canonical_name": (canonical_store["entities"].get(entity_id) or {}).get("canonical_name") or entity_id.lower(),
                "display_name": (canonical_store["entities"].get(entity_id) or {}).get("display_name") or entity_id,
                "type": (canonical_store["entities"].get(entity_id) or {}).get("entity_kind") or "Entity",
                "entity_kind": (canonical_store["entities"].get(entity_id) or {}).get("entity_kind") or "Entity",
                "aliases": list((canonical_store["entities"].get(entity_id) or {}).get("aliases") or []),
                "summary_snippet": None,
                "support_count": 0,
                "latest_support_time": None,
                "latest_supporting_fact": None,
                "confidence": None,
                "salience": None,
                "state": "ACTIVE",
                "metadata": {},
            },
            "neighbors": list(entity_lookup.values())[:limit],
            "edges": edges[:limit],
            "truncated": len(edges) > limit,
        }

    async def fake_find_canonical_paths(
        session,
        *,
        project_id: str,
        src_entity_id: str,
        dst_entity_id: str,
        relation_types: list[str] | None,
        max_depth: int,
        current_only: bool,
        valid_at: str | None,
        as_of_system_time: str | None,
        limit_paths: int,
    ) -> dict:
        _ = (session, project_id, current_only, valid_at, as_of_system_time)
        src_entity_id = canonical_store["redirects"].get(src_entity_id, {}).get("target_entity_id", src_entity_id)
        dst_entity_id = canonical_store["redirects"].get(dst_entity_id, {}).get("target_entity_id", dst_entity_id)

        def entity_payload(entity_id: str) -> dict:
            entity = canonical_store["entities"].get(entity_id)
            if entity is not None:
                entity_name = entity.get("display_name") or entity_id
                entity_kind = entity.get("entity_kind") or "Entity"
                return {
                    "entity_id": entity_id,
                    "name": entity_name,
                    "canonical_name": entity.get("canonical_name") or entity_name.lower(),
                    "display_name": entity_name,
                    "type": entity_kind,
                    "entity_kind": entity_kind,
                    "aliases": list(entity.get("aliases") or []),
                    "summary_snippet": None,
                    "support_count": 0,
                    "latest_support_time": None,
                    "latest_supporting_fact": None,
                    "confidence": None,
                    "salience": None,
                    "state": str(entity.get("state") or "ACTIVE"),
                    "metadata": deepcopy(entity.get("metadata") or {}),
                }
            return {
                "entity_id": entity_id,
                "name": entity_id,
                "canonical_name": entity_id.lower(),
                "display_name": entity_id,
                "type": "Entity",
                "entity_kind": "Entity",
                "aliases": [],
                "summary_snippet": None,
                "support_count": 0,
                "latest_support_time": None,
                "latest_supporting_fact": None,
                "confidence": None,
                "salience": None,
                "state": "ACTIVE",
                "metadata": {},
            }

        known_entities: set[str] = set()
        for item in canonical_store["search_docs"]:
            if item.get("kind") != "fact":
                continue
            for entity in item.get("entities") or []:
                entity_id = entity.get("entity_id")
                if entity_id:
                    known_entities.add(str(entity_id))
        fact_rows = []
        for fact in canonical_store["versions"].values():
            if fact.get("object_entity_id") is None:
                continue
            if current_only and (fact.get("status") != "CURRENT" or fact.get("superseded_at") is not None):
                continue
            if relation_types and fact.get("relation_type_id") not in set(relation_types):
                continue
            known_entities.add(str(fact.get("subject_entity_id")))
            known_entities.add(str(fact.get("object_entity_id")))
            fact_rows.append(deepcopy(fact))

        if src_entity_id not in known_entities:
            return {"missing_entity_id": src_entity_id}
        if dst_entity_id not in known_entities:
            return {"missing_entity_id": dst_entity_id}

        paths = []

        def walk(current_entity_id: str, entity_ids: list[str], fact_version_ids: list[str], steps: list[dict]) -> None:
            if len(fact_version_ids) >= max_depth:
                return
            for fact in fact_rows:
                endpoints = {fact.get("subject_entity_id"), fact.get("object_entity_id")}
                if current_entity_id not in endpoints:
                    continue
                next_entity_id = (
                    str(fact.get("object_entity_id"))
                    if fact.get("subject_entity_id") == current_entity_id
                    else str(fact.get("subject_entity_id"))
                )
                direction = "OUT" if fact.get("subject_entity_id") == current_entity_id else "IN"
                if next_entity_id in entity_ids:
                    continue
                next_entity_ids = [*entity_ids, next_entity_id]
                next_fact_ids = [*fact_version_ids, str(fact.get("fact_version_id"))]
                next_steps = [
                    *steps,
                    {
                        "step_kind": "fact",
                        "fact_version_id": fact.get("fact_version_id"),
                        "fact_group_id": fact.get("fact_group_id"),
                        "relation_type_id": fact.get("relation_type_id"),
                        "relation_type": fact.get("relation_type_id"),
                        "direction": direction,
                        "statement": fact.get("statement"),
                        "confidence": fact.get("confidence"),
                        "salience_score": fact.get("salience_score"),
                        "trust_class": fact.get("trust_class"),
                        "recorded_at": fact.get("recorded_at"),
                    },
                    {
                        "step_kind": "entity",
                        "entity_id": next_entity_id,
                        "name": entity_payload(next_entity_id)["display_name"],
                        "entity_kind": entity_payload(next_entity_id)["entity_kind"],
                    },
                ]
                if next_entity_id == dst_entity_id:
                    scores = [float(step["confidence"] or 0) for step in next_steps if step.get("step_kind") == "fact"]
                    salience_scores = [
                        float(step["salience_score"] or 0) for step in next_steps if step.get("step_kind") == "fact"
                    ]
                    newest_recorded_at = max(
                        (step.get("recorded_at") or "" for step in next_steps if step.get("step_kind") == "fact"),
                        default="",
                    )
                    paths.append(
                        {
                            "score": sum(scores) / len(scores) if scores else 0.0,
                            "avg_salience": sum(salience_scores) / len(salience_scores) if salience_scores else 0.0,
                            "newest_recorded_at": newest_recorded_at,
                            "path_signature": "|".join([*next_entity_ids, *next_fact_ids]),
                            "hop_count": len(next_fact_ids),
                            "entity_ids": next_entity_ids,
                            "fact_version_ids": next_fact_ids,
                            "steps": next_steps,
                        }
                    )
                    continue
                walk(next_entity_id, next_entity_ids, next_fact_ids, next_steps)

        walk(
            src_entity_id,
            [src_entity_id],
            [],
            [
                {
                    "step_kind": "entity",
                    "entity_id": src_entity_id,
                    "name": entity_payload(src_entity_id)["display_name"],
                    "entity_kind": entity_payload(src_entity_id)["entity_kind"],
                }
            ],
        )
        paths.sort(
            key=lambda item: (
                -float(item["score"]),
                item["hop_count"],
                -float(item["avg_salience"]),
                item["newest_recorded_at"],
                item["path_signature"],
            ),
            reverse=False,
        )
        truncated = len(paths) > limit_paths
        rows = paths[:limit_paths]
        for row in rows:
            row.pop("avg_salience", None)
            row.pop("newest_recorded_at", None)
            row.pop("path_signature", None)
        return {
            "paths": rows,
            "truncated": truncated,
            "search_metadata": {
                "src_entity_id": src_entity_id,
                "dst_entity_id": dst_entity_id,
                "max_depth_applied": max_depth,
                "limit_paths": limit_paths,
                "relation_types_applied": list(relation_types or []),
                "current_only": current_only,
                "valid_at": valid_at,
                "as_of_system_time": as_of_system_time,
                "engine": "sql_recursive",
            },
        }

    async def fake_explain_canonical_fact(
        session,
        *,
        project_id: str,
        fact_version_id: str,
    ) -> dict | None:
        _ = (session, project_id)
        fact = canonical_store["versions"].get(fact_version_id)
        if fact is None:
            return None
        group = canonical_store["groups"][fact["fact_group_id"]]
        supporting_episode_ids = []
        for item in group.get("provenance") or []:
            if item.get("source_kind") == "episode" and item.get("source_id"):
                supporting_episode_ids.append(item["source_id"])
        supporting_episodes = []
        for episode_id in supporting_episode_ids:
            episode = episode_store.get(episode_id)
            if episode is None:
                continue
            supporting_episodes.append(
                {
                    "episode_id": episode_id,
                    "reference_time": episode.get("reference_time"),
                    "ingested_at": episode.get("ingested_at"),
                    "summary": episode.get("summary") or (episode.get("content") or "")[:160],
                    "metadata": json.loads(episode.get("metadata_json") or "{}"),
                    "role": "supports",
                    "provenance_metadata": {},
                    "linked_at": episode.get("ingested_at"),
                }
            )
        lineage_versions = [deepcopy(canonical_store["versions"][version_id]) for version_id in group["lineage"]]
        return {
            "fact": {
                **deepcopy(fact),
                "subject_entity": None,
                "object_entity": None,
                "relation_type": {
                    "relation_type_id": fact.get("relation_type_id"),
                    "name": fact.get("relation_type_id"),
                    "inverse_name": None,
                    "relation_class": "test",
                    "metadata": {},
                },
            },
            "lineage": {
                "fact_group_id": fact["fact_group_id"],
                "current_fact_version_id": group["current_fact_version_id"],
                "versions": lineage_versions,
            },
            "supporting_episodes": supporting_episodes,
            "extraction_details": {
                "relation_type": {
                    "relation_type_id": fact.get("relation_type_id"),
                    "name": fact.get("relation_type_id"),
                    "inverse_name": None,
                    "relation_class": "test",
                    "metadata": {},
                },
                "provenance": deepcopy(group.get("provenance") or []),
                "created_from_episode_id": fact.get("created_from_episode_id"),
                "metadata": deepcopy(fact.get("metadata") or {}),
            },
            "confidence_breakdown": {
                "confidence": fact.get("confidence"),
                "salience_score": fact.get("salience_score"),
                "trust_class": fact.get("trust_class"),
                "status": fact.get("status"),
                "is_current": group["current_fact_version_id"] == fact_version_id,
            },
        }

    class FakeQueue:
        async def enqueue_ingest(
            self,
            *,
            episode_id: str,
            project_id: str,
            request_id: str,
            token_id: str | None,
            operation_id: str | None = None,
        ):
            _ = operation_id
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
            operation_id: str | None = None,
        ):
            _ = operation_id
            result = await get_memory_core().update_fact(
                project_id,
                fact_id=fact_id,
                new_fact_id=new_fact_id,
                new_text=new_text,
                effective_time=effective_time,
                reason=reason,
            )
            return EnqueueUpdateFactResult(job_id="job_update_test", immediate_result=result)

        async def enqueue_index_repo(
            self,
            *,
            index_id: str,
            project_id: str,
            request_id: str,
            token_id: str | None,
            operation_id: str | None = None,
        ):
            _ = (request_id, token_id, operation_id)
            job_id = f"job_index_test_{len(_bucket_for(index_store, project_id)['order'])}"
            _complete_index_run(index_store, index_id=index_id)
            return job_id

    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: FakeQueue(), raising=False)
    _install_fake_operation_backend(
        monkeypatch,
        episode_store=episode_store,
        index_store=index_store,
        queue_getter=lambda: tool_handlers.get_task_queue(),
        queue_mode="eager",
    )

    monkeypatch.setattr(mcp_transport, "open_db_session", override_session)
    monkeypatch.setattr(mcp_transport, "authenticate_bearer_token", fake_auth)
    monkeypatch.setattr(mcp_transport, "touch_token_usage", fake_touch)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit)
    monkeypatch.setattr(tool_handlers, "create_episode", fake_create_episode)
    monkeypatch.setattr(tool_handlers, "get_episode_for_project", fake_get_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_episode_for_project", fake_delete_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_canonical_episode", fake_delete_canonical_episode)
    monkeypatch.setattr(tool_handlers, "list_timeline_episodes", fake_list_timeline)
    monkeypatch.setattr(tool_handlers, "list_recent_raw_episodes", fake_recent_raw)
    monkeypatch.setattr(tool_handlers, "set_episode_job_id", fake_set_episode_job_id, raising=False)
    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(tool_handlers, "put_text", fake_put_text)
    monkeypatch.setattr(tool_handlers, "delete_object", fake_delete_object)
    monkeypatch.setattr(tool_handlers, "get_working_memory", fake_get_working_memory)
    monkeypatch.setattr(tool_handlers, "patch_working_memory", fake_patch_working_memory)
    monkeypatch.setattr(tool_handlers, "save_canonical_episode", fake_save_canonical_episode)
    monkeypatch.setattr(tool_handlers, "search_canonical_memory", fake_search_canonical_memory)
    monkeypatch.setattr(tool_handlers, "list_canonical_facts", fake_list_canonical_facts)
    monkeypatch.setattr(tool_handlers, "get_current_fact_by_version_or_group", fake_get_current_fact_by_version_or_group)
    monkeypatch.setattr(tool_handlers, "get_canonical_fact", fake_get_canonical_fact)
    monkeypatch.setattr(tool_handlers, "update_canonical_fact", fake_update_canonical_fact)
    monkeypatch.setattr(tool_handlers, "pin_canonical_memory", fake_pin_canonical_memory)
    monkeypatch.setattr(tool_handlers, "search_canonical_entities", fake_search_canonical_entities)
    monkeypatch.setattr(tool_handlers, "resolve_canonical_reference", fake_resolve_reference)
    monkeypatch.setattr(tool_handlers, "merge_canonical_entities", fake_merge_canonical_entities)
    monkeypatch.setattr(tool_handlers, "split_canonical_entity", fake_split_canonical_entity)
    monkeypatch.setattr(tool_handlers, "get_canonical_neighbors", fake_get_canonical_neighbors)
    monkeypatch.setattr(tool_handlers, "find_canonical_paths", fake_find_canonical_paths)
    monkeypatch.setattr(tool_handlers, "explain_canonical_fact", fake_explain_canonical_fact)
    return index_store


def setup_app_celery_transport(monkeypatch, token: AuthenticatedToken, episode_store: dict) -> None:
    asyncio.run(reset_runtime_state())
    monkeypatch.setattr(runtime.settings, "memory_backend", "local")
    monkeypatch.setattr(runtime.settings, "kv_backend", "local")
    monkeypatch.setattr(runtime.settings, "queue_backend", "celery")
    object_store: dict[str, str] = {}
    working_memory_store: dict[tuple[str, str, str], dict] = {}

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
        commit: bool = True,
    ) -> None:
        _ = (session, commit)
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

    async def fake_set_episode_job_id(session, *, episode_id: str, job_id: str, commit: bool = True) -> None:
        _ = (session, commit)
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

    async def fake_get_working_memory(session, *, project_id: str, task_id: str, session_id: str) -> dict | None:
        _ = session
        row = working_memory_store.get((project_id, task_id, session_id))
        return deepcopy(row) if row is not None else None

    async def fake_patch_working_memory(
        session,
        *,
        project_id: str,
        task_id: str,
        session_id: str,
        patch: dict,
        checkpoint_note: str | None = None,
        expires_at: str | None = None,
        commit: bool = True,
    ) -> dict:
        _ = (session, commit)
        timestamp = _now_iso()
        key = (project_id, task_id, session_id)
        current = deepcopy(working_memory_store.get(key) or {})
        next_state = dict(current.get("state") or {})
        next_state.update(patch)
        row = {
            "project_id": project_id,
            "task_id": task_id,
            "session_id": session_id,
            "state": next_state,
            "checkpoint_note": checkpoint_note if checkpoint_note is not None else current.get("checkpoint_note"),
            "created_at": current.get("created_at") or timestamp,
            "updated_at": timestamp,
            "expires_at": expires_at if expires_at is not None else current.get("expires_at"),
        }
        working_memory_store[key] = deepcopy(row)
        return row

    async def fake_save_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
        content: str,
        reference_time: str | None,
        metadata: dict | None,
    ):
        _ = (session, project_id, episode_id, content, reference_time, metadata)
        return SimpleNamespace(
            observation_doc_id="doc_celery",
            fact_group_id="factgrp_celery",
            fact_version_id="factv_celery",
            entities=[],
        )

    async def fake_search_canonical_memory(
        session,
        *,
        project_id: str,
        query: str,
        filters: dict | None,
        sort: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        _ = (session, project_id, query, filters, sort, limit, offset)
        return []

    async def fake_list_canonical_facts(session, *, project_id: str, filters: dict | None, limit: int, offset: int) -> list[dict]:
        _ = (session, project_id, filters, limit, offset)
        return []

    async def fake_get_current_fact_by_version_or_group(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id, fact_group_id)
        return None

    async def fake_get_canonical_fact(
        session,
        *,
        project_id: str,
        fact_version_id: str | None = None,
        fact_group_id: str | None = None,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id, fact_group_id)
        return None

    async def fake_update_canonical_fact(
        session,
        *,
        project_id: str,
        fact_group_id: str,
        expected_current_version_id: str,
        statement: str,
        effective_time: str,
        reason: str | None,
        metadata: dict | None = None,
    ) -> dict:
        _ = (session, project_id, fact_group_id, expected_current_version_id, statement, effective_time, reason, metadata)
        raise AssertionError("canonical fact update should not be used in celery transport tests")

    async def fake_pin_canonical_memory(
        session,
        *,
        project_id: str,
        target_kind: str,
        target_id: str,
        pin_action: str,
        reason: str | None,
    ) -> dict | None:
        _ = (session, project_id, target_kind, target_id, pin_action, reason)
        return None

    async def fake_delete_canonical_episode(
        session,
        *,
        project_id: str,
        episode_id: str,
    ) -> dict:
        _ = (session, project_id, episode_id)
        return {
            "fact_group_ids": [],
            "fact_version_ids": [],
            "fact_groups_deleted": 0,
            "fact_versions_deleted": 0,
            "provenance_deleted": 0,
            "search_docs_deleted": 0,
        }

    async def fake_search_canonical_entities(
        session,
        *,
        project_id: str,
        query: str,
        entity_kinds: list[str] | None,
        salience_classes: list[str] | None,
        limit: int,
    ) -> dict:
        _ = (session, project_id, query, entity_kinds, salience_classes, limit)
        return {"status": "READY", "query": query, "entities": [], "total": 0}

    async def fake_resolve_reference(
        session,
        *,
        project_id: str,
        mention_text: str,
        observed_kind: str | None,
        repo_scope: str | None,
        include_code_index: bool,
        limit: int,
    ) -> dict:
        _ = (session, project_id, mention_text, observed_kind, repo_scope, include_code_index, limit)
        return {
            "status": "NO_MATCH",
            "best_match": None,
            "candidates": [],
            "needs_disambiguation": False,
            "latest_ready_index": None,
            "unresolved_mention": None,
        }

    async def fake_merge_canonical_entities(
        session,
        *,
        project_id: str,
        operation_id: str | None,
        resolution_event_id: str,
        target_entity_id: str,
        source_entity_ids: list[str],
        reason: str | None,
    ) -> dict:
        _ = (session, project_id, operation_id, resolution_event_id, target_entity_id, source_entity_ids, reason)
        return {
            "resolution_event_id": resolution_event_id,
            "canonical_target_entity_id": target_entity_id,
            "redirected_entity_ids": list(source_entity_ids),
        }

    async def fake_split_canonical_entity(
        session,
        *,
        project_id: str,
        operation_id: str | None,
        resolution_event_id: str,
        source_entity_id: str,
        partitions: list[dict],
        reason: str | None,
    ) -> dict:
        _ = (session, project_id, operation_id, resolution_event_id, source_entity_id, partitions, reason)
        return {
            "resolution_event_id": resolution_event_id,
            "created_entity_ids": [],
            "reassigned_aliases": 0,
            "reassigned_facts": 0,
        }

    async def fake_get_canonical_neighbors(
        session,
        *,
        project_id: str,
        entity_id: str,
        direction: str,
        relation_types: list[str] | None,
        current_only: bool,
        valid_at: str | None,
        as_of_system_time: str | None,
        limit: int,
    ) -> dict | None:
        _ = (session, project_id, entity_id, direction, relation_types, current_only, valid_at, as_of_system_time, limit)
        return None

    async def fake_find_canonical_paths(
        session,
        *,
        project_id: str,
        src_entity_id: str,
        dst_entity_id: str,
        relation_types: list[str] | None,
        max_depth: int,
        current_only: bool,
        valid_at: str | None,
        as_of_system_time: str | None,
        limit_paths: int,
    ) -> dict:
        _ = (
            session,
            project_id,
            src_entity_id,
            dst_entity_id,
            relation_types,
            max_depth,
            current_only,
            valid_at,
            as_of_system_time,
            limit_paths,
        )
        return {
            "paths": [],
            "truncated": False,
            "search_metadata": {
                "src_entity_id": src_entity_id,
                "dst_entity_id": dst_entity_id,
                "max_depth_applied": max_depth,
                "limit_paths": limit_paths,
                "relation_types_applied": list(relation_types or []),
                "current_only": current_only,
                "valid_at": valid_at,
                "as_of_system_time": as_of_system_time,
                "engine": "sql_recursive",
            },
        }

    async def fake_explain_canonical_fact(
        session,
        *,
        project_id: str,
        fact_version_id: str,
    ) -> dict | None:
        _ = (session, project_id, fact_version_id)
        return None

    monkeypatch.setattr(tool_handlers, "get_task_queue", lambda: runtime.get_task_queue(), raising=False)
    _install_fake_operation_backend(
        monkeypatch,
        episode_store=episode_store,
        index_store={},
        queue_getter=lambda: tool_handlers.get_task_queue(),
        queue_mode="celery",
    )

    monkeypatch.setattr(mcp_transport, "open_db_session", override_session)
    monkeypatch.setattr(mcp_transport, "authenticate_bearer_token", fake_auth)
    monkeypatch.setattr(mcp_transport, "touch_token_usage", fake_touch)
    monkeypatch.setattr(mcp_transport, "insert_audit_log", fake_audit)
    monkeypatch.setattr(tool_handlers, "create_episode", fake_create_episode)
    monkeypatch.setattr(tool_handlers, "get_episode_for_project", fake_get_episode_for_project)
    monkeypatch.setattr(tool_handlers, "delete_episode_for_project", fake_delete_episode_for_project)
    monkeypatch.setattr(tool_handlers, "set_episode_job_id", fake_set_episode_job_id, raising=False)
    monkeypatch.setattr(tool_handlers, "get_monthly_vibe_tokens", fake_monthly_vibe_tokens)
    monkeypatch.setattr(tool_handlers, "put_text", fake_put_text)
    monkeypatch.setattr(tool_handlers, "delete_object", fake_delete_object)
    monkeypatch.setattr(tool_handlers, "get_working_memory", fake_get_working_memory)
    monkeypatch.setattr(tool_handlers, "patch_working_memory", fake_patch_working_memory)
    monkeypatch.setattr(tool_handlers, "save_canonical_episode", fake_save_canonical_episode)
    monkeypatch.setattr(tool_handlers, "search_canonical_memory", fake_search_canonical_memory)
    monkeypatch.setattr(tool_handlers, "list_canonical_facts", fake_list_canonical_facts)
    monkeypatch.setattr(tool_handlers, "get_current_fact_by_version_or_group", fake_get_current_fact_by_version_or_group)
    monkeypatch.setattr(tool_handlers, "get_canonical_fact", fake_get_canonical_fact)
    monkeypatch.setattr(tool_handlers, "update_canonical_fact", fake_update_canonical_fact)
    monkeypatch.setattr(tool_handlers, "pin_canonical_memory", fake_pin_canonical_memory)
    monkeypatch.setattr(tool_handlers, "search_canonical_entities", fake_search_canonical_entities)
    monkeypatch.setattr(tool_handlers, "resolve_canonical_reference", fake_resolve_reference)
    monkeypatch.setattr(tool_handlers, "merge_canonical_entities", fake_merge_canonical_entities)
    monkeypatch.setattr(tool_handlers, "split_canonical_entity", fake_split_canonical_entity)
    monkeypatch.setattr(tool_handlers, "get_canonical_neighbors", fake_get_canonical_neighbors)
    monkeypatch.setattr(tool_handlers, "find_canonical_paths", fake_find_canonical_paths)
    monkeypatch.setattr(tool_handlers, "explain_canonical_fact", fake_explain_canonical_fact)
    monkeypatch.setattr(tool_handlers, "delete_canonical_episode", fake_delete_canonical_episode)
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
    monkeypatch.setattr(code_index.settings, "index_remote_git_enabled", True)
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
            repo_source={
                "type": "git",
                "remote_url": f"https://example.com/{project_id}.git",
                "ref": "main",
                "repo_name": str(repo_dir),
            },
            mode="FULL_SNAPSHOT",
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
