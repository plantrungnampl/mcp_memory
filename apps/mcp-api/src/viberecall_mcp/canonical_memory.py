from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.ids import new_id
from viberecall_mcp.repositories.canonical_memory import (
    add_entity_alias,
    create_fact_group,
    create_provenance_link,
    delete_episode_canonical_memory,
    ensure_projection_watermark,
    ensure_relation_type,
    get_current_fact_by_version_or_group,
    insert_fact_version,
    list_current_facts as repo_list_current_facts,
    list_fact_lineage,
    list_fact_provenance,
    natural_key_hash,
    search_memory_docs,
    set_current_fact_version,
    supersede_current_fact_version,
    upsert_entity,
    upsert_memory_search_doc,
)


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


@dataclass(slots=True)
class CanonicalSaveResult:
    observation_doc_id: str
    fact_group_id: str
    fact_version_id: str
    entities: list[dict]


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

    search_payload = {
        "kind": "fact",
        "fact": {
            "id": fact_version_id,
            "fact_version_id": fact_version_id,
            "fact_group_id": fact_group_id,
            "text": statement,
            "statement": statement,
            "valid_at": reference_time,
            "invalid_at": None,
        },
        "entities": entities,
        "provenance": {
            "episode_ids": [episode_id],
            "reference_time": reference_time,
            "ingested_at": None,
        },
        "summary": summary,
    }
    episode_doc_id = f"episode:{episode_id}"
    await upsert_memory_search_doc(
        session,
        doc_id=episode_doc_id,
        project_id=project_id,
        doc_kind="episode",
        source_id=episode_id,
        title=summary or statement[:80],
        body=statement,
        filters=metadata,
        rank_features={
            "kind": "episode",
            "episode": {
                "episode_id": episode_id,
                "reference_time": reference_time,
                "summary": summary,
                "metadata": metadata,
            }
        },
    )
    await upsert_memory_search_doc(
        session,
        doc_id=doc_id,
        project_id=project_id,
        doc_kind="fact",
        source_id=fact_version_id,
        title=summary or statement[:80],
        body=" ".join([statement] + [entity["name"] for entity in entities]),
        filters={
            "tags": metadata.get("tags") or [],
            "files": metadata.get("files") or [],
            "repo": metadata.get("repo"),
            "entity_types": [entity["type"] for entity in entities],
        },
        rank_features=search_payload,
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
    limit: int,
    offset: int,
) -> list[dict]:
    rows = await search_memory_docs(
        session,
        project_id=project_id,
        query=query,
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
            results.append(result)
            continue
        episode_payload = payload.get("episode") if isinstance(payload, dict) else None
        if episode_payload is not None:
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
    await upsert_memory_search_doc(
        session,
        doc_id=f"fact:{new_fact_version_id}",
        project_id=project_id,
        doc_kind="fact",
        source_id=new_fact_version_id,
        title=_summary(statement) or statement[:80],
        body=statement,
        filters=merged_metadata,
        rank_features={
            "kind": "fact",
            "fact": {
                "id": new_fact_version_id,
                "fact_version_id": new_fact_version_id,
                "fact_group_id": fact_group_id,
                "text": statement,
                "statement": statement,
                "valid_at": effective_time,
                "invalid_at": None,
            },
            "entities": [
                {"entity_id": current["subject_entity_id"], "name": current["subject_entity_id"], "type": None},
            ],
            "provenance": {
                "episode_ids": [current.get("created_from_episode_id")] if current.get("created_from_episode_id") else [],
                "reference_time": effective_time,
                "ingested_at": None,
            },
            "summary": _summary(statement),
        },
    )
    return {
        "old_fact_version_id": expected_current_version_id,
        "new_fact_version_id": new_fact_version_id,
        "fact_group_id": fact_group_id,
        "committed_at": effective_time,
        "old_fact": {"id": expected_current_version_id, "invalid_at": effective_time},
        "new_fact": {"id": new_fact_version_id, "valid_at": effective_time},
    }
