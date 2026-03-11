from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.code_index import _get_latest_ready_index_run, search_entities as search_code_index_entities
from viberecall_mcp.ids import new_id
from viberecall_mcp.repositories.canonical_memory import (
    add_entity_alias,
    create_entity_resolution_event,
    create_fact_group,
    create_provenance_link,
    create_entity_redirect,
    delete_episode_canonical_memory,
    ensure_projection_watermark,
    ensure_relation_type,
    get_entity_direct,
    get_entity,
    get_fact_version,
    get_memory_search_doc,
    get_current_fact_by_version_or_group,
    get_neighbors as repo_get_neighbors,
    get_entity_redirect,
    find_paths as repo_find_paths,
    get_relation_type,
    insert_fact_version,
    list_current_facts as repo_list_current_facts,
    list_fact_supporting_episodes,
    list_fact_lineage,
    list_fact_provenance,
    merge_entities as repo_merge_entities,
    natural_key_hash,
    resolve_entity_redirect,
    resolve_open_unresolved_mention,
    search_entities as repo_search_entities,
    search_memory_docs,
    set_current_fact_version,
    split_entity as repo_split_entity,
    supersede_current_fact_version,
    upsert_open_unresolved_mention,
    update_entity_salience,
    update_fact_version_salience,
    upsert_entity,
    upsert_memory_search_doc,
)
from viberecall_mcp.repositories.episodes import get_episode_for_project, update_episode_salience


_DEFAULT_SALIENCE_CLASS = "WARM"
_DEFAULT_SALIENCE_SCORE = 0.5
_PINNED_SALIENCE_CLASS = "PINNED"
_PINNED_SALIENCE_SCORE = 1.0
_COLD_SALIENCE_CLASS = "COLD"
_COLD_SALIENCE_SCORE = 0.2
_MANUAL_SALIENCE_KEY = "manual_salience"


def _salience_score_for_class(value: str) -> float:
    normalized = str(value or _DEFAULT_SALIENCE_CLASS).upper()
    if normalized == _PINNED_SALIENCE_CLASS:
        return _PINNED_SALIENCE_SCORE
    if normalized == _COLD_SALIENCE_CLASS:
        return _COLD_SALIENCE_SCORE
    return _DEFAULT_SALIENCE_SCORE


def _normalize_salience_class(value: str | None) -> str:
    normalized = str(value or _DEFAULT_SALIENCE_CLASS).strip().upper()
    return normalized or _DEFAULT_SALIENCE_CLASS


def _normalize_salience_score(value: Any, *, salience_class: str) -> float:
    if value is None:
        return _salience_score_for_class(salience_class)
    return float(value)


def _unresolved_mention_result(payload: dict | None) -> dict | None:
    if payload is None:
        return None
    return {
        "mention_id": str(payload["mention_id"]),
        "status": str(payload["status"]),
    }


def _resolution_tracking_context(
    *,
    mention_text: str,
    observed_kind: str | None,
    repo_scope: str | None,
    status: str,
    best_match: dict | None,
    candidates: list[dict],
    latest_ready_index: dict | None,
) -> dict:
    payload: dict[str, Any] = {
        "source": "viberecall_resolve_reference",
        "mention_text": mention_text,
        "observed_kind": observed_kind,
        "repo_scope": repo_scope,
        "last_status": status,
        "candidate_count": len(candidates),
        "candidate_entity_ids": [
            str(candidate.get("entity_id"))
            for candidate in candidates
            if str(candidate.get("entity_id") or "").strip()
        ],
        "latest_ready_index": latest_ready_index,
        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    if best_match is not None:
        payload["best_match"] = best_match
    if candidates:
        payload["candidates"] = candidates
    return payload


def _manual_salience_state(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}
    value = metadata.get(_MANUAL_SALIENCE_KEY)
    return value if isinstance(value, dict) else {}


def _with_manual_salience(metadata: dict | None, manual_state: dict) -> dict:
    updated = dict(metadata or {})
    updated[_MANUAL_SALIENCE_KEY] = manual_state
    return updated


def _apply_pin_action(
    *,
    current_score: Any,
    current_class: str | None,
    metadata: dict | None,
    pin_action: str,
    reason: str | None,
) -> tuple[float, str, dict]:
    normalized_action = str(pin_action).upper()
    updated_at = datetime.now(timezone.utc).isoformat()
    current_class_normalized = _normalize_salience_class(current_class)
    current_score_normalized = _normalize_salience_score(current_score, salience_class=current_class_normalized)
    manual_state = _manual_salience_state(metadata)
    override_active = bool(manual_state.get("override_active"))
    baseline_class = _normalize_salience_class(manual_state.get("baseline_class") if manual_state else current_class_normalized)
    baseline_score = _normalize_salience_score(
        manual_state.get("baseline_score") if manual_state else current_score_normalized,
        salience_class=baseline_class,
    )

    if normalized_action == "PIN":
        manual_state = {
            "baseline_score": baseline_score if override_active else current_score_normalized,
            "baseline_class": baseline_class if override_active else current_class_normalized,
            "override_active": True,
            "last_action": normalized_action,
            "reason": reason,
            "updated_at": updated_at,
        }
        return _PINNED_SALIENCE_SCORE, _PINNED_SALIENCE_CLASS, _with_manual_salience(metadata, manual_state)

    if normalized_action == "DEMOTE":
        manual_state = {
            "baseline_score": baseline_score if override_active else current_score_normalized,
            "baseline_class": baseline_class if override_active else current_class_normalized,
            "override_active": True,
            "last_action": normalized_action,
            "reason": reason,
            "updated_at": updated_at,
        }
        return _COLD_SALIENCE_SCORE, _COLD_SALIENCE_CLASS, _with_manual_salience(metadata, manual_state)

    restored_class = _normalize_salience_class(manual_state.get("baseline_class")) if manual_state else _DEFAULT_SALIENCE_CLASS
    restored_score = _normalize_salience_score(
        manual_state.get("baseline_score"),
        salience_class=restored_class,
    ) if manual_state else _DEFAULT_SALIENCE_SCORE
    manual_state = {
        "baseline_score": restored_score,
        "baseline_class": restored_class,
        "override_active": False,
        "last_action": normalized_action,
        "reason": reason,
        "updated_at": updated_at,
    }
    return restored_score, restored_class, _with_manual_salience(metadata, manual_state)


def _salience_state_payload(*, score: Any, salience_class: str | None, metadata: dict | None) -> dict:
    manual_state = _manual_salience_state(metadata)
    normalized_class = _normalize_salience_class(salience_class)
    normalized_score = _normalize_salience_score(score, salience_class=normalized_class)
    return {
        "salience_score": normalized_score,
        "salience_class": normalized_class,
        "manual_override": bool(manual_state.get("override_active")),
        "reason": manual_state.get("reason"),
        "updated_at": manual_state.get("updated_at"),
    }


def _fact_rank_features(
    *,
    fact_version_id: str,
    fact_group_id: str,
    statement: str,
    valid_at: str | None,
    invalid_at: str | None,
    salience_score: Any,
    salience_class: str | None,
    entities: list[dict],
    provenance_episode_ids: list[str],
    reference_time: str | None,
    summary: str,
) -> dict:
    return {
        "kind": "fact",
        "fact": {
            "id": fact_version_id,
            "fact_version_id": fact_version_id,
            "fact_group_id": fact_group_id,
            "text": statement,
            "statement": statement,
            "valid_at": valid_at,
            "invalid_at": invalid_at,
            "salience_score": _normalize_salience_score(salience_score, salience_class=_normalize_salience_class(salience_class)),
            "salience_class": _normalize_salience_class(salience_class),
        },
        "entities": entities,
        "provenance": {
            "episode_ids": provenance_episode_ids,
            "reference_time": reference_time,
            "ingested_at": None,
        },
        "summary": summary,
    }


def _episode_rank_features(
    *,
    episode_id: str,
    reference_time: str | None,
    summary: str | None,
    metadata: dict | None,
    salience_score: Any,
    salience_class: str | None,
) -> dict:
    return {
        "kind": "episode",
        "episode": {
            "episode_id": episode_id,
            "reference_time": reference_time,
            "summary": summary,
            "metadata": metadata or {},
            "salience_score": _normalize_salience_score(salience_score, salience_class=_normalize_salience_class(salience_class)),
            "salience_class": _normalize_salience_class(salience_class),
        },
    }


def _metadata_dict(value: Any) -> dict:
    if isinstance(value, str):
        return json.loads(value)
    return value if isinstance(value, dict) else {}


def _entity_id(project_id: str, kind: str, value: str) -> str:
    digest = hashlib.sha1(f"{project_id}:{kind}:{value.strip().lower()}".encode("utf-8")).hexdigest()[:24]
    return f"ent_{digest}"


def _normalize_statement(content: str) -> str:
    return " ".join(content.split()).strip().lower()


def _summary(content: str) -> str:
    return (content or "").strip()[:160].strip()


def _entity_payload(entity_id: str, entity_kind: str, name: str) -> dict:
    return {
        "id": entity_id,
        "entity_id": entity_id,
        "type": entity_kind,
        "name": name,
    }


def _reference_match(candidate: dict, normalized_query: str) -> dict:
    canonical_name = str(candidate.get("canonical_name") or "").strip().lower()
    display_name = str(candidate.get("display_name") or "").strip().lower()
    aliases = [str(alias).strip().lower() for alias in (candidate.get("aliases") or []) if str(alias).strip()]

    if normalized_query and normalized_query in aliases:
        return {"rank": 0, "source": "alias", "exact": True}
    if normalized_query and normalized_query == canonical_name:
        return {"rank": 0, "source": "canonical_name", "exact": True}
    if normalized_query and normalized_query == display_name:
        return {"rank": 0, "source": "display_name", "exact": True}

    values = aliases + [canonical_name, display_name]
    if normalized_query and any(value.startswith(normalized_query) for value in values if value):
        return {"rank": 1, "source": "prefix", "exact": False}
    if normalized_query and any(normalized_query in value for value in values if value):
        return {"rank": 2, "source": "contains", "exact": False}
    return {"rank": 99, "source": "none", "exact": False}


def _code_index_entity_types(observed_kind: str | None) -> list[str] | None:
    normalized = str(observed_kind or "").strip()
    if normalized in {"File", "Module", "Symbol"}:
        return [normalized]
    return None


def _reference_candidate_from_canonical(candidate: dict, *, normalized_query: str) -> dict:
    match = _reference_match(candidate, normalized_query)
    return {
        "candidate_type": "canonical_entity",
        "entity_id": candidate.get("entity_id"),
        "name": candidate.get("display_name") or candidate.get("name"),
        "display_name": candidate.get("display_name") or candidate.get("name"),
        "canonical_name": candidate.get("canonical_name"),
        "entity_kind": candidate.get("entity_kind") or candidate.get("type"),
        "aliases": list(candidate.get("aliases") or []),
        "support_count": int(candidate.get("support_count") or 0),
        "salience_score": candidate.get("salience_score"),
        "salience_class": candidate.get("salience_class"),
        "score": candidate.get("salience_score") or 0.5,
        "provisional": False,
        "match": match,
        "snapshot_ref": None,
    }


def _reference_candidate_from_code_index(candidate: dict, *, snapshot_ref: dict | None, normalized_query: str) -> dict:
    name = str(candidate.get("name") or "")
    lower_name = name.strip().lower()
    exact = bool(normalized_query and lower_name == normalized_query)
    rank = 0 if exact else (1 if normalized_query and lower_name.startswith(normalized_query) else 2)
    return {
        "candidate_type": "code_index_entity",
        "entity_id": None,
        "name": name,
        "display_name": name,
        "canonical_name": name,
        "entity_kind": candidate.get("type"),
        "aliases": [],
        "support_count": 0,
        "salience_score": None,
        "salience_class": None,
        "score": candidate.get("score"),
        "provisional": True,
        "match": {
            "rank": rank,
            "source": "code_index",
            "exact": exact,
        },
        "snapshot_ref": snapshot_ref,
        "file_path": candidate.get("file_path"),
        "language": candidate.get("language"),
        "kind": candidate.get("kind"),
        "line_start": candidate.get("line_start"),
        "line_end": candidate.get("line_end"),
    }


@dataclass(slots=True)
class CanonicalSaveResult:
    observation_doc_id: str
    fact_group_id: str
    fact_version_id: str
    entities: list[dict]


async def _sync_episode_search_doc(
    session: AsyncSession,
    *,
    project_id: str,
    episode_id: str,
    content: str,
    reference_time: str | None,
    summary: str | None,
    metadata: dict | None,
    salience_score: Any,
    salience_class: str | None,
) -> None:
    doc_id = f"episode:{episode_id}"
    existing = await get_memory_search_doc(session, project_id=project_id, doc_id=doc_id)
    await upsert_memory_search_doc(
        session,
        doc_id=doc_id,
        project_id=project_id,
        doc_kind="episode",
        source_id=episode_id,
        title=(str(existing.get("title")) if existing and existing.get("title") is not None else (summary or content[:80])),
        body=(str(existing.get("body")) if existing and existing.get("body") is not None else content),
        filters=(existing.get("filters_json") if existing else metadata) or {},
        rank_features=_episode_rank_features(
            episode_id=episode_id,
            reference_time=reference_time,
            summary=summary,
            metadata=metadata,
            salience_score=salience_score,
            salience_class=salience_class,
        ),
    )


async def _sync_fact_search_doc(
    session: AsyncSession,
    *,
    project_id: str,
    fact_version_id: str,
    fact_group_id: str,
    statement: str,
    valid_at: str | None,
    invalid_at: str | None,
    metadata: dict | None,
    salience_score: Any,
    salience_class: str | None,
    entities: list[dict],
    provenance_episode_ids: list[str],
) -> None:
    doc_id = f"fact:{fact_version_id}"
    existing = await get_memory_search_doc(session, project_id=project_id, doc_id=doc_id)
    summary = _summary(statement)
    await upsert_memory_search_doc(
        session,
        doc_id=doc_id,
        project_id=project_id,
        doc_kind="fact",
        source_id=fact_version_id,
        title=(str(existing.get("title")) if existing and existing.get("title") is not None else (summary or statement[:80])),
        body=(
            str(existing.get("body"))
            if existing and existing.get("body") is not None
            else " ".join([statement] + [entity["name"] for entity in entities])
        ),
        filters=(existing.get("filters_json") if existing else metadata) or {},
        rank_features=_fact_rank_features(
            fact_version_id=fact_version_id,
            fact_group_id=fact_group_id,
            statement=statement,
            valid_at=valid_at,
            invalid_at=invalid_at,
            salience_score=salience_score,
            salience_class=salience_class,
            entities=entities,
            provenance_episode_ids=provenance_episode_ids,
            reference_time=valid_at,
            summary=summary,
        ),
    )


async def delete_canonical_episode(
    session: AsyncSession,
    *,
    project_id: str,
    episode_id: str,
) -> dict:
    return await delete_episode_canonical_memory(
        session,
        project_id=project_id,
        episode_id=episode_id,
    )


async def save_canonical_episode(
    session: AsyncSession,
    *,
    project_id: str,
    episode_id: str,
    content: str,
    reference_time: str | None,
    metadata: dict | None,
) -> CanonicalSaveResult:
    metadata = metadata or {}
    statement = content.strip()
    summary = _summary(statement)
    relation_type_id = "observation_captured"
    await ensure_relation_type(
        session,
        relation_type_id=relation_type_id,
        name="observation_captured",
        inverse_name="captured_in_observation",
        relation_class="observation",
    )

    subject_name = str(metadata.get("repo") or f"project:{project_id}")
    subject_kind = "Repository" if metadata.get("repo") else "Project"
    subject_entity_id = _entity_id(project_id, subject_kind, subject_name)
    await upsert_entity(
        session,
        entity_id=subject_entity_id,
        project_id=project_id,
        entity_kind=subject_kind,
        canonical_name=subject_name.strip().lower(),
        display_name=subject_name,
        metadata={"source": "episode", "episode_id": episode_id},
    )
    await add_entity_alias(
        session,
        project_id=project_id,
        entity_id=subject_entity_id,
        alias_type="name",
        alias_value=subject_name,
        confidence=1.0,
    )

    entities = [_entity_payload(subject_entity_id, subject_kind, subject_name)]
    for file_path in metadata.get("files") or []:
        entity_id = _entity_id(project_id, "File", str(file_path))
        await upsert_entity(
            session,
            entity_id=entity_id,
            project_id=project_id,
            entity_kind="File",
            canonical_name=str(file_path).strip().lower(),
            display_name=str(file_path),
            metadata={"source": "episode", "episode_id": episode_id},
        )
        await add_entity_alias(
            session,
            project_id=project_id,
            entity_id=entity_id,
            alias_type="path",
            alias_value=str(file_path),
        )
        entities.append(_entity_payload(entity_id, "File", str(file_path)))

    for tag in metadata.get("tags") or []:
        entity_id = _entity_id(project_id, "Tag", str(tag))
        await upsert_entity(
            session,
            entity_id=entity_id,
            project_id=project_id,
            entity_kind="Tag",
            canonical_name=str(tag).strip().lower(),
            display_name=str(tag),
            metadata={"source": "episode", "episode_id": episode_id},
        )
        await add_entity_alias(
            session,
            project_id=project_id,
            entity_id=entity_id,
            alias_type="tag",
            alias_value=str(tag),
        )
        entities.append(_entity_payload(entity_id, "Tag", str(tag)))

    fact_group_id = new_id("factgrp")
    fact_version_id = new_id("factv")
    doc_id = f"fact:{fact_version_id}"
    key_hash = natural_key_hash(project_id=project_id, statement=statement, metadata=metadata)
    await create_fact_group(
        session,
        fact_group_id=fact_group_id,
        project_id=project_id,
        natural_key_hash=key_hash,
    )
    await insert_fact_version(
        session,
        fact_version_id=fact_version_id,
        fact_group_id=fact_group_id,
        project_id=project_id,
        fact_shape="observation",
        subject_entity_id=subject_entity_id,
        relation_type_id=relation_type_id,
        statement=statement,
        normalized_statement=_normalize_statement(statement),
        value_json={"metadata": metadata, "summary": summary},
        valid_from=reference_time,
        status="CURRENT",
        confidence=0.75,
        salience_score=0.5,
        salience_class=_DEFAULT_SALIENCE_CLASS,
        trust_class="observed",
        created_from_episode_id=episode_id,
        metadata=metadata,
    )
    await set_current_fact_version(session, fact_group_id=fact_group_id, fact_version_id=fact_version_id)

    await create_provenance_link(
        session,
        project_id=project_id,
        source_kind="episode",
        source_id=episode_id,
        target_kind="fact_group",
        target_id=fact_group_id,
        role="supports",
        metadata={"fact_version_id": fact_version_id},
    )
    await create_provenance_link(
        session,
        project_id=project_id,
        source_kind="episode",
        source_id=episode_id,
        target_kind="fact_version",
        target_id=fact_version_id,
        role="created",
        metadata={"fact_group_id": fact_group_id},
    )

    for entity in entities:
        await create_provenance_link(
            session,
            project_id=project_id,
            source_kind="episode",
            source_id=episode_id,
            target_kind="entity",
            target_id=entity["entity_id"],
            role="mentioned",
            metadata={"fact_group_id": fact_group_id},
        )

    await _sync_episode_search_doc(
        session,
        project_id=project_id,
        episode_id=episode_id,
        content=statement,
        reference_time=reference_time,
        summary=summary,
        metadata=metadata,
        salience_score=_DEFAULT_SALIENCE_SCORE,
        salience_class=_DEFAULT_SALIENCE_CLASS,
    )
    await _sync_fact_search_doc(
        session,
        project_id=project_id,
        fact_version_id=fact_version_id,
        fact_group_id=fact_group_id,
        statement=statement,
        valid_at=reference_time,
        invalid_at=None,
        metadata={
            "tags": metadata.get("tags") or [],
            "files": metadata.get("files") or [],
            "repo": metadata.get("repo"),
            "entity_types": [entity["type"] for entity in entities],
        },
        salience_score=_DEFAULT_SALIENCE_SCORE,
        salience_class=_DEFAULT_SALIENCE_CLASS,
        entities=entities,
        provenance_episode_ids=[episode_id],
    )
    await ensure_projection_watermark(
        session,
        project_id=project_id,
        projection_name="memory_search_docs",
        watermark=1,
    )
    return CanonicalSaveResult(
        observation_doc_id=doc_id,
        fact_group_id=fact_group_id,
        fact_version_id=fact_version_id,
        entities=entities,
    )


async def search_canonical_memory(
    session: AsyncSession,
    *,
    project_id: str,
    query: str,
    filters: dict | None,
    sort: str,
    limit: int,
    offset: int,
) -> list[dict]:
    rows = await search_memory_docs(
        session,
        project_id=project_id,
        query=query,
        filters=filters,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    results = []
    for row in rows:
        payload = row.get("rank_features_json") or {}
        if row["doc_kind"] == "fact":
            result = payload or {}
            result["kind"] = "fact"
            result["score"] = float(row.get("score") or 0.0)
            fact_payload = result.get("fact") if isinstance(result, dict) else None
            if isinstance(fact_payload, dict):
                fact_payload.setdefault("salience_score", _DEFAULT_SALIENCE_SCORE)
                fact_payload.setdefault("salience_class", _DEFAULT_SALIENCE_CLASS)
            results.append(result)
            continue
        episode_payload = payload.get("episode") if isinstance(payload, dict) else None
        if episode_payload is not None:
            episode_payload.setdefault("salience_score", _DEFAULT_SALIENCE_SCORE)
            episode_payload.setdefault("salience_class", _DEFAULT_SALIENCE_CLASS)
            results.append(
                {
                    "kind": "episode",
                    "episode": episode_payload,
                    "score": float(row.get("score") or 0.0),
                }
            )
    return results


async def list_canonical_facts(
    session: AsyncSession,
    *,
    project_id: str,
    filters: dict | None,
    limit: int,
    offset: int,
) -> list[dict]:
    return await repo_list_current_facts(
        session,
        project_id=project_id,
        filters=filters,
        limit=limit,
        offset=offset,
    )


async def search_canonical_entities(
    session: AsyncSession,
    *,
    project_id: str,
    query: str,
    entity_kinds: list[str] | None,
    salience_classes: list[str] | None,
    limit: int,
) -> dict:
    entities = await repo_search_entities(
        session,
        project_id=project_id,
        query=query,
        entity_kinds=entity_kinds,
        salience_classes=salience_classes,
        limit=limit,
    )
    return {
        "status": "READY",
        "query": query,
        "entities": entities,
        "total": len(entities),
    }


async def resolve_reference(
    session: AsyncSession,
    *,
    project_id: str,
    mention_text: str,
    observed_kind: str | None,
    repo_scope: str | None,
    include_code_index: bool,
    limit: int,
) -> dict:
    normalized_query = " ".join(str(mention_text).split()).strip().lower()
    canonical_candidates = await repo_search_entities(
        session,
        project_id=project_id,
        query=mention_text,
        entity_kinds=[str(observed_kind)] if str(observed_kind or "").strip() else None,
        salience_classes=None,
        limit=max(limit * 2, limit),
    )
    canonical_results = [
        _reference_candidate_from_canonical(candidate, normalized_query=normalized_query)
        for candidate in canonical_candidates
        if (
            not repo_scope
            or repo_scope in json.dumps(candidate.get("metadata") or {}, sort_keys=True)
            or repo_scope in " ".join(str(alias) for alias in (candidate.get("aliases") or []))
        )
    ]
    canonical_results.sort(
        key=lambda item: (
            -int(item["match"]["rank"]),
            float(item.get("score") or 0.0),
            int(item.get("support_count") or 0),
            str(item.get("display_name") or ""),
        ),
        reverse=True,
    )
    canonical_results.sort(
        key=lambda item: (
            int(item["match"]["rank"]),
            -float(item.get("score") or 0.0),
            -int(item.get("support_count") or 0),
            str(item.get("display_name") or ""),
        )
    )

    latest_ready_index = None
    provisional_candidates: list[dict] = []
    ready_run = await _get_latest_ready_index_run(session, project_id=project_id)
    if ready_run is not None:
        latest_ready_index = {
            "index_id": str(ready_run.get("index_id")),
            "completed_at": ready_run.get("completed_at").isoformat()
            if getattr(ready_run.get("completed_at"), "isoformat", None)
            else str(ready_run.get("completed_at") or ""),
            "repo_source_type": ready_run.get("repo_source_type"),
            "repo_source_ref": ready_run.get("repo_source_ref"),
            "repo_name": ready_run.get("repo_name"),
        }
    if include_code_index and ready_run is not None:
        index_result = await search_code_index_entities(
            session=session,
            project_id=project_id,
            query=mention_text,
            entity_types=_code_index_entity_types(observed_kind),
            limit=max(limit * 2, limit),
        )
        provisional_candidates = [
            _reference_candidate_from_code_index(
                candidate,
                snapshot_ref=latest_ready_index,
                normalized_query=normalized_query,
            )
            for candidate in (index_result.get("entities") or [])
            if not repo_scope or str(candidate.get("file_path") or "").startswith(str(repo_scope))
        ]
        provisional_candidates.sort(
            key=lambda item: (
                int(item["match"]["rank"]),
                -float(item.get("score") or 0.0),
                str(item.get("display_name") or ""),
            )
        )

    ordered_candidates = (canonical_results + provisional_candidates)[:limit]
    canonical_best = canonical_results[0] if canonical_results else None
    provisional_best = provisional_candidates[0] if provisional_candidates else None

    if canonical_best is not None:
        best_rank = int(canonical_best["match"]["rank"])
        same_rank = [candidate for candidate in canonical_results if int(candidate["match"]["rank"]) == best_rank]
        status = "RESOLVED" if len(same_rank) == 1 else "AMBIGUOUS"
        best_match = canonical_best
    elif provisional_best is not None:
        best_rank = int(provisional_best["match"]["rank"])
        same_rank = [candidate for candidate in provisional_candidates if int(candidate["match"]["rank"]) == best_rank]
        status = "RESOLVED" if len(same_rank) == 1 else "AMBIGUOUS"
        best_match = provisional_best
    else:
        status = "NO_MATCH"
        best_match = None

    unresolved_mention = None
    tracking_context = _resolution_tracking_context(
        mention_text=mention_text,
        observed_kind=observed_kind,
        repo_scope=repo_scope,
        status=status,
        best_match=best_match,
        candidates=ordered_candidates,
        latest_ready_index=latest_ready_index,
    )
    if status in {"AMBIGUOUS", "NO_MATCH"}:
        unresolved_mention = await upsert_open_unresolved_mention(
            session,
            mention_id=new_id("mention"),
            project_id=project_id,
            mention_text=mention_text,
            observed_kind=observed_kind,
            repo_scope=repo_scope,
            context=tracking_context,
        )
    elif status == "RESOLVED":
        unresolved_mention = await resolve_open_unresolved_mention(
            session,
            project_id=project_id,
            mention_text=mention_text,
            observed_kind=observed_kind,
            repo_scope=repo_scope,
            context={
                **tracking_context,
                "resolved_match": best_match,
            },
        )

    return {
        "status": status,
        "best_match": best_match,
        "candidates": ordered_candidates,
        "needs_disambiguation": status == "AMBIGUOUS",
        "latest_ready_index": latest_ready_index,
        "unresolved_mention": _unresolved_mention_result(unresolved_mention),
    }


async def get_canonical_neighbors(
    session: AsyncSession,
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
    return await repo_get_neighbors(
        session,
        project_id=project_id,
        entity_id=entity_id,
        direction=direction,
        relation_types=relation_types,
        current_only=current_only,
        valid_at=valid_at,
        as_of_system_time=as_of_system_time,
        limit=limit,
    )


async def find_canonical_paths(
    session: AsyncSession,
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
    src_entity = await get_entity(
        session,
        project_id=project_id,
        entity_id=src_entity_id,
    )
    if src_entity is None:
        return {
            "missing_entity_id": src_entity_id,
            "missing_role": "src",
        }

    dst_entity = await get_entity(
        session,
        project_id=project_id,
        entity_id=dst_entity_id,
    )
    if dst_entity is None:
        return {
            "missing_entity_id": dst_entity_id,
            "missing_role": "dst",
        }

    result = await repo_find_paths(
        session,
        project_id=project_id,
        src_entity_id=src_entity_id,
        dst_entity_id=dst_entity_id,
        relation_types=relation_types,
        max_depth=max_depth,
        current_only=current_only,
        valid_at=valid_at,
        as_of_system_time=as_of_system_time,
        limit_paths=limit_paths,
    )
    return {
        **result,
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


async def get_canonical_fact(
    session: AsyncSession,
    *,
    project_id: str,
    fact_version_id: str | None = None,
    fact_group_id: str | None = None,
) -> dict | None:
    current = await get_current_fact_by_version_or_group(
        session,
        project_id=project_id,
        fact_version_id=fact_version_id,
        fact_group_id=fact_group_id,
    )
    if current is None:
        return None
    lineage = await list_fact_lineage(
        session,
        project_id=project_id,
        fact_group_id=current["fact_group_id"],
    )
    provenance = await list_fact_provenance(
        session,
        project_id=project_id,
        fact_group_id=current["fact_group_id"],
    )
    return {
        "current": current,
        "lineage": lineage,
        "provenance": provenance,
        "related_entities": [current["subject_entity_id"], current.get("object_entity_id")],
    }


async def explain_canonical_fact(
    session: AsyncSession,
    *,
    project_id: str,
    fact_version_id: str,
) -> dict | None:
    fact = await get_fact_version(
        session,
        project_id=project_id,
        fact_version_id=fact_version_id,
    )
    if fact is None:
        return None

    relation_type = await get_relation_type(
        session,
        relation_type_id=fact["relation_type_id"],
    )
    subject_entity = await get_entity(
        session,
        project_id=project_id,
        entity_id=fact["subject_entity_id"],
    )
    object_entity = None
    if fact.get("object_entity_id"):
        object_entity = await get_entity(
            session,
            project_id=project_id,
            entity_id=str(fact["object_entity_id"]),
        )

    lineage_versions = await list_fact_lineage(
        session,
        project_id=project_id,
        fact_group_id=fact["fact_group_id"],
    )
    current_group = await get_current_fact_by_version_or_group(
        session,
        project_id=project_id,
        fact_group_id=fact["fact_group_id"],
    )
    lineage = []
    ordered_versions = list(reversed(lineage_versions))
    for index, version in enumerate(ordered_versions):
        lineage.append(
            {
                **version,
                "is_current": current_group is not None and version["fact_version_id"] == current_group["fact_version_id"],
                "previous_fact_version_id": ordered_versions[index - 1]["fact_version_id"] if index > 0 else None,
                "next_fact_version_id": ordered_versions[index + 1]["fact_version_id"]
                if index + 1 < len(ordered_versions)
                else None,
            }
        )

    provenance = await list_fact_provenance(
        session,
        project_id=project_id,
        fact_group_id=fact["fact_group_id"],
    )
    supporting_episodes = await list_fact_supporting_episodes(
        session,
        project_id=project_id,
        fact_group_id=fact["fact_group_id"],
    )
    return {
        "fact": {
            **fact,
            "subject_entity": subject_entity,
            "object_entity": object_entity,
            "relation_type": relation_type,
        },
        "lineage": {
            "fact_group_id": fact["fact_group_id"],
            "current_fact_version_id": current_group["fact_version_id"] if current_group else None,
            "versions": lineage,
        },
        "supporting_episodes": supporting_episodes,
        "extraction_details": {
            "relation_type": relation_type,
            "provenance": provenance,
            "created_from_episode_id": fact.get("created_from_episode_id"),
            "metadata": fact.get("metadata") or {},
        },
        "confidence_breakdown": {
            "confidence": fact.get("confidence"),
            "salience_score": fact.get("salience_score"),
            "salience_class": fact.get("salience_class"),
            "trust_class": fact.get("trust_class"),
            "status": fact.get("status"),
            "is_current": current_group is not None and fact["fact_version_id"] == current_group["fact_version_id"],
        },
    }


async def update_canonical_fact(
    session: AsyncSession,
    *,
    project_id: str,
    fact_group_id: str,
    expected_current_version_id: str,
    statement: str,
    effective_time: str,
    reason: str | None,
    metadata: dict | None = None,
) -> dict:
    current = await get_current_fact_by_version_or_group(
        session,
        project_id=project_id,
        fact_group_id=fact_group_id,
    )
    if current is None:
        raise KeyError(fact_group_id)
    if current["fact_version_id"] != expected_current_version_id:
        raise RuntimeError(json.dumps({"code": "CONFLICT", "expected_current_version_id": current["fact_version_id"]}))
    updated = await supersede_current_fact_version(
        session,
        fact_group_id=fact_group_id,
        expected_current_version_id=expected_current_version_id,
        superseded_at=effective_time,
    )
    if not updated:
        raise RuntimeError(json.dumps({"code": "CONFLICT", "expected_current_version_id": current["fact_version_id"]}))

    new_fact_version_id = new_id("factv")
    merged_metadata = dict(current.get("metadata") or {})
    if metadata:
        merged_metadata.update(metadata)
    if reason:
        merged_metadata["reason"] = reason
    await insert_fact_version(
        session,
        fact_version_id=new_fact_version_id,
        fact_group_id=fact_group_id,
        project_id=project_id,
        fact_shape="observation",
        subject_entity_id=current["subject_entity_id"],
        relation_type_id=current["relation_type_id"],
        object_entity_id=current.get("object_entity_id"),
        statement=statement,
        normalized_statement=_normalize_statement(statement),
        value_json=current.get("value_json") or {},
        valid_from=effective_time,
        valid_to=current.get("valid_to"),
        status="CURRENT",
        confidence=current.get("confidence"),
        salience_score=current.get("salience_score"),
        salience_class=current.get("salience_class") or _DEFAULT_SALIENCE_CLASS,
        trust_class=current.get("trust_class") or "observed",
        created_from_episode_id=current.get("created_from_episode_id"),
        replaces_fact_version_id=expected_current_version_id,
        metadata=merged_metadata,
    )
    await set_current_fact_version(session, fact_group_id=fact_group_id, fact_version_id=new_fact_version_id)
    await create_provenance_link(
        session,
        project_id=project_id,
        source_kind="fact_version",
        source_id=expected_current_version_id,
        target_kind="fact_version",
        target_id=new_fact_version_id,
        role="superseded_by",
        metadata={"reason": reason},
    )
    await _sync_fact_search_doc(
        session,
        project_id=project_id,
        fact_version_id=new_fact_version_id,
        fact_group_id=fact_group_id,
        statement=statement,
        valid_at=effective_time,
        invalid_at=None,
        metadata=merged_metadata,
        salience_score=current.get("salience_score"),
        salience_class=current.get("salience_class"),
        entities=[
            {
                "entity_id": current["subject_entity_id"],
                "name": current["subject_entity_id"],
                "type": None,
            },
        ],
        provenance_episode_ids=[current.get("created_from_episode_id")] if current.get("created_from_episode_id") else [],
    )
    return {
        "old_fact_version_id": expected_current_version_id,
        "new_fact_version_id": new_fact_version_id,
        "fact_group_id": fact_group_id,
        "committed_at": effective_time,
        "old_fact": {"id": expected_current_version_id, "invalid_at": effective_time},
        "new_fact": {
            "id": new_fact_version_id,
            "valid_at": effective_time,
            "salience_score": current.get("salience_score"),
            "salience_class": current.get("salience_class") or _DEFAULT_SALIENCE_CLASS,
        },
    }


async def pin_canonical_memory(
    session: AsyncSession,
    *,
    project_id: str,
    target_kind: str,
    target_id: str,
    pin_action: str,
    reason: str | None,
) -> dict | None:
    normalized_target_kind = str(target_kind).upper()
    normalized_pin_action = str(pin_action).upper()

    if normalized_target_kind == "FACT":
        fact = await get_current_fact_by_version_or_group(
            session,
            project_id=project_id,
            fact_version_id=target_id,
            fact_group_id=target_id,
        )
        if fact is None:
            return None
        next_score, next_class, next_metadata = _apply_pin_action(
            current_score=fact.get("salience_score"),
            current_class=fact.get("salience_class"),
            metadata=fact.get("metadata"),
            pin_action=normalized_pin_action,
            reason=reason,
        )
        updated_fact = await update_fact_version_salience(
            session,
            project_id=project_id,
            fact_version_id=fact["fact_version_id"],
            salience_score=next_score,
            salience_class=next_class,
            metadata_json=next_metadata,
        )
        if updated_fact is None:
            return None
        await _sync_fact_search_doc(
            session,
            project_id=project_id,
            fact_version_id=updated_fact["fact_version_id"],
            fact_group_id=updated_fact["fact_group_id"],
            statement=updated_fact["statement"],
            valid_at=updated_fact.get("valid_from"),
            invalid_at=updated_fact.get("valid_to"),
            metadata=updated_fact.get("metadata") or {},
            salience_score=updated_fact.get("salience_score"),
            salience_class=updated_fact.get("salience_class"),
            entities=[
                {
                    "entity_id": updated_fact["subject_entity_id"],
                    "name": updated_fact["subject_entity_id"],
                    "type": None,
                },
            ],
            provenance_episode_ids=[updated_fact.get("created_from_episode_id")]
            if updated_fact.get("created_from_episode_id")
            else [],
        )
        await ensure_projection_watermark(
            session,
            project_id=project_id,
            projection_name="memory_search_docs",
            watermark=1,
        )
        salience_state = _salience_state_payload(
            score=updated_fact.get("salience_score"),
            salience_class=updated_fact.get("salience_class"),
            metadata=updated_fact.get("metadata"),
        )
        return {
            "target_kind": normalized_target_kind,
            "target_id": target_id,
            "resolved_target": {
                "fact_group_id": updated_fact["fact_group_id"],
                "fact_version_id": updated_fact["fact_version_id"],
            },
            "pin_action": normalized_pin_action,
            "salience_state": salience_state,
            "updated_at": salience_state["updated_at"],
        }

    if normalized_target_kind == "ENTITY":
        entity = await get_entity(
            session,
            project_id=project_id,
            entity_id=target_id,
        )
        if entity is None:
            return None
        next_score, next_class, next_metadata = _apply_pin_action(
            current_score=entity.get("salience_score"),
            current_class=entity.get("salience_class"),
            metadata=entity.get("metadata"),
            pin_action=normalized_pin_action,
            reason=reason,
        )
        updated_entity = await update_entity_salience(
            session,
            project_id=project_id,
            entity_id=target_id,
            salience_score=next_score,
            salience_class=next_class,
            metadata_json=next_metadata,
        )
        if updated_entity is None:
            return None
        salience_state = _salience_state_payload(
            score=updated_entity.get("salience_score"),
            salience_class=updated_entity.get("salience_class"),
            metadata=updated_entity.get("metadata"),
        )
        return {
            "target_kind": normalized_target_kind,
            "target_id": target_id,
            "resolved_target": {
                "entity_id": updated_entity["entity_id"],
            },
            "pin_action": normalized_pin_action,
            "salience_state": salience_state,
            "updated_at": salience_state["updated_at"],
        }

    episode = await get_episode_for_project(
        session,
        project_id=project_id,
        episode_id=target_id,
    )
    if episode is None:
        return None
    episode_metadata = _metadata_dict(episode.get("metadata_json"))
    next_score, next_class, next_metadata = _apply_pin_action(
        current_score=episode.get("salience_score"),
        current_class=episode.get("salience_class"),
        metadata=episode_metadata,
        pin_action=normalized_pin_action,
        reason=reason,
    )
    updated_episode = await update_episode_salience(
        session,
        project_id=project_id,
        episode_id=target_id,
        salience_score=next_score,
        salience_class=next_class,
        metadata_json=next_metadata,
    )
    if updated_episode is None:
        return None
    await _sync_episode_search_doc(
        session,
        project_id=project_id,
        episode_id=target_id,
        content=str(updated_episode.get("content") or updated_episode.get("summary") or ""),
        reference_time=updated_episode.get("reference_time").isoformat()
        if hasattr(updated_episode.get("reference_time"), "isoformat")
        else updated_episode.get("reference_time"),
        summary=updated_episode.get("summary"),
        metadata=_metadata_dict(updated_episode.get("metadata_json")),
        salience_score=updated_episode.get("salience_score"),
        salience_class=updated_episode.get("salience_class"),
    )
    await ensure_projection_watermark(
        session,
        project_id=project_id,
        projection_name="memory_search_docs",
        watermark=1,
    )
    salience_state = _salience_state_payload(
        score=updated_episode.get("salience_score"),
        salience_class=updated_episode.get("salience_class"),
        metadata=_metadata_dict(updated_episode.get("metadata_json")),
    )
    return {
        "target_kind": normalized_target_kind,
        "target_id": target_id,
        "resolved_target": {
            "episode_id": target_id,
        },
        "pin_action": normalized_pin_action,
        "salience_state": salience_state,
        "updated_at": salience_state["updated_at"],
    }


async def merge_canonical_entities(
    session: AsyncSession,
    *,
    project_id: str,
    operation_id: str | None,
    resolution_event_id: str,
    target_entity_id: str,
    source_entity_ids: list[str],
    reason: str | None,
) -> dict:
    return await repo_merge_entities(
        session,
        project_id=project_id,
        resolution_event_id=resolution_event_id,
        operation_id=operation_id,
        target_entity_id=target_entity_id,
        source_entity_ids=source_entity_ids,
        reason=reason,
    )


async def split_canonical_entity(
    session: AsyncSession,
    *,
    project_id: str,
    operation_id: str | None,
    resolution_event_id: str,
    source_entity_id: str,
    partitions: list[dict],
    reason: str | None,
) -> dict:
    normalized_partitions: list[dict] = []
    for partition in partitions:
        normalized_partition = dict(partition)
        if normalized_partition.get("new_entity"):
            new_entity = dict(normalized_partition["new_entity"])
            new_entity.setdefault("display_name", new_entity.get("canonical_name"))
            new_entity["entity_id"] = new_id("ent")
            normalized_partition["new_entity"] = new_entity
        normalized_partitions.append(normalized_partition)
    return await repo_split_entity(
        session,
        project_id=project_id,
        resolution_event_id=resolution_event_id,
        operation_id=operation_id,
        source_entity_id=source_entity_id,
        partitions=normalized_partitions,
        reason=reason,
    )
