from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.code_index_shared import (
    _entity_search_text,
    _file_entity_id,
    _iso_or_none,
    _module_entity_id,
    _stats_payload,
    _tokenize,
)
from viberecall_mcp.code_index_store import (
    _chunk_candidate_rows,
    _chunk_rows_for_entity_ids,
    _current_run_payload,
    _entity_candidate_rows,
    _entity_rows_for_file_paths,
    _file_rows_for_index,
    _get_latest_index_run,
    _get_latest_ready_index_run,
    _get_project_index_run,
    _latest_ready_payload,
)


async def index_status_impl(
    *,
    session: AsyncSession,
    project_id: str,
    index_run_id: str | None = None,
) -> dict[str, Any]:
    latest_ready = await _get_latest_ready_index_run(session, project_id=project_id)
    if index_run_id is not None:
        requested = await _get_project_index_run(session, project_id=project_id, index_id=index_run_id)
        if requested is None:
            raise ValueError("Index run not found")
        return {
            "status": str(requested.get("status") or "EMPTY"),
            "project_id": project_id,
            "current_run": _current_run_payload(requested),
            "latest_ready_snapshot": _latest_ready_payload(latest_ready),
            "stats": _stats_payload(requested if str(requested.get("status")) == "READY" else latest_ready),
        }

    latest_run = await _get_latest_index_run(session, project_id=project_id)
    if latest_run is None and latest_ready is None:
        return {
            "status": "EMPTY",
            "project_id": project_id,
            "current_run": None,
            "latest_ready_snapshot": None,
            "stats": _stats_payload(None),
        }

    if latest_run is not None and str(latest_run.get("status")) in {"QUEUED", "RUNNING", "FAILED"}:
        return {
            "status": str(latest_run["status"]),
            "project_id": project_id,
            "current_run": _current_run_payload(latest_run),
            "latest_ready_snapshot": _latest_ready_payload(latest_ready),
            "stats": _stats_payload(latest_ready or latest_run),
        }

    return {
        "status": "READY",
        "project_id": project_id,
        "current_run": None,
        "latest_ready_snapshot": _latest_ready_payload(latest_ready or latest_run),
        "stats": _stats_payload(latest_ready or latest_run),
    }


def _search_entities_in_state(
    *,
    indexed_at: str | None,
    entities: list[dict[str, Any]],
    query: str,
    entity_types: list[str] | None,
    limit: int,
) -> dict[str, Any]:
    query_lower = query.strip().lower()
    query_tokens = set(_tokenize(query_lower))
    allowed_types = {item.strip() for item in (entity_types or []) if item.strip()}

    results: list[dict[str, Any]] = []
    for entity in entities:
        entity_type = str(entity.get("type") or entity.get("entity_type") or "")
        if allowed_types and entity_type not in allowed_types:
            continue
        name = str(entity.get("name") or "")
        search_text = str(
            entity.get("search_text")
            or _entity_search_text(
                entity_id=str(entity.get("entity_id") or ""),
                entity_type=entity_type,
                name=name,
                file_path=str(entity.get("file_path") or "") or None,
                kind=str(entity.get("kind") or "") or None,
            )
        )
        search_tokens = set(entity.get("search_tokens") or _tokenize(search_text))
        if query_lower not in search_text and not query_tokens.intersection(search_tokens):
            continue

        score = 0.3
        if query_lower and query_lower in name.lower():
            score += 0.5
        if query_lower and query_lower in entity_type.lower():
            score += 0.2
        if query_tokens:
            overlap = len(query_tokens.intersection(search_tokens))
            if overlap:
                score += min(0.4, overlap / max(1, len(query_tokens)) * 0.4)

        results.append(
            {
                "entity_id": entity.get("entity_id"),
                "type": entity_type,
                "name": name,
                "file_path": entity.get("file_path"),
                "language": entity.get("language"),
                "kind": entity.get("kind"),
                "line_start": entity.get("line_start"),
                "line_end": entity.get("line_end"),
                "score": round(float(min(score, 1.0)), 4),
            }
        )

    results.sort(
        key=lambda item: (item["score"], str(item.get("type") or ""), str(item.get("name") or "")),
        reverse=True,
    )
    return {
        "status": "READY",
        "entities": results[:limit],
        "total": len(results),
        "indexed_at": indexed_at,
    }


async def search_entities_impl(
    *,
    session: AsyncSession,
    project_id: str,
    query: str,
    entity_types: list[str] | None,
    limit: int,
) -> dict[str, Any]:
    ready_run = await _get_latest_ready_index_run(session, project_id=project_id)
    if ready_run is None:
        return {"entities": [], "total": 0, "status": "EMPTY"}

    entity_rows = await _entity_candidate_rows(
        session,
        index_id=str(ready_run["index_id"]),
        query_lower=query.strip().lower(),
        entity_types=entity_types,
    )
    return _search_entities_in_state(
        indexed_at=_iso_or_none(ready_run.get("completed_at")),
        entities=[
            {
                "entity_id": row.get("entity_id"),
                "type": row.get("entity_type"),
                "name": row.get("name"),
                "file_path": row.get("file_path"),
                "language": row.get("language"),
                "kind": row.get("kind"),
                "line_start": row.get("line_start"),
                "line_end": row.get("line_end"),
                "search_text": row.get("search_text"),
                "search_tokens": list(row.get("search_tokens") or []),
            }
            for row in entity_rows
        ],
        query=query,
        entity_types=entity_types,
        limit=limit,
    )


def _chunk_score(query_tokens: set[str], chunk: dict[str, Any], boosted_entity_ids: set[str]) -> float:
    tokens = set(chunk.get("tokens") or [])
    if not tokens:
        return 0.0
    overlap = len(query_tokens.intersection(tokens))
    base = overlap / max(1, len(query_tokens))
    if str(chunk.get("entity_id") or "") in boosted_entity_ids:
        base += 0.25
    return min(base, 1.0)


async def build_context_pack_impl(
    *,
    session: AsyncSession,
    project_id: str,
    query: str,
    limit: int,
) -> dict[str, Any]:
    ready_run = await _get_latest_ready_index_run(session, project_id=project_id)
    if ready_run is None:
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

    query_lower = query.strip().lower()
    query_tokens = set(_tokenize(query_lower))

    entity_rows = await _entity_candidate_rows(
        session,
        index_id=str(ready_run["index_id"]),
        query_lower=query_lower,
        entity_types=["Symbol", "File", "Module"],
    )
    entity_result = _search_entities_in_state(
        indexed_at=_iso_or_none(ready_run.get("completed_at")),
        entities=[
            {
                "entity_id": row.get("entity_id"),
                "type": row.get("entity_type"),
                "name": row.get("name"),
                "file_path": row.get("file_path"),
                "language": row.get("language"),
                "kind": row.get("kind"),
                "line_start": row.get("line_start"),
                "line_end": row.get("line_end"),
                "search_text": row.get("search_text"),
                "search_tokens": list(row.get("search_tokens") or []),
            }
            for row in entity_rows
        ],
        query=query,
        entity_types=["Symbol", "File", "Module"],
        limit=max(limit * 3, 25),
    )
    boosted_entity_ids = {str(item.get("entity_id") or "") for item in entity_result.get("entities", [])}

    chunk_rows = await _chunk_candidate_rows(
        session,
        index_id=str(ready_run["index_id"]),
        query_tokens=query_tokens,
        boosted_entity_ids=boosted_entity_ids,
    )
    ranked_chunks: list[dict[str, Any]] = []
    for chunk in chunk_rows:
        score = _chunk_score(query_tokens, chunk, boosted_entity_ids)
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

    return {
        "status": "READY",
        "query": query,
        "architecture_map": {
            "indexed_at": _iso_or_none(ready_run.get("completed_at")),
            "repo_path": ready_run.get("repo_path"),
            "summary": _stats_payload(ready_run),
            "top_modules": list(ready_run.get("top_modules_json") or []),
            "top_files": list(ready_run.get("top_files_json") or []),
        },
        "relevant_symbols": relevant_symbols,
        "citations": citations,
        "gaps": [] if citations else ["No high-scoring code citations for this query."],
    }


def _module_entity_id_from_name(module_name: str) -> str:
    return _module_entity_id(module_name)


async def build_code_topology_graph_impl(
    *,
    session: AsyncSession,
    project_id: str,
    query: str | None,
    max_nodes: int,
    max_edges: int,
) -> dict[str, Any]:
    ready_run = await _get_latest_ready_index_run(session, project_id=project_id)
    now = datetime.now(timezone.utc)
    if ready_run is None:
        return {
            "generated_at": now.isoformat(),
            "mode": "code",
            "empty_reason": "no_ready_index",
            "available_modes": ["concepts", "code"],
            "node_primary_label": "Symbols",
            "node_secondary_label": "Files",
            "edge_support_label": "Importing files",
            "entity_count": 0,
            "relationship_count": 0,
            "truncated": False,
            "nodes": [],
            "edges": [],
        }

    file_rows = await _file_rows_for_index(session, index_id=str(ready_run["index_id"]))
    if not file_rows:
        return {
            "generated_at": now.isoformat(),
            "mode": "code",
            "empty_reason": "no_graph_data",
            "available_modes": ["concepts", "code"],
            "node_primary_label": "Symbols",
            "node_secondary_label": "Files",
            "edge_support_label": "Importing files",
            "entity_count": 0,
            "relationship_count": 0,
            "truncated": False,
            "nodes": [],
            "edges": [],
        }

    module_stats: dict[str, dict[str, Any]] = {}
    pending_imports: list[tuple[str, str]] = []

    for row in file_rows:
        file_path = str(row.get("file_path") or "")
        module_name = str(row.get("module_name") or "")
        row_json = row.get("row_json") or {}
        if not file_path or not module_name:
            continue
        module = module_stats.setdefault(
            module_name,
            {
                "entity_id": _module_entity_id_from_name(module_name),
                "type": "Module",
                "name": module_name,
                "fact_count": 0,
                "episode_count": 0,
                "reference_time": _iso_or_none(ready_run.get("completed_at")),
                "hover_text": [],
                "file_paths": set(),
            },
        )
        symbols = row_json.get("symbols") or []
        imports = row_json.get("imports") or []
        module["fact_count"] += len(symbols)
        module["episode_count"] += 1
        module["file_paths"].add(file_path)
        if len(module["hover_text"]) < 3:
            module["hover_text"].append({"text": file_path, "reference_time": _iso_or_none(ready_run.get("completed_at"))})
        for import_name in imports:
            import_module = str(import_name or "").strip()
            if import_module:
                pending_imports.append((module_name, import_module))

    known_modules = set(module_stats.keys())
    edge_weights: Counter[tuple[str, str]] = Counter()
    neighbors: dict[str, set[str]] = defaultdict(set)
    for source_module, target_module in pending_imports:
        if target_module not in known_modules or source_module == target_module:
            continue
        key = (source_module, target_module)
        edge_weights[key] += 1
        neighbors[_module_entity_id_from_name(source_module)].add(_module_entity_id_from_name(target_module))
        neighbors[_module_entity_id_from_name(target_module)].add(_module_entity_id_from_name(source_module))

    normalized_query = (query or "").strip().lower()
    selected_ids = {str(module["entity_id"]) for module in module_stats.values()}
    if normalized_query:
        direct_matches = {
            str(module["entity_id"])
            for module in module_stats.values()
            if normalized_query in str(module["name"]).lower() or normalized_query in str(module["entity_id"]).lower()
        }
        contextual_matches = set(direct_matches)
        for entity_id in direct_matches:
            contextual_matches.update(neighbors.get(entity_id, set()))
        selected_ids &= contextual_matches

    truncated_nodes = False
    if len(selected_ids) > max_nodes:
        ordered_ids = sorted(
            selected_ids,
            key=lambda entity_id: (
                int(next(module["fact_count"] for module in module_stats.values() if module["entity_id"] == entity_id)),
                int(next(module["episode_count"] for module in module_stats.values() if module["entity_id"] == entity_id)),
                entity_id,
            ),
            reverse=True,
        )
        selected_ids = set(ordered_ids[:max_nodes])
        truncated_nodes = True

    edge_rows: list[dict[str, Any]] = []
    for (source_module, target_module), weight in edge_weights.items():
        source_id = _module_entity_id_from_name(source_module)
        target_id = _module_entity_id_from_name(target_module)
        if source_id not in selected_ids or target_id not in selected_ids:
            continue
        edge_rows.append(
            {
                "edge_id": f"edge:{source_id}:{target_id}",
                "type": "IMPORTS",
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "weight": int(weight),
                "episode_count": int(weight),
                "label": f"Imported by {int(weight)} file{'s' if int(weight) != 1 else ''}",
            }
        )

    edge_rows.sort(key=lambda row: (row["weight"], row["source_entity_id"], row["target_entity_id"]), reverse=True)
    truncated_edges = False
    if len(edge_rows) > max_edges:
        edge_rows = edge_rows[:max_edges]
        truncated_edges = True

    node_rows = [
        {
            "entity_id": module["entity_id"],
            "type": module["type"],
            "name": module["name"],
            "fact_count": int(module["fact_count"]),
            "episode_count": int(module["episode_count"]),
            "reference_time": module["reference_time"],
            "hover_text": list(module["hover_text"]),
        }
        for module in module_stats.values()
        if str(module["entity_id"]) in selected_ids
    ]
    node_rows.sort(key=lambda row: (row["fact_count"], row["episode_count"], row["name"]), reverse=True)

    return {
        "generated_at": now.isoformat(),
        "mode": "code",
        "empty_reason": "none" if node_rows else "no_graph_data",
        "available_modes": ["concepts", "code"],
        "node_primary_label": "Symbols",
        "node_secondary_label": "Files",
        "edge_support_label": "Importing files",
        "entity_count": len(node_rows),
        "relationship_count": len(edge_rows),
        "truncated": truncated_nodes or truncated_edges,
        "nodes": node_rows,
        "edges": edge_rows,
    }


async def get_code_topology_entity_detail_impl(
    *,
    session: AsyncSession,
    project_id: str,
    entity_id: str,
) -> dict[str, Any]:
    ready_run = await _get_latest_ready_index_run(session, project_id=project_id)
    if ready_run is None:
        raise ValueError("Code index is not ready")

    module_prefix = "module:"
    if not entity_id.startswith(module_prefix):
        raise ValueError("Code topology currently supports module nodes only")
    module_name = entity_id[len(module_prefix) :]
    file_rows = await _file_rows_for_index(session, index_id=str(ready_run["index_id"]))
    module_file_rows = [row for row in file_rows if str(row.get("module_name") or "") == module_name]
    if not module_file_rows:
        raise ValueError("Entity not found")

    file_paths = [str(row.get("file_path") or "") for row in module_file_rows if str(row.get("file_path") or "")]
    symbol_rows = await _entity_rows_for_file_paths(
        session,
        index_id=str(ready_run["index_id"]),
        file_paths=file_paths,
        entity_type="Symbol",
    )
    file_chunk_rows = await _chunk_rows_for_entity_ids(
        session,
        index_id=str(ready_run["index_id"]),
        entity_ids=[_file_entity_id(path) for path in file_paths],
    )

    import_counts: Counter[str] = Counter()
    imported_by_counts: Counter[str] = Counter()
    all_module_names = {str(row.get("module_name") or "") for row in file_rows if str(row.get("module_name") or "")}
    for row in file_rows:
        source_module = str(row.get("module_name") or "")
        imports = ((row.get("row_json") or {}).get("imports") or [])
        for import_name in imports:
            target_module = str(import_name or "").strip()
            if not target_module or target_module not in all_module_names or target_module == source_module:
                continue
            if source_module == module_name:
                import_counts[target_module] += 1
            if target_module == module_name:
                imported_by_counts[source_module] += 1

    related_entities = [
        {
            "entity_id": _module_entity_id_from_name(name),
            "type": "Module",
            "name": name,
            "relation_type": "IMPORTS",
            "support_count": int(count),
        }
        for name, count in import_counts.items()
    ] + [
        {
            "entity_id": _module_entity_id_from_name(name),
            "type": "Module",
            "name": name,
            "relation_type": "IMPORTED_BY",
            "support_count": int(count),
        }
        for name, count in imported_by_counts.items()
    ]
    related_entities.sort(
        key=lambda item: (item["support_count"], item["relation_type"], item["name"]),
        reverse=True,
    )

    citations = [
        {
            "citation_id": str(chunk.get("chunk_id") or ""),
            "source_type": "code_chunk",
            "entity_id": str(chunk.get("entity_id") or ""),
            "file_path": chunk.get("file_path"),
            "line_start": chunk.get("line_start"),
            "line_end": chunk.get("line_end"),
            "snippet": chunk.get("snippet"),
        }
        for chunk in file_chunk_rows[:8]
    ]

    return {
        "mode": "code",
        "entity": {
            "entity_id": entity_id,
            "type": "Module",
            "name": module_name,
            "fact_count": len(symbol_rows),
            "episode_count": len(file_paths),
            "file_paths": file_paths,
            "language": None,
            "kind": None,
        },
        "facts": [],
        "provenance": [],
        "related_entities": related_entities[:10],
        "citations": citations,
        "symbols": [
            {
                "entity_id": str(row.get("entity_id") or ""),
                "name": str(row.get("name") or ""),
                "kind": row.get("kind"),
                "file_path": row.get("file_path"),
                "line_start": row.get("line_start"),
                "line_end": row.get("line_end"),
                "language": row.get("language"),
            }
            for row in symbol_rows[:24]
        ],
    }
