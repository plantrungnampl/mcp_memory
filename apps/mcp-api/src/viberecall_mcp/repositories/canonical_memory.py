from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


def _json(value: dict | list | None) -> str:
    if value is None:
        payload: dict | list = {}
    else:
        payload = value
    return json.dumps(payload, default=str)


def _coerce_timestamptz(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _fact_payload_from_row(row: dict) -> dict:
    metadata = row.get("metadata_json")
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    value_json = row.get("value_json")
    if isinstance(value_json, str):
        value_json = json.loads(value_json)
    return {
        "fact_version_id": row["fact_version_id"],
        "fact_group_id": row["fact_group_id"],
        "statement": row["statement"],
        "normalized_statement": row["normalized_statement"],
        "subject_entity_id": row["subject_entity_id"],
        "relation_type_id": row["relation_type_id"],
        "object_entity_id": row.get("object_entity_id"),
        "value_json": value_json,
        "valid_from": _iso(row.get("valid_from")),
        "valid_to": _iso(row.get("valid_to")),
        "recorded_at": _iso(row.get("recorded_at")),
        "superseded_at": _iso(row.get("superseded_at")),
        "status": row["status"],
        "confidence": float(row["confidence"]) if isinstance(row.get("confidence"), Decimal) else row.get("confidence"),
        "salience_score": float(row["salience_score"])
        if isinstance(row.get("salience_score"), Decimal)
        else row.get("salience_score"),
        "trust_class": row["trust_class"],
        "created_from_episode_id": row.get("created_from_episode_id"),
        "replaces_fact_version_id": row.get("replaces_fact_version_id"),
        "metadata": metadata or {},
    }


async def ensure_projection_watermark(
    session: AsyncSession,
    *,
    project_id: str,
    projection_name: str,
    watermark: int,
) -> None:
    await session.execute(
        text(
            """
            insert into projection_watermarks (project_id, projection_name, watermark)
            values (:project_id, :projection_name, :watermark)
            on conflict (project_id, projection_name)
            do update set
                watermark = greatest(projection_watermarks.watermark, excluded.watermark),
                updated_at = now()
            """
        ),
        {
            "project_id": project_id,
            "projection_name": projection_name,
            "watermark": watermark,
        },
    )


async def upsert_entity(
    session: AsyncSession,
    *,
    entity_id: str,
    project_id: str,
    entity_kind: str,
    canonical_name: str,
    display_name: str,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into entities (
                entity_id, project_id, entity_kind, canonical_name, display_name, metadata_json
            ) values (
                :entity_id, :project_id, :entity_kind, :canonical_name, :display_name, cast(:metadata_json as jsonb)
            )
            on conflict (entity_id)
            do update set
                entity_kind = excluded.entity_kind,
                canonical_name = excluded.canonical_name,
                display_name = excluded.display_name,
                metadata_json = entities.metadata_json || excluded.metadata_json,
                updated_at = now()
            """
        ),
        {
            "entity_id": entity_id,
            "project_id": project_id,
            "entity_kind": entity_kind,
            "canonical_name": canonical_name,
            "display_name": display_name,
            "metadata_json": _json(metadata),
        },
    )


async def add_entity_alias(
    session: AsyncSession,
    *,
    project_id: str,
    entity_id: str,
    alias_type: str,
    alias_value: str,
    confidence: float | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into entity_aliases (
                project_id, entity_id, alias_type, alias_value, confidence, active
            ) values (
                :project_id, :entity_id, :alias_type, :alias_value, :confidence, true
            )
            on conflict (project_id, alias_type, alias_value)
            where active = true
            do update set
                entity_id = excluded.entity_id,
                confidence = excluded.confidence,
                active = true
            """
        ),
        {
            "project_id": project_id,
            "entity_id": entity_id,
            "alias_type": alias_type,
            "alias_value": alias_value,
            "confidence": confidence,
        },
    )


async def ensure_relation_type(
    session: AsyncSession,
    *,
    relation_type_id: str,
    name: str,
    inverse_name: str,
    relation_class: str,
    is_transitive: bool = False,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into relation_types (
                relation_type_id, name, inverse_name, relation_class, is_transitive, metadata_json
            ) values (
                :relation_type_id, :name, :inverse_name, :relation_class, :is_transitive, cast(:metadata_json as jsonb)
            )
            on conflict (relation_type_id)
            do update set
                name = excluded.name,
                inverse_name = excluded.inverse_name,
                relation_class = excluded.relation_class,
                is_transitive = excluded.is_transitive,
                metadata_json = relation_types.metadata_json || excluded.metadata_json
            """
        ),
        {
            "relation_type_id": relation_type_id,
            "name": name,
            "inverse_name": inverse_name,
            "relation_class": relation_class,
            "is_transitive": is_transitive,
            "metadata_json": _json(metadata),
        },
    )


async def create_fact_group(
    session: AsyncSession,
    *,
    fact_group_id: str,
    project_id: str,
    natural_key_hash: str | None,
) -> None:
    await session.execute(
        text(
            """
            insert into fact_groups (fact_group_id, project_id, natural_key_hash)
            values (:fact_group_id, :project_id, :natural_key_hash)
            """
        ),
        {
            "fact_group_id": fact_group_id,
            "project_id": project_id,
            "natural_key_hash": natural_key_hash,
        },
    )


async def insert_fact_version(
    session: AsyncSession,
    *,
    fact_version_id: str,
    fact_group_id: str,
    project_id: str,
    fact_shape: str,
    subject_entity_id: str,
    relation_type_id: str,
    statement: str,
    normalized_statement: str,
    object_entity_id: str | None = None,
    value_json: dict | None = None,
    valid_from: str | datetime | None = None,
    valid_to: str | datetime | None = None,
    status: str = "CURRENT",
    confidence: float | None = None,
    salience_score: float | None = None,
    trust_class: str = "observed",
    created_from_episode_id: str | None = None,
    replaces_fact_version_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into fact_versions (
                fact_version_id, fact_group_id, project_id, fact_shape,
                subject_entity_id, relation_type_id, object_entity_id,
                value_json, statement, normalized_statement,
                valid_from, valid_to, status, confidence, salience_score,
                trust_class, created_from_episode_id, replaces_fact_version_id, metadata_json
            ) values (
                :fact_version_id, :fact_group_id, :project_id, :fact_shape,
                :subject_entity_id, :relation_type_id, :object_entity_id,
                cast(:value_json as jsonb), :statement, :normalized_statement,
                :valid_from, :valid_to, :status, :confidence, :salience_score,
                :trust_class, :created_from_episode_id, :replaces_fact_version_id, cast(:metadata_json as jsonb)
            )
            """
        ),
        {
            "fact_version_id": fact_version_id,
            "fact_group_id": fact_group_id,
            "project_id": project_id,
            "fact_shape": fact_shape,
            "subject_entity_id": subject_entity_id,
            "relation_type_id": relation_type_id,
            "object_entity_id": object_entity_id,
            "value_json": _json(value_json),
            "statement": statement,
            "normalized_statement": normalized_statement,
            "valid_from": _coerce_timestamptz(valid_from),
            "valid_to": _coerce_timestamptz(valid_to),
            "status": status,
            "confidence": confidence,
            "salience_score": salience_score,
            "trust_class": trust_class,
            "created_from_episode_id": created_from_episode_id,
            "replaces_fact_version_id": replaces_fact_version_id,
            "metadata_json": _json(metadata),
        },
    )


async def set_current_fact_version(
    session: AsyncSession,
    *,
    fact_group_id: str,
    fact_version_id: str,
) -> None:
    await session.execute(
        text(
            """
            update fact_groups
            set current_fact_version_id = :fact_version_id,
                updated_at = now()
            where fact_group_id = :fact_group_id
            """
        ),
        {
            "fact_group_id": fact_group_id,
            "fact_version_id": fact_version_id,
        },
    )


async def supersede_current_fact_version(
    session: AsyncSession,
    *,
    fact_group_id: str,
    expected_current_version_id: str,
    superseded_at: str | datetime | None = None,
) -> bool:
    result = await session.execute(
        text(
            """
            update fact_versions
            set status = 'SUPERSEDED',
                superseded_at = coalesce(:superseded_at, now())
            where fact_group_id = :fact_group_id
              and fact_version_id = :expected_current_version_id
              and status = 'CURRENT'
              and superseded_at is null
            """
        ),
        {
            "fact_group_id": fact_group_id,
            "expected_current_version_id": expected_current_version_id,
            "superseded_at": _coerce_timestamptz(superseded_at),
        },
    )
    return (result.rowcount or 0) == 1


async def create_provenance_link(
    session: AsyncSession,
    *,
    project_id: str,
    source_kind: str,
    source_id: str,
    target_kind: str,
    target_id: str,
    role: str,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into provenance_links (
                project_id, source_kind, source_id, target_kind, target_id, role, metadata_json
            ) values (
                :project_id, :source_kind, :source_id, :target_kind, :target_id, :role, cast(:metadata_json as jsonb)
            )
            """
        ),
        {
            "project_id": project_id,
            "source_kind": source_kind,
            "source_id": source_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "role": role,
            "metadata_json": _json(metadata),
        },
    )


async def upsert_memory_search_doc(
    session: AsyncSession,
    *,
    doc_id: str,
    project_id: str,
    doc_kind: str,
    source_id: str,
    title: str,
    body: str,
    filters: dict | None = None,
    rank_features: dict | None = None,
    visible_from_watermark: int = 0,
) -> None:
    await session.execute(
        text(
            """
            insert into memory_search_docs (
                doc_id, project_id, doc_kind, source_id, title, body,
                filters_json, rank_features_json, visible_from_watermark
            ) values (
                :doc_id, :project_id, :doc_kind, :source_id, :title, :body,
                cast(:filters_json as jsonb), cast(:rank_features_json as jsonb), :visible_from_watermark
            )
            on conflict (doc_id)
            do update set
                title = excluded.title,
                body = excluded.body,
                filters_json = excluded.filters_json,
                rank_features_json = excluded.rank_features_json,
                hidden_at_watermark = null,
                updated_at = now()
            """
        ),
        {
            "doc_id": doc_id,
            "project_id": project_id,
            "doc_kind": doc_kind,
            "source_id": source_id,
            "title": title,
            "body": body,
            "filters_json": _json(filters),
            "rank_features_json": _json(rank_features),
            "visible_from_watermark": visible_from_watermark,
        },
    )


async def list_current_facts(
    session: AsyncSession,
    *,
    project_id: str,
    filters: dict | None,
    limit: int,
    offset: int,
) -> list[dict]:
    filters = filters or {}
    clauses = ["fv.project_id = :project_id", "fv.status = 'CURRENT'", "fv.superseded_at is null"]
    params: dict[str, Any] = {"project_id": project_id, "limit": limit, "offset": offset}
    if filters.get("valid_at"):
        clauses.append("(fv.valid_from is null or fv.valid_from <= cast(:valid_at as timestamptz))")
        clauses.append("(fv.valid_to is null or fv.valid_to > cast(:valid_at as timestamptz))")
        params["valid_at"] = _coerce_timestamptz(filters.get("valid_at"))
    if filters.get("tag"):
        clauses.append("coalesce(fv.metadata_json->'tags', '[]'::jsonb) ? :tag")
        params["tag"] = str(filters["tag"])
    if filters.get("entity_type"):
        clauses.append(
            """
            exists (
              select 1
              from entities e
              where e.project_id = fv.project_id
                and e.entity_id in (fv.subject_entity_id, coalesce(fv.object_entity_id, ''))
                and e.entity_kind = :entity_type
            )
            """
        )
        params["entity_type"] = str(filters["entity_type"])

    result = await session.execute(
        text(
            f"""
            select fv.fact_version_id, fv.fact_group_id, fv.statement, fv.normalized_statement,
                   fv.subject_entity_id, fv.relation_type_id, fv.object_entity_id, fv.value_json,
                   fv.valid_from, fv.valid_to, fv.recorded_at, fv.superseded_at, fv.status,
                   fv.confidence, fv.salience_score, fv.trust_class, fv.created_from_episode_id,
                   fv.replaces_fact_version_id, fv.metadata_json
            from fact_versions fv
            where {' and '.join(clauses)}
            order by coalesce(fv.valid_from, fv.recorded_at) desc, fv.fact_version_id desc
            limit :limit offset :offset
            """
        ),
        params,
    )
    return [_fact_payload_from_row(dict(row)) for row in result.mappings().all()]


async def search_memory_docs(
    session: AsyncSession,
    *,
    project_id: str,
    query: str,
    limit: int,
    offset: int,
) -> list[dict]:
    normalized = str(query).strip()
    if not normalized:
        return []
    result = await session.execute(
        text(
            """
            select doc_id, doc_kind, source_id, filters_json, rank_features_json,
                   ts_rank_cd(tsv, websearch_to_tsquery('simple', :query)) as score
            from memory_search_docs
            where project_id = :project_id
              and hidden_at_watermark is null
              and (
                doc_kind <> 'fact'
                or exists (
                  select 1
                  from fact_versions fv
                  where fv.fact_version_id = memory_search_docs.source_id
                    and fv.project_id = memory_search_docs.project_id
                    and fv.status = 'CURRENT'
                    and fv.superseded_at is null
                )
              )
              and (
                tsv @@ websearch_to_tsquery('simple', :query)
                or body ilike :like_query
                or title ilike :like_query
              )
            order by score desc, updated_at desc, doc_id desc
            limit :limit offset :offset
            """
        ),
        {
            "project_id": project_id,
            "query": normalized,
            "like_query": f"%{normalized}%",
            "limit": limit,
            "offset": offset,
        },
    )
    rows = []
    for row in result.mappings().all():
        payload = dict(row)
        for key in ("filters_json", "rank_features_json"):
            if isinstance(payload.get(key), str):
                payload[key] = json.loads(payload[key])
        if isinstance(payload.get("score"), Decimal):
            payload["score"] = float(payload["score"])
        rows.append(payload)
    return rows


async def get_current_fact_by_version_or_group(
    session: AsyncSession,
    *,
    project_id: str,
    fact_version_id: str | None = None,
    fact_group_id: str | None = None,
) -> dict | None:
    if fact_version_id is None and fact_group_id is None:
        raise ValueError("fact_version_id or fact_group_id is required")
    clauses = ["fv.project_id = :project_id", "fv.status = 'CURRENT'", "fv.superseded_at is null"]
    params: dict[str, Any] = {"project_id": project_id}
    if fact_version_id is not None:
        clauses.append("(fv.fact_version_id = :fact_version_id or fv.fact_group_id = (select fact_group_id from fact_versions where fact_version_id = :fact_version_id))")
        params["fact_version_id"] = fact_version_id
    if fact_group_id is not None:
        clauses.append("fv.fact_group_id = :fact_group_id")
        params["fact_group_id"] = fact_group_id
    result = await session.execute(
        text(
            f"""
            select fv.fact_version_id, fv.fact_group_id, fv.statement, fv.normalized_statement,
                   fv.subject_entity_id, fv.relation_type_id, fv.object_entity_id, fv.value_json,
                   fv.valid_from, fv.valid_to, fv.recorded_at, fv.superseded_at, fv.status,
                   fv.confidence, fv.salience_score, fv.trust_class, fv.created_from_episode_id,
                   fv.replaces_fact_version_id, fv.metadata_json
            from fact_versions fv
            where {' and '.join(clauses)}
            order by fv.recorded_at desc
            limit 1
            """
        ),
        params,
    )
    row = result.mappings().first()
    return _fact_payload_from_row(dict(row)) if row else None


async def list_fact_lineage(
    session: AsyncSession,
    *,
    project_id: str,
    fact_group_id: str,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select fv.fact_version_id, fv.fact_group_id, fv.statement, fv.normalized_statement,
                   fv.subject_entity_id, fv.relation_type_id, fv.object_entity_id, fv.value_json,
                   fv.valid_from, fv.valid_to, fv.recorded_at, fv.superseded_at, fv.status,
                   fv.confidence, fv.salience_score, fv.trust_class, fv.created_from_episode_id,
                   fv.replaces_fact_version_id, fv.metadata_json
            from fact_versions fv
            where fv.project_id = :project_id
              and fv.fact_group_id = :fact_group_id
            order by fv.recorded_at desc, fv.fact_version_id desc
            """
        ),
        {
            "project_id": project_id,
            "fact_group_id": fact_group_id,
        },
    )
    return [_fact_payload_from_row(dict(row)) for row in result.mappings().all()]


async def list_fact_provenance(
    session: AsyncSession,
    *,
    project_id: str,
    fact_group_id: str,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select provenance_id, source_kind, source_id, target_kind, target_id, role, metadata_json, created_at
            from provenance_links
            where project_id = :project_id
              and (
                (target_kind = 'fact_group' and target_id = :fact_group_id)
                or (target_kind = 'fact_version' and target_id in (
                  select fact_version_id from fact_versions where fact_group_id = :fact_group_id
                ))
              )
            order by created_at desc, provenance_id desc
            """
        ),
        {
            "project_id": project_id,
            "fact_group_id": fact_group_id,
        },
    )
    rows = []
    for row in result.mappings().all():
        payload = dict(row)
        metadata = payload.get("metadata_json")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        payload["metadata"] = metadata or {}
        payload.pop("metadata_json", None)
        payload["created_at"] = _iso(payload.get("created_at"))
        rows.append(payload)
    return rows


def natural_key_hash(*, project_id: str, statement: str, metadata: dict | None) -> str:
    payload = json.dumps(
        {
            "project_id": project_id,
            "statement": _normalize_text(statement),
            "metadata": metadata or {},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


async def delete_episode_canonical_memory(
    session: AsyncSession,
    *,
    project_id: str,
    episode_id: str,
    commit: bool = True,
) -> dict:
    fact_group_rows = await session.execute(
        text(
            """
            select distinct fact_group_id
            from fact_versions
            where project_id = :project_id
              and created_from_episode_id = :episode_id
            """
        ),
        {
            "project_id": project_id,
            "episode_id": episode_id,
        },
    )
    fact_group_ids = [str(row["fact_group_id"]) for row in fact_group_rows.mappings().all()]
    fact_version_ids: list[str] = []
    if fact_group_ids:
        fact_version_rows = await session.execute(
            text(
                """
                select fact_version_id
                from fact_versions
                where project_id = :project_id
                  and fact_group_id in :fact_group_ids
                """
            ).bindparams(bindparam("fact_group_ids", expanding=True)),
            {
                "project_id": project_id,
                "fact_group_ids": fact_group_ids,
            },
        )
        fact_version_ids = [str(row["fact_version_id"]) for row in fact_version_rows.mappings().all()]

    search_docs_deleted = 0
    if fact_version_ids:
        delete_fact_docs = await session.execute(
            text(
                """
                delete from memory_search_docs
                where project_id = :project_id
                  and source_id in :fact_version_ids
                """
            ).bindparams(bindparam("fact_version_ids", expanding=True)),
            {
                "project_id": project_id,
                "fact_version_ids": fact_version_ids,
            },
        )
        search_docs_deleted += delete_fact_docs.rowcount or 0

    delete_episode_doc = await session.execute(
        text(
            """
            delete from memory_search_docs
            where project_id = :project_id
              and doc_kind = 'episode'
              and source_id = :episode_id
            """
        ),
        {
            "project_id": project_id,
            "episode_id": episode_id,
        },
    )
    search_docs_deleted += delete_episode_doc.rowcount or 0

    provenance_deleted = 0
    delete_episode_provenance = await session.execute(
        text(
            """
            delete from provenance_links
            where project_id = :project_id
              and source_kind = 'episode'
              and source_id = :episode_id
            """
        ),
        {
            "project_id": project_id,
            "episode_id": episode_id,
        },
    )
    provenance_deleted += delete_episode_provenance.rowcount or 0

    if fact_version_ids:
        delete_version_provenance = await session.execute(
            text(
                """
                delete from provenance_links
                where project_id = :project_id
                  and (
                    (target_kind = 'fact_version' and target_id in :fact_version_ids)
                    or (source_kind = 'fact_version' and source_id in :fact_version_ids)
                  )
                """
            ).bindparams(bindparam("fact_version_ids", expanding=True)),
            {
                "project_id": project_id,
                "fact_version_ids": fact_version_ids,
            },
        )
        provenance_deleted += delete_version_provenance.rowcount or 0

    if fact_group_ids:
        delete_group_provenance = await session.execute(
            text(
                """
                delete from provenance_links
                where project_id = :project_id
                  and target_kind = 'fact_group'
                  and target_id in :fact_group_ids
                """
            ).bindparams(bindparam("fact_group_ids", expanding=True)),
            {
                "project_id": project_id,
                "fact_group_ids": fact_group_ids,
            },
        )
        provenance_deleted += delete_group_provenance.rowcount or 0

    fact_versions_deleted = 0
    if fact_group_ids:
        delete_versions = await session.execute(
            text(
                """
                delete from fact_versions
                where project_id = :project_id
                  and fact_group_id in :fact_group_ids
                """
            ).bindparams(bindparam("fact_group_ids", expanding=True)),
            {
                "project_id": project_id,
                "fact_group_ids": fact_group_ids,
            },
        )
        fact_versions_deleted = delete_versions.rowcount or 0

    fact_groups_deleted = 0
    if fact_group_ids:
        delete_groups = await session.execute(
            text(
                """
                delete from fact_groups
                where project_id = :project_id
                  and fact_group_id in :fact_group_ids
                """
            ).bindparams(bindparam("fact_group_ids", expanding=True)),
            {
                "project_id": project_id,
                "fact_group_ids": fact_group_ids,
            },
        )
        fact_groups_deleted = delete_groups.rowcount or 0

    if commit:
        await session.commit()
    return {
        "fact_group_ids": fact_group_ids,
        "fact_version_ids": fact_version_ids,
        "fact_groups_deleted": fact_groups_deleted,
        "fact_versions_deleted": fact_versions_deleted,
        "provenance_deleted": provenance_deleted,
        "search_docs_deleted": search_docs_deleted,
    }
