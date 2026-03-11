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


def _parse_json(value: Any) -> dict | list | None:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _summary_snippet(value: str | None, *, limit: int = 160) -> str | None:
    if value is None:
        return None
    snippet = " ".join(str(value).split()).strip()
    if not snippet:
        return None
    return snippet[:limit]


def _unresolved_mention_payload_from_row(row: dict) -> dict:
    context = _parse_json(row.get("context_json")) or {}
    return {
        "mention_id": row["mention_id"],
        "project_id": row["project_id"],
        "mention_text": row["mention_text"],
        "observed_kind": row.get("observed_kind"),
        "repo_scope": row.get("repo_scope"),
        "context": context,
        "status": row["status"],
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


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
        "salience_class": row.get("salience_class"),
        "trust_class": row["trust_class"],
        "created_from_episode_id": row.get("created_from_episode_id"),
        "replaces_fact_version_id": row.get("replaces_fact_version_id"),
        "metadata": metadata or {},
    }


def _entity_payload_from_row(row: dict) -> dict:
    metadata = _parse_json(row.get("metadata_json")) or {}
    aliases = row.get("aliases") or []
    if isinstance(aliases, str):
        aliases = json.loads(aliases)
    latest_supporting_fact = row.get("latest_supporting_fact") or {}
    if isinstance(latest_supporting_fact, str):
        latest_supporting_fact = json.loads(latest_supporting_fact)
    confidence = row.get("max_confidence")
    salience = row.get("max_salience_score")
    entity_salience_score = row.get("salience_score")
    return {
        "entity_id": row["entity_id"],
        "name": row["display_name"],
        "canonical_name": row["canonical_name"],
        "display_name": row["display_name"],
        "type": row["entity_kind"],
        "entity_kind": row["entity_kind"],
        "aliases": [str(alias) for alias in aliases if alias],
        "summary_snippet": _summary_snippet(row.get("latest_supporting_statement")),
        "support_count": int(row.get("support_count") or 0),
        "latest_support_time": _iso(row.get("latest_support_time")),
        "latest_supporting_fact": latest_supporting_fact or None,
        "confidence": float(confidence) if isinstance(confidence, Decimal) else confidence,
        "salience": float(salience) if isinstance(salience, Decimal) else salience,
        "salience_score": float(entity_salience_score)
        if isinstance(entity_salience_score, Decimal)
        else entity_salience_score,
        "salience_class": row.get("salience_class"),
        "state": row.get("state"),
        "metadata": metadata,
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
    salience_score: float | None = None,
    salience_class: str | None = None,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into entities (
                entity_id, project_id, entity_kind, canonical_name, display_name,
                salience_score, salience_class, metadata_json
            ) values (
                :entity_id, :project_id, :entity_kind, :canonical_name, :display_name,
                coalesce(:salience_score, 0.5), coalesce(:salience_class, 'WARM'),
                cast(:metadata_json as jsonb)
            )
            on conflict (entity_id)
            do update set
                entity_kind = excluded.entity_kind,
                canonical_name = excluded.canonical_name,
                display_name = excluded.display_name,
                salience_score = coalesce(excluded.salience_score, entities.salience_score),
                salience_class = coalesce(excluded.salience_class, entities.salience_class),
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
            "salience_score": salience_score,
            "salience_class": salience_class,
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
    salience_class: str = "WARM",
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
                valid_from, valid_to, status, confidence, salience_score, salience_class,
                trust_class, created_from_episode_id, replaces_fact_version_id, metadata_json
            ) values (
                :fact_version_id, :fact_group_id, :project_id, :fact_shape,
                :subject_entity_id, :relation_type_id, :object_entity_id,
                cast(:value_json as jsonb), :statement, :normalized_statement,
                :valid_from, :valid_to, :status, :confidence, :salience_score, :salience_class,
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
            "salience_class": salience_class,
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


async def get_memory_search_doc(
    session: AsyncSession,
    *,
    project_id: str,
    doc_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select doc_id, project_id, doc_kind, source_id, title, body,
                   filters_json, rank_features_json, visible_from_watermark,
                   hidden_at_watermark, updated_at
            from memory_search_docs
            where project_id = :project_id
              and doc_id = :doc_id
            """
        ),
        {
            "project_id": project_id,
            "doc_id": doc_id,
        },
    )
    row = result.mappings().first()
    if row is None:
        return None
    payload = dict(row)
    payload["filters_json"] = _parse_json(payload.get("filters_json")) or {}
    payload["rank_features_json"] = _parse_json(payload.get("rank_features_json")) or {}
    payload["updated_at"] = _iso(payload.get("updated_at"))
    return payload


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
                   fv.confidence, fv.salience_score, fv.salience_class, fv.trust_class, fv.created_from_episode_id,
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
    filters: dict | None,
    sort: str,
    limit: int,
    offset: int,
) -> list[dict]:
    normalized = str(query).strip()
    if not normalized:
        return []
    filters = filters or {}
    sort_mode = str(sort or "RELEVANCE").upper()
    sort_clause = """
            exact_match_rank desc,
            score desc,
            salience_class_rank desc,
            effective_salience_score desc,
            effective_time desc,
            doc_id desc
    """
    if sort_mode in {"RECENCY", "TIME"}:
        sort_clause = """
            exact_match_rank desc,
            effective_time desc,
            salience_class_rank desc,
            effective_salience_score desc,
            score desc,
            doc_id desc
        """

    clauses = [
        "memory_search_docs.project_id = :project_id",
        "memory_search_docs.hidden_at_watermark is null",
        """
        (
          memory_search_docs.doc_kind <> 'fact'
          or exists (
            select 1
            from fact_versions current_fact
            where current_fact.fact_version_id = memory_search_docs.source_id
              and current_fact.project_id = memory_search_docs.project_id
              and current_fact.status = 'CURRENT'
              and current_fact.superseded_at is null
          )
        )
        """,
        """
        (
          memory_search_docs.tsv @@ websearch_to_tsquery('simple', :query)
          or memory_search_docs.body ilike :like_query
          or memory_search_docs.title ilike :like_query
        )
        """,
    ]
    params: dict[str, Any] = {
        "project_id": project_id,
        "query": normalized,
        "query_exact": normalized.lower(),
        "like_query": f"%{normalized}%",
        "limit": limit,
        "offset": offset,
    }
    if filters.get("salience_classes"):
        clauses.append(
            """
            coalesce(
              fv.salience_class,
              ep.salience_class,
              memory_search_docs.rank_features_json #>> '{fact,salience_class}',
              memory_search_docs.rank_features_json #>> '{episode,salience_class}',
              'WARM'
            ) in :salience_classes
            """
        )
        params["salience_classes"] = [str(item).upper() for item in (filters.get("salience_classes") or [])]
    statement = text(
        f"""
        select
               memory_search_docs.doc_id,
               memory_search_docs.doc_kind,
               memory_search_docs.source_id,
               memory_search_docs.filters_json,
               memory_search_docs.rank_features_json,
               ts_rank_cd(memory_search_docs.tsv, websearch_to_tsquery('simple', :query)) as score,
               case
                 when lower(memory_search_docs.title) = :query_exact
                   or lower(memory_search_docs.body) = :query_exact
                   or lower(coalesce(memory_search_docs.rank_features_json #>> '{{fact,text}}', '')) = :query_exact
                   or lower(coalesce(memory_search_docs.rank_features_json #>> '{{fact,statement}}', '')) = :query_exact
                   or lower(coalesce(memory_search_docs.rank_features_json #>> '{{episode,summary}}', '')) = :query_exact
                 then 1
                 else 0
               end as exact_match_rank,
               coalesce(
                 fv.salience_score,
                 ep.salience_score,
                 cast(memory_search_docs.rank_features_json #>> '{{fact,salience_score}}' as numeric),
                 cast(memory_search_docs.rank_features_json #>> '{{episode,salience_score}}' as numeric),
                 0.5
               ) as effective_salience_score,
               coalesce(
                 fv.salience_class,
                 ep.salience_class,
                 memory_search_docs.rank_features_json #>> '{{fact,salience_class}}',
                 memory_search_docs.rank_features_json #>> '{{episode,salience_class}}',
                 'WARM'
               ) as effective_salience_class,
               case
                 when coalesce(
                   fv.salience_class,
                   ep.salience_class,
                   memory_search_docs.rank_features_json #>> '{{fact,salience_class}}',
                   memory_search_docs.rank_features_json #>> '{{episode,salience_class}}',
                   'WARM'
                 ) = 'PINNED' then 5
                 when coalesce(
                   fv.salience_class,
                   ep.salience_class,
                   memory_search_docs.rank_features_json #>> '{{fact,salience_class}}',
                   memory_search_docs.rank_features_json #>> '{{episode,salience_class}}',
                   'WARM'
                 ) = 'HOT' then 4
                 when coalesce(
                   fv.salience_class,
                   ep.salience_class,
                   memory_search_docs.rank_features_json #>> '{{fact,salience_class}}',
                   memory_search_docs.rank_features_json #>> '{{episode,salience_class}}',
                   'WARM'
                 ) = 'WARM' then 3
                 when coalesce(
                   fv.salience_class,
                   ep.salience_class,
                   memory_search_docs.rank_features_json #>> '{{fact,salience_class}}',
                   memory_search_docs.rank_features_json #>> '{{episode,salience_class}}',
                   'WARM'
                 ) = 'COLD' then 2
                 when coalesce(
                   fv.salience_class,
                   ep.salience_class,
                   memory_search_docs.rank_features_json #>> '{{fact,salience_class}}',
                   memory_search_docs.rank_features_json #>> '{{episode,salience_class}}',
                   'WARM'
                 ) = 'ARCHIVED' then 1
                 else 0
               end as salience_class_rank,
               coalesce(fv.valid_from, fv.recorded_at, ep.reference_time, ep.ingested_at, memory_search_docs.updated_at) as effective_time
        from memory_search_docs
        left join fact_versions fv
          on fv.project_id = memory_search_docs.project_id
         and fv.fact_version_id = memory_search_docs.source_id
         and memory_search_docs.doc_kind = 'fact'
        left join episodes ep
          on ep.project_id = memory_search_docs.project_id
         and ep.episode_id = memory_search_docs.source_id
         and memory_search_docs.doc_kind = 'episode'
        where {' and '.join(clauses)}
        order by {sort_clause}
        limit :limit offset :offset
        """
    )
    if filters.get("salience_classes"):
        statement = statement.bindparams(bindparam("salience_classes", expanding=True))
    result = await session.execute(statement, params)
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


async def search_entities(
    session: AsyncSession,
    *,
    project_id: str,
    query: str,
    entity_kinds: list[str] | None,
    salience_classes: list[str] | None,
    limit: int,
) -> list[dict]:
    normalized = _normalize_text(str(query))
    if not normalized:
        return []

    clauses = ["e.project_id = :project_id", "e.state = 'ACTIVE'"]
    params: dict[str, Any] = {
        "project_id": project_id,
        "query_exact": normalized,
        "query_prefix": f"{normalized}%",
        "query_contains": f"%{normalized}%",
        "limit": limit,
    }
    if entity_kinds:
        clauses.append("e.entity_kind in :entity_kinds")
        params["entity_kinds"] = [str(item) for item in entity_kinds]
    if salience_classes:
        clauses.append("coalesce(e.salience_class, 'WARM') in :salience_classes")
        params["salience_classes"] = [str(item).upper() for item in salience_classes]

    query_stmt = text(
        f"""
            with candidate_entities as (
              select
                e.entity_id,
                e.project_id,
                e.entity_kind,
                e.canonical_name,
                e.display_name,
                e.salience_score,
                e.salience_class,
                e.state,
                e.metadata_json,
                min(
                  case
                    when lower(e.canonical_name) = :query_exact
                      or lower(e.display_name) = :query_exact
                      or lower(coalesce(ea.alias_value, '')) = :query_exact
                    then 0
                    when lower(e.canonical_name) like :query_prefix
                      or lower(e.display_name) like :query_prefix
                      or lower(coalesce(ea.alias_value, '')) like :query_prefix
                    then 1
                    when lower(e.canonical_name) like :query_contains
                      or lower(e.display_name) like :query_contains
                      or lower(coalesce(ea.alias_value, '')) like :query_contains
                    then 2
                    else 99
                  end
                ) as match_rank
              from entities e
              left join entity_aliases ea
                on ea.project_id = e.project_id
               and ea.entity_id = e.entity_id
               and ea.active = true
              where {' and '.join(clauses)}
              group by
                e.entity_id,
                e.project_id,
                e.entity_kind,
                e.canonical_name,
                e.display_name,
                e.salience_score,
                e.salience_class,
                e.state,
                e.metadata_json
              having min(
                case
                  when lower(e.canonical_name) = :query_exact
                    or lower(e.display_name) = :query_exact
                    or lower(coalesce(ea.alias_value, '')) = :query_exact
                  then 0
                  when lower(e.canonical_name) like :query_prefix
                    or lower(e.display_name) like :query_prefix
                    or lower(coalesce(ea.alias_value, '')) like :query_prefix
                  then 1
                  when lower(e.canonical_name) like :query_contains
                    or lower(e.display_name) like :query_contains
                    or lower(coalesce(ea.alias_value, '')) like :query_contains
                  then 2
                  else 99
                end
              ) < 99
            )
            select
              c.entity_id,
              c.entity_kind,
              c.canonical_name,
              c.display_name,
              c.salience_score,
              c.salience_class,
              c.state,
              c.metadata_json,
              c.match_rank,
              coalesce(alias_data.aliases, '[]'::jsonb) as aliases,
              coalesce(support_data.support_count, 0) as support_count,
              support_data.latest_support_time,
              support_data.latest_supporting_statement,
              support_data.latest_supporting_fact,
              support_data.max_confidence,
              support_data.max_salience_score
            from candidate_entities c
            left join lateral (
              select jsonb_agg(alias_value order by alias_value) as aliases
              from (
                select distinct ea.alias_value
                from entity_aliases ea
                where ea.project_id = c.project_id
                  and ea.entity_id = c.entity_id
                  and ea.active = true
              ) alias_rows
            ) alias_data on true
            left join lateral (
              select
                count(*)::int as support_count,
                max(coalesce(fv.valid_from, fv.recorded_at)) as latest_support_time,
                (
                  array_agg(
                    fv.statement
                    order by
                      coalesce(fv.valid_from, fv.recorded_at) desc,
                      fv.fact_version_id asc
                  )
                )[1] as latest_supporting_statement,
                (
                  jsonb_agg(
                    jsonb_build_object(
                      'fact_version_id', fv.fact_version_id,
                      'fact_group_id', fv.fact_group_id,
                      'statement', fv.statement
                    )
                    order by
                      coalesce(fv.valid_from, fv.recorded_at) desc,
                      fv.fact_version_id asc
                  )
                )->0 as latest_supporting_fact,
                max(fv.confidence) as max_confidence,
                max(fv.salience_score) as max_salience_score
              from fact_versions fv
              where fv.project_id = c.project_id
                and fv.status = 'CURRENT'
                and fv.superseded_at is null
                and (fv.subject_entity_id = c.entity_id or fv.object_entity_id = c.entity_id)
            ) support_data on true
            order by
              c.match_rank asc,
              coalesce(c.salience_score, 0.5) desc,
              case
                when coalesce(c.salience_class, 'WARM') = 'PINNED' then 5
                when coalesce(c.salience_class, 'WARM') = 'HOT' then 4
                when coalesce(c.salience_class, 'WARM') = 'WARM' then 3
                when coalesce(c.salience_class, 'WARM') = 'COLD' then 2
                when coalesce(c.salience_class, 'WARM') = 'ARCHIVED' then 1
                else 0
              end desc,
              coalesce(support_data.support_count, 0) desc,
              coalesce(support_data.max_salience_score, 0) desc,
              support_data.latest_support_time desc nulls last,
              c.display_name asc,
              c.entity_id asc
            limit :limit
            """
    )
    if entity_kinds:
        query_stmt = query_stmt.bindparams(bindparam("entity_kinds", expanding=True))
    if salience_classes:
        query_stmt = query_stmt.bindparams(bindparam("salience_classes", expanding=True))
    result = await session.execute(query_stmt, params)
    return [_entity_payload_from_row(dict(row)) for row in result.mappings().all()]


async def get_entity_redirect(
    session: AsyncSession,
    *,
    project_id: str,
    source_entity_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select source_entity_id, target_entity_id, resolution_event_id, created_at
            from entity_redirects
            where project_id = :project_id
              and source_entity_id = :source_entity_id
            """
        ),
        {
            "project_id": project_id,
            "source_entity_id": source_entity_id,
        },
    )
    row = result.mappings().first()
    if row is None:
        return None
    payload = dict(row)
    payload["created_at"] = _iso(payload.get("created_at"))
    return payload


async def resolve_entity_redirect(
    session: AsyncSession,
    *,
    project_id: str,
    entity_id: str,
) -> dict:
    requested_entity_id = str(entity_id)
    current_entity_id = requested_entity_id
    seen: set[str] = set()
    redirect_chain: list[dict] = []

    while True:
        if current_entity_id in seen:
            raise RuntimeError(f"Redirect cycle detected for entity_id={requested_entity_id}")
        seen.add(current_entity_id)
        redirect = await get_entity_redirect(
            session,
            project_id=project_id,
            source_entity_id=current_entity_id,
        )
        if redirect is None:
            break
        redirect_chain.append(redirect)
        current_entity_id = str(redirect["target_entity_id"])

    return {
        "requested_entity_id": requested_entity_id,
        "canonical_entity_id": current_entity_id,
        "redirect_chain": redirect_chain,
        "redirected": current_entity_id != requested_entity_id,
    }


async def get_entity_direct(
    session: AsyncSession,
    *,
    project_id: str,
    entity_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select
              e.entity_id,
              e.entity_kind,
              e.canonical_name,
              e.display_name,
              e.salience_score,
              e.salience_class,
              e.state,
              e.metadata_json,
              coalesce(
                (
                  select jsonb_agg(alias_value order by alias_value)
                  from (
                    select distinct ea.alias_value
                    from entity_aliases ea
                    where ea.project_id = e.project_id
                      and ea.entity_id = e.entity_id
                      and ea.active = true
                  ) alias_rows
                ),
                '[]'::jsonb
              ) as aliases
            from entities e
            where e.project_id = :project_id
              and e.entity_id = :entity_id
            """
        ),
        {
            "project_id": project_id,
            "entity_id": entity_id,
        },
    )
    row = result.mappings().first()
    if row is None:
        return None
    payload = _entity_payload_from_row(dict(row))
    payload["support_count"] = 0
    payload["latest_support_time"] = None
    payload["latest_supporting_fact"] = None
    payload["summary_snippet"] = None
    payload["confidence"] = None
    payload["salience"] = None
    return payload


async def get_entity(
    session: AsyncSession,
    *,
    project_id: str,
    entity_id: str,
) -> dict | None:
    resolution = await resolve_entity_redirect(
        session,
        project_id=project_id,
        entity_id=entity_id,
    )
    payload = await get_entity_direct(
        session,
        project_id=project_id,
        entity_id=str(resolution["canonical_entity_id"]),
    )
    if payload is None:
        return None
    if resolution["redirected"]:
        payload["requested_entity_id"] = str(resolution["requested_entity_id"])
        payload["canonical_entity_id"] = str(resolution["canonical_entity_id"])
        payload["redirect_chain"] = list(resolution["redirect_chain"])
    return payload


async def get_entities_by_ids(
    session: AsyncSession,
    *,
    project_id: str,
    entity_ids: list[str],
) -> dict[str, dict]:
    ordered_ids = [str(entity_id) for entity_id in entity_ids if str(entity_id).strip()]
    if not ordered_ids:
        return {}

    canonical_ids = list(
        dict.fromkeys(
            [
                str(
                    (
                        await resolve_entity_redirect(
                            session,
                            project_id=project_id,
                            entity_id=entity_id,
                        )
                    )["canonical_entity_id"]
                )
                for entity_id in ordered_ids
            ]
        )
    )
    query = text(
        """
        select
          e.entity_id,
          e.entity_kind,
          e.canonical_name,
          e.display_name,
          e.salience_score,
          e.salience_class,
          e.state,
          e.metadata_json,
          coalesce(
            (
              select jsonb_agg(alias_value order by alias_value)
              from (
                select distinct ea.alias_value
                from entity_aliases ea
                where ea.project_id = e.project_id
                  and ea.entity_id = e.entity_id
                  and ea.active = true
              ) alias_rows
            ),
            '[]'::jsonb
          ) as aliases
        from entities e
        where e.project_id = :project_id
          and e.entity_id in :entity_ids
        """
    ).bindparams(bindparam("entity_ids", expanding=True))
    result = await session.execute(
        query,
        {
            "project_id": project_id,
            "entity_ids": canonical_ids,
        },
    )

    payloads: dict[str, dict] = {}
    for row in result.mappings().all():
        payload = _entity_payload_from_row(dict(row))
        payload["support_count"] = 0
        payload["latest_support_time"] = None
        payload["latest_supporting_fact"] = None
        payload["summary_snippet"] = None
        payload["confidence"] = None
        payload["salience"] = None
        payloads[payload["entity_id"]] = payload
    return payloads


async def acquire_entity_resolution_locks(
    session: AsyncSession,
    *,
    project_id: str,
    entity_ids: list[str],
) -> None:
    for entity_id in sorted({str(item) for item in entity_ids if str(item).strip()}):
        await session.execute(
            text("select pg_advisory_xact_lock(hashtext(:project_id), hashtext(:entity_id))"),
            {
                "project_id": project_id,
                "entity_id": entity_id,
            },
        )


async def create_entity_resolution_event(
    session: AsyncSession,
    *,
    resolution_event_id: str,
    project_id: str,
    operation_id: str | None,
    event_kind: str,
    reason: str | None,
    canonical_target_entity_id: str | None,
    payload: dict | None,
) -> None:
    await session.execute(
        text(
            """
            insert into entity_resolution_events (
              resolution_event_id, project_id, operation_id, event_kind,
              reason, canonical_target_entity_id, payload_json
            ) values (
              :resolution_event_id, :project_id, :operation_id, :event_kind,
              :reason, :canonical_target_entity_id, cast(:payload_json as jsonb)
            )
            """
        ),
        {
            "resolution_event_id": resolution_event_id,
            "project_id": project_id,
            "operation_id": operation_id,
            "event_kind": event_kind,
            "reason": reason,
            "canonical_target_entity_id": canonical_target_entity_id,
            "payload_json": _json(payload),
        },
    )


async def create_entity_redirect(
    session: AsyncSession,
    *,
    project_id: str,
    source_entity_id: str,
    target_entity_id: str,
    resolution_event_id: str | None,
) -> None:
    await session.execute(
        text(
            """
            insert into entity_redirects (
              source_entity_id, project_id, target_entity_id, resolution_event_id
            ) values (
              :source_entity_id, :project_id, :target_entity_id, :resolution_event_id
            )
            on conflict (source_entity_id)
            do update set
              target_entity_id = excluded.target_entity_id,
              resolution_event_id = excluded.resolution_event_id
            """
        ),
        {
            "source_entity_id": source_entity_id,
            "project_id": project_id,
            "target_entity_id": target_entity_id,
            "resolution_event_id": resolution_event_id,
        },
    )


async def list_entity_alias_rows(
    session: AsyncSession,
    *,
    project_id: str,
    entity_id: str,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select alias_id, entity_id, alias_type, alias_value, confidence, active, created_at
            from entity_aliases
            where project_id = :project_id
              and entity_id = :entity_id
              and active = true
            order by alias_value asc, alias_type asc, alias_id asc
            """
        ),
        {
            "project_id": project_id,
            "entity_id": entity_id,
        },
    )
    rows = []
    for row in result.mappings().all():
        payload = dict(row)
        payload["created_at"] = _iso(payload.get("created_at"))
        rows.append(payload)
    return rows


async def get_open_unresolved_mention(
    session: AsyncSession,
    *,
    project_id: str,
    mention_text: str,
    observed_kind: str | None,
    repo_scope: str | None,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select mention_id, project_id, mention_text, observed_kind, repo_scope,
                   context_json, status, created_at, updated_at
            from unresolved_mentions
            where project_id = :project_id
              and status = 'OPEN'
              and lower(btrim(mention_text)) = :mention_text_norm
              and coalesce(lower(btrim(observed_kind)), '') = :observed_kind_norm
              and coalesce(lower(btrim(repo_scope)), '') = :repo_scope_norm
            order by updated_at desc, mention_id desc
            limit 1
            """
        ),
        {
            "project_id": project_id,
            "mention_text_norm": _normalize_text(mention_text),
            "observed_kind_norm": _normalize_text(observed_kind or "") if observed_kind else "",
            "repo_scope_norm": _normalize_text(repo_scope or "") if repo_scope else "",
        },
    )
    row = result.mappings().first()
    return _unresolved_mention_payload_from_row(dict(row)) if row else None


async def upsert_open_unresolved_mention(
    session: AsyncSession,
    *,
    mention_id: str,
    project_id: str,
    mention_text: str,
    observed_kind: str | None,
    repo_scope: str | None,
    context: dict | None,
) -> dict:
    existing = await get_open_unresolved_mention(
        session,
        project_id=project_id,
        mention_text=mention_text,
        observed_kind=observed_kind,
        repo_scope=repo_scope,
    )
    if existing is not None:
        result = await session.execute(
            text(
                """
                update unresolved_mentions
                set mention_text = :mention_text,
                    observed_kind = :observed_kind,
                    repo_scope = :repo_scope,
                    context_json = unresolved_mentions.context_json || cast(:context_json as jsonb),
                    updated_at = now()
                where mention_id = :mention_id
                returning mention_id, project_id, mention_text, observed_kind, repo_scope,
                          context_json, status, created_at, updated_at
                """
            ),
            {
                "mention_id": existing["mention_id"],
                "mention_text": mention_text,
                "observed_kind": observed_kind,
                "repo_scope": repo_scope,
                "context_json": _json(context),
            },
        )
        row = result.mappings().first()
        return _unresolved_mention_payload_from_row(dict(row))

    result = await session.execute(
        text(
            """
            insert into unresolved_mentions (
              mention_id, project_id, mention_text, observed_kind, repo_scope, context_json, status
            ) values (
              :mention_id, :project_id, :mention_text, :observed_kind, :repo_scope, cast(:context_json as jsonb), 'OPEN'
            )
            on conflict do nothing
            returning mention_id, project_id, mention_text, observed_kind, repo_scope,
                      context_json, status, created_at, updated_at
            """
        ),
        {
            "mention_id": mention_id,
            "project_id": project_id,
            "mention_text": mention_text,
            "observed_kind": observed_kind,
            "repo_scope": repo_scope,
            "context_json": _json(context),
        },
    )
    row = result.mappings().first()
    if row is not None:
        return _unresolved_mention_payload_from_row(dict(row))
    return await upsert_open_unresolved_mention(
        session,
        mention_id=mention_id,
        project_id=project_id,
        mention_text=mention_text,
        observed_kind=observed_kind,
        repo_scope=repo_scope,
        context=context,
    )


async def resolve_open_unresolved_mention(
    session: AsyncSession,
    *,
    project_id: str,
    mention_text: str,
    observed_kind: str | None,
    repo_scope: str | None,
    context: dict | None,
) -> dict | None:
    existing = await get_open_unresolved_mention(
        session,
        project_id=project_id,
        mention_text=mention_text,
        observed_kind=observed_kind,
        repo_scope=repo_scope,
    )
    if existing is None:
        return None
    result = await session.execute(
        text(
            """
            update unresolved_mentions
            set status = 'RESOLVED',
                context_json = unresolved_mentions.context_json || cast(:context_json as jsonb),
                updated_at = now()
            where mention_id = :mention_id
            returning mention_id, project_id, mention_text, observed_kind, repo_scope,
                      context_json, status, created_at, updated_at
            """
        ),
        {
            "mention_id": existing["mention_id"],
            "context_json": _json(context),
        },
    )
    row = result.mappings().first()
    return _unresolved_mention_payload_from_row(dict(row)) if row else None


async def merge_entities(
    session: AsyncSession,
    *,
    project_id: str,
    resolution_event_id: str,
    operation_id: str | None,
    target_entity_id: str,
    source_entity_ids: list[str],
    reason: str | None,
) -> dict:
    unique_source_ids = list(dict.fromkeys(str(item) for item in source_entity_ids if str(item).strip()))
    if not unique_source_ids:
        raise ValueError("source_entity_ids must not be empty")
    await acquire_entity_resolution_locks(
        session,
        project_id=project_id,
        entity_ids=[target_entity_id, *unique_source_ids],
    )

    target_entity = await get_entity_direct(
        session,
        project_id=project_id,
        entity_id=target_entity_id,
    )
    if target_entity is None:
        raise KeyError(target_entity_id)
    if str(target_entity.get("state") or "ACTIVE") != "ACTIVE":
        raise ValueError("target entity must be ACTIVE")

    source_entities: list[dict] = []
    for source_entity_id in unique_source_ids:
        source_entity = await get_entity_direct(
            session,
            project_id=project_id,
            entity_id=source_entity_id,
        )
        if source_entity is None:
            raise KeyError(source_entity_id)
        if str(source_entity.get("state") or "ACTIVE") != "ACTIVE":
            raise ValueError(f"source entity is not ACTIVE: {source_entity_id}")
        source_entities.append(source_entity)

    for source_entity in source_entities:
        target_resolution = await resolve_entity_redirect(
            session,
            project_id=project_id,
            entity_id=target_entity_id,
        )
        if str(source_entity["entity_id"]) == str(target_resolution["canonical_entity_id"]):
            raise ValueError("redirect cycle detected")

    for source_entity in source_entities:
        for alias_value in {
            str(source_entity.get("canonical_name") or "").strip(),
            str(source_entity.get("display_name") or "").strip(),
        }:
            if not alias_value:
                continue
            await add_entity_alias(
                session,
                project_id=project_id,
                entity_id=target_entity_id,
                alias_type="merge_redirect",
                alias_value=alias_value,
                confidence=1.0,
            )

    deactivate_conflicts = text(
        """
        update entity_aliases source_alias
        set active = false
        where source_alias.project_id = :project_id
          and source_alias.entity_id in :source_entity_ids
          and source_alias.active = true
          and exists (
            select 1
            from entity_aliases target_alias
            where target_alias.project_id = source_alias.project_id
              and target_alias.entity_id = :target_entity_id
              and target_alias.active = true
              and target_alias.alias_type = source_alias.alias_type
              and target_alias.alias_value = source_alias.alias_value
          )
        """
    ).bindparams(bindparam("source_entity_ids", expanding=True))
    await session.execute(
        deactivate_conflicts,
        {
            "project_id": project_id,
            "target_entity_id": target_entity_id,
            "source_entity_ids": unique_source_ids,
        },
    )

    update_aliases = text(
        """
        update entity_aliases
        set entity_id = :target_entity_id
        where project_id = :project_id
          and entity_id in :source_entity_ids
          and active = true
        """
    ).bindparams(bindparam("source_entity_ids", expanding=True))
    await session.execute(
        update_aliases,
        {
            "project_id": project_id,
            "target_entity_id": target_entity_id,
            "source_entity_ids": unique_source_ids,
        },
    )

    rebind_subject = text(
        """
        update fact_versions
        set subject_entity_id = :target_entity_id
        where project_id = :project_id
          and subject_entity_id in :source_entity_ids
        """
    ).bindparams(bindparam("source_entity_ids", expanding=True))
    await session.execute(
        rebind_subject,
        {
            "project_id": project_id,
            "target_entity_id": target_entity_id,
            "source_entity_ids": unique_source_ids,
        },
    )

    rebind_object = text(
        """
        update fact_versions
        set object_entity_id = :target_entity_id
        where project_id = :project_id
          and object_entity_id in :source_entity_ids
        """
    ).bindparams(bindparam("source_entity_ids", expanding=True))
    await session.execute(
        rebind_object,
        {
            "project_id": project_id,
            "target_entity_id": target_entity_id,
            "source_entity_ids": unique_source_ids,
        },
    )

    update_target_links = text(
        """
        update provenance_links
        set target_id = :target_entity_id
        where project_id = :project_id
          and target_kind = 'entity'
          and target_id in :source_entity_ids
        """
    ).bindparams(bindparam("source_entity_ids", expanding=True))
    await session.execute(
        update_target_links,
        {
            "project_id": project_id,
            "target_entity_id": target_entity_id,
            "source_entity_ids": unique_source_ids,
        },
    )

    update_source_links = text(
        """
        update provenance_links
        set source_id = :target_entity_id
        where project_id = :project_id
          and source_kind = 'entity'
          and source_id in :source_entity_ids
        """
    ).bindparams(bindparam("source_entity_ids", expanding=True))
    await session.execute(
        update_source_links,
        {
            "project_id": project_id,
            "target_entity_id": target_entity_id,
            "source_entity_ids": unique_source_ids,
        },
    )

    await create_entity_resolution_event(
        session,
        resolution_event_id=resolution_event_id,
        project_id=project_id,
        operation_id=operation_id,
        event_kind="MERGE",
        reason=reason,
        canonical_target_entity_id=target_entity_id,
        payload={
            "target_entity_id": target_entity_id,
            "source_entity_ids": unique_source_ids,
        },
    )

    for source_entity in source_entities:
        metadata = dict(source_entity.get("metadata") or {})
        metadata["resolution"] = {
            "status": "REDIRECTED",
            "target_entity_id": target_entity_id,
            "resolution_event_id": resolution_event_id,
            "reason": reason,
        }
        await session.execute(
            text(
                """
                update entities
                set state = 'REDIRECTED',
                    metadata_json = cast(:metadata_json as jsonb),
                    updated_at = now()
                where project_id = :project_id
                  and entity_id = :entity_id
                """
            ),
            {
                "project_id": project_id,
                "entity_id": source_entity["entity_id"],
                "metadata_json": _json(metadata),
            },
        )
        await create_entity_redirect(
            session,
            project_id=project_id,
            source_entity_id=str(source_entity["entity_id"]),
            target_entity_id=target_entity_id,
            resolution_event_id=resolution_event_id,
        )
    return {
        "resolution_event_id": resolution_event_id,
        "canonical_target_entity_id": target_entity_id,
        "redirected_entity_ids": unique_source_ids,
    }


async def split_entity(
    session: AsyncSession,
    *,
    project_id: str,
    resolution_event_id: str,
    operation_id: str | None,
    source_entity_id: str,
    partitions: list[dict],
    reason: str | None,
) -> dict:
    await acquire_entity_resolution_locks(
        session,
        project_id=project_id,
        entity_ids=[
            source_entity_id,
            *[
                str(partition.get("target_entity_id"))
                for partition in partitions
                if partition.get("target_entity_id")
            ],
        ],
    )

    source_entity = await get_entity_direct(
        session,
        project_id=project_id,
        entity_id=source_entity_id,
    )
    if source_entity is None:
        raise KeyError(source_entity_id)
    if str(source_entity.get("state") or "ACTIVE") != "ACTIVE":
        raise ValueError("source entity must be ACTIVE")

    alias_assignment_keys: set[str] = set()
    fact_assignment_keys: set[tuple[str, str]] = set()
    created_entity_ids: list[str] = []
    resolved_partitions: list[dict] = []

    for partition in partitions:
        alias_values = [str(item) for item in (partition.get("alias_values") or []) if str(item).strip()]
        fact_bindings = [
            {
                "fact_version_id": str(item.get("fact_version_id")),
                "slot": str(item.get("slot") or "").lower(),
            }
            for item in (partition.get("fact_bindings") or [])
        ]
        for alias_value in alias_values:
            normalized_key = alias_value.strip().lower()
            if normalized_key in alias_assignment_keys:
                raise ValueError(f"duplicate alias assignment: {alias_value}")
            alias_assignment_keys.add(normalized_key)
        for binding in fact_bindings:
            binding_key = (binding["fact_version_id"], binding["slot"])
            if binding_key in fact_assignment_keys:
                raise ValueError(f"duplicate fact binding assignment: {binding['fact_version_id']}:{binding['slot']}")
            fact_assignment_keys.add(binding_key)

        target_entity_id = partition.get("target_entity_id")
        default_name_alias: str | None = None
        if target_entity_id:
            target_entity = await get_entity_direct(
                session,
                project_id=project_id,
                entity_id=str(target_entity_id),
            )
            if target_entity is None:
                raise KeyError(str(target_entity_id))
            if str(target_entity.get("state") or "ACTIVE") != "ACTIVE":
                raise ValueError("split target entity must be ACTIVE")
        else:
            new_entity = dict(partition.get("new_entity") or {})
            target_entity_id = str(new_entity["entity_id"])
            await upsert_entity(
                session,
                entity_id=target_entity_id,
                project_id=project_id,
                entity_kind=str(new_entity["entity_kind"]),
                canonical_name=str(new_entity["canonical_name"]),
                display_name=str(new_entity.get("display_name") or new_entity["canonical_name"]),
                metadata={
                    "resolution": {
                        "status": "CREATED_FROM_SPLIT",
                        "source_entity_id": source_entity_id,
                        "resolution_event_id": resolution_event_id,
                        "reason": reason,
                    }
                },
            )
            default_name_alias = str(new_entity.get("display_name") or new_entity["canonical_name"])
            created_entity_ids.append(target_entity_id)

        resolved_partitions.append(
            {
                "target_entity_id": str(target_entity_id),
                "alias_values": alias_values,
                "fact_bindings": fact_bindings,
                "default_name_alias": default_name_alias,
            }
        )

    source_alias_rows = await list_entity_alias_rows(
        session,
        project_id=project_id,
        entity_id=source_entity_id,
    )
    source_alias_map: dict[str, list[dict]] = {}
    for alias_row in source_alias_rows:
        source_alias_map.setdefault(str(alias_row["alias_value"]).strip().lower(), []).append(alias_row)

    reassigned_aliases = 0
    reassigned_facts = 0
    for partition in resolved_partitions:
        target_entity_id = str(partition["target_entity_id"])
        alias_values = partition["alias_values"]
        if alias_values:
            missing_aliases = [
                alias_value
                for alias_value in alias_values
                if alias_value.strip().lower() not in source_alias_map
            ]
            if missing_aliases:
                raise ValueError(f"unknown alias_values for source entity: {missing_aliases}")

            deactivate_conflicts = text(
                """
                update entity_aliases source_alias
                set active = false
                where source_alias.project_id = :project_id
                  and source_alias.entity_id = :source_entity_id
                  and source_alias.active = true
                  and lower(source_alias.alias_value) in :alias_values
                  and exists (
                    select 1
                    from entity_aliases target_alias
                    where target_alias.project_id = source_alias.project_id
                      and target_alias.entity_id = :target_entity_id
                      and target_alias.active = true
                      and target_alias.alias_type = source_alias.alias_type
                      and target_alias.alias_value = source_alias.alias_value
                  )
                """
            ).bindparams(bindparam("alias_values", expanding=True))
            await session.execute(
                deactivate_conflicts,
                {
                    "project_id": project_id,
                    "source_entity_id": source_entity_id,
                    "target_entity_id": target_entity_id,
                    "alias_values": [alias_value.strip().lower() for alias_value in alias_values],
                },
            )
            update_aliases = text(
                """
                update entity_aliases
                set entity_id = :target_entity_id
                where project_id = :project_id
                  and entity_id = :source_entity_id
                  and active = true
                  and lower(alias_value) in :alias_values
                """
            ).bindparams(bindparam("alias_values", expanding=True))
            alias_result = await session.execute(
                update_aliases,
                {
                    "project_id": project_id,
                    "source_entity_id": source_entity_id,
                    "target_entity_id": target_entity_id,
                    "alias_values": [alias_value.strip().lower() for alias_value in alias_values],
                },
            )
            reassigned_aliases += int(alias_result.rowcount or 0)

        for binding in partition["fact_bindings"]:
            fact_version_id = binding["fact_version_id"]
            slot = binding["slot"]
            if slot not in {"subject", "object", "both"}:
                raise ValueError(f"invalid fact binding slot: {slot}")
            fact = await get_fact_version(
                session,
                project_id=project_id,
                fact_version_id=fact_version_id,
            )
            if fact is None:
                raise KeyError(fact_version_id)

            updated_any = False
            if slot in {"subject", "both"} and str(fact["subject_entity_id"]) == source_entity_id:
                subject_result = await session.execute(
                    text(
                        """
                        update fact_versions
                        set subject_entity_id = :target_entity_id
                        where project_id = :project_id
                          and fact_version_id = :fact_version_id
                          and subject_entity_id = :source_entity_id
                        """
                    ),
                    {
                        "project_id": project_id,
                        "fact_version_id": fact_version_id,
                        "source_entity_id": source_entity_id,
                        "target_entity_id": target_entity_id,
                    },
                )
                updated_any = updated_any or bool(subject_result.rowcount or 0)
                reassigned_facts += int(subject_result.rowcount or 0)
            elif slot == "subject":
                raise ValueError(f"fact_version_id is not bound on subject slot: {fact_version_id}")

            if slot in {"object", "both"} and str(fact.get("object_entity_id") or "") == source_entity_id:
                object_result = await session.execute(
                    text(
                        """
                        update fact_versions
                        set object_entity_id = :target_entity_id
                        where project_id = :project_id
                          and fact_version_id = :fact_version_id
                          and object_entity_id = :source_entity_id
                        """
                    ),
                    {
                        "project_id": project_id,
                        "fact_version_id": fact_version_id,
                        "source_entity_id": source_entity_id,
                        "target_entity_id": target_entity_id,
                    },
                )
                updated_any = updated_any or bool(object_result.rowcount or 0)
                reassigned_facts += int(object_result.rowcount or 0)
            elif slot == "object":
                raise ValueError(f"fact_version_id is not bound on object slot: {fact_version_id}")

            if slot == "both" and not updated_any:
                raise ValueError(f"fact_version_id is not bound to source entity: {fact_version_id}")

    for partition in resolved_partitions:
        default_name_alias = str(partition.get("default_name_alias") or "").strip()
        if not default_name_alias:
            continue
        await add_entity_alias(
            session,
            project_id=project_id,
            entity_id=str(partition["target_entity_id"]),
            alias_type="name",
            alias_value=default_name_alias,
            confidence=1.0,
        )

    await create_entity_resolution_event(
        session,
        resolution_event_id=resolution_event_id,
        project_id=project_id,
        operation_id=operation_id,
        event_kind="SPLIT",
        reason=reason,
        canonical_target_entity_id=None,
        payload={
            "source_entity_id": source_entity_id,
            "created_entity_ids": created_entity_ids,
            "partitions": resolved_partitions,
            "reassigned_aliases": reassigned_aliases,
            "reassigned_facts": reassigned_facts,
        },
    )
    return {
        "resolution_event_id": resolution_event_id,
        "created_entity_ids": created_entity_ids,
        "reassigned_aliases": reassigned_aliases,
        "reassigned_facts": reassigned_facts,
    }


async def get_neighbors(
    session: AsyncSession,
    *,
    project_id: str,
    entity_id: str,
    direction: str,
    relation_types: list[str] | None,
    current_only: bool,
    valid_at: str | datetime | None,
    as_of_system_time: str | datetime | None,
    limit: int,
) -> dict | None:
    anchor = await get_entity(
        session,
        project_id=project_id,
        entity_id=entity_id,
    )
    if anchor is None:
        return None
    canonical_entity_id = str(anchor["entity_id"])

    clauses = ["fv.project_id = :project_id", "fv.object_entity_id is not null"]
    params: dict[str, Any] = {
        "project_id": project_id,
        "entity_id": canonical_entity_id,
        "limit": limit + 1,
    }
    normalized_direction = str(direction).upper()
    if normalized_direction == "OUT":
        clauses.append("fv.subject_entity_id = :entity_id")
    elif normalized_direction == "IN":
        clauses.append("fv.object_entity_id = :entity_id")
    else:
        clauses.append("(fv.subject_entity_id = :entity_id or fv.object_entity_id = :entity_id)")

    if relation_types:
        clauses.append("(fv.relation_type_id in :relation_types or rt.name in :relation_types)")
        params["relation_types"] = [str(item) for item in relation_types]

    if current_only:
        clauses.append("fv.status = 'CURRENT'")
        clauses.append("fv.superseded_at is null")
    if valid_at is not None:
        clauses.append("(fv.valid_from is null or fv.valid_from <= :valid_at)")
        clauses.append("(fv.valid_to is null or fv.valid_to > :valid_at)")
        params["valid_at"] = _coerce_timestamptz(valid_at)
    if as_of_system_time is not None:
        clauses.append("fv.recorded_at <= :as_of_system_time")
        clauses.append("(fv.superseded_at is null or fv.superseded_at > :as_of_system_time)")
        params["as_of_system_time"] = _coerce_timestamptz(as_of_system_time)

    query = text(
        f"""
        select
          fv.fact_version_id,
          fv.fact_group_id,
          fv.statement,
          fv.subject_entity_id,
          fv.object_entity_id,
          fv.valid_from,
          fv.valid_to,
          fv.recorded_at,
          fv.status,
          fv.confidence,
          fv.salience_score,
          fv.salience_class,
          fv.trust_class,
          fv.metadata_json,
          rt.relation_type_id,
          rt.name as relation_name,
          rt.inverse_name,
          rt.relation_class,
          rt.metadata_json as relation_metadata_json,
          case
            when fv.subject_entity_id = :entity_id then 'OUT'
            else 'IN'
          end as edge_direction,
          neighbor.entity_id as neighbor_entity_id,
          neighbor.entity_kind as neighbor_entity_kind,
          neighbor.canonical_name as neighbor_canonical_name,
          neighbor.display_name as neighbor_display_name,
          neighbor.salience_score as neighbor_salience_score,
          neighbor.salience_class as neighbor_salience_class,
          neighbor.state as neighbor_state,
          neighbor.metadata_json as neighbor_metadata_json,
          coalesce(
            (
              select jsonb_agg(alias_value order by alias_value)
              from (
                select distinct ea.alias_value
                from entity_aliases ea
                where ea.project_id = neighbor.project_id
                  and ea.entity_id = neighbor.entity_id
                  and ea.active = true
              ) alias_rows
            ),
            '[]'::jsonb
          ) as neighbor_aliases
        from fact_versions fv
        join relation_types rt
          on rt.relation_type_id = fv.relation_type_id
        join entities neighbor
          on neighbor.project_id = fv.project_id
         and neighbor.entity_id = case
           when fv.subject_entity_id = :entity_id then fv.object_entity_id
           else fv.subject_entity_id
         end
        where {' and '.join(clauses)}
        order by
          coalesce(fv.confidence, 0) desc,
          coalesce(fv.salience_score, 0) desc,
          fv.recorded_at desc,
          fv.fact_version_id asc
        limit :limit
        """
    )
    if relation_types:
        query = query.bindparams(bindparam("relation_types", expanding=True))
    result = await session.execute(query, params)

    edges: list[dict] = []
    neighbors_by_id: dict[str, dict] = {}
    rows = result.mappings().all()
    truncated = len(rows) > limit
    for row in rows[:limit]:
        payload = dict(row)
        neighbor_payload = {
            "entity_id": payload["neighbor_entity_id"],
            "name": payload["neighbor_display_name"],
            "canonical_name": payload["neighbor_canonical_name"],
            "display_name": payload["neighbor_display_name"],
            "type": payload["neighbor_entity_kind"],
            "entity_kind": payload["neighbor_entity_kind"],
            "aliases": [str(alias) for alias in (_parse_json(payload.get("neighbor_aliases")) or []) if alias],
            "summary_snippet": _summary_snippet(payload.get("statement")),
            "support_count": 1,
            "latest_support_time": _iso(payload.get("recorded_at")),
            "latest_supporting_fact": {
                "fact_version_id": payload["fact_version_id"],
                "fact_group_id": payload["fact_group_id"],
                "statement": payload["statement"],
            },
            "confidence": float(payload["confidence"]) if isinstance(payload.get("confidence"), Decimal) else payload.get("confidence"),
            "salience": float(payload["salience_score"])
            if isinstance(payload.get("salience_score"), Decimal)
            else payload.get("salience_score"),
            "salience_score": float(payload["neighbor_salience_score"])
            if isinstance(payload.get("neighbor_salience_score"), Decimal)
            else payload.get("neighbor_salience_score"),
            "salience_class": payload.get("neighbor_salience_class"),
            "state": payload.get("neighbor_state"),
            "metadata": _parse_json(payload.get("neighbor_metadata_json")) or {},
        }
        neighbors_by_id.setdefault(neighbor_payload["entity_id"], neighbor_payload)
        edges.append(
            {
                "fact_version_id": payload["fact_version_id"],
                "fact_group_id": payload["fact_group_id"],
                "direction": payload["edge_direction"],
                "subject_entity_id": payload["subject_entity_id"],
                "object_entity_id": payload["object_entity_id"],
                "relation_type_id": payload["relation_type_id"],
                "relation_type": payload["relation_name"],
                "inverse_relation_type": payload["inverse_name"],
                "relation_class": payload["relation_class"],
                "statement": payload["statement"],
                "status": payload["status"],
                "valid_from": _iso(payload.get("valid_from")),
                "valid_to": _iso(payload.get("valid_to")),
                "recorded_at": _iso(payload.get("recorded_at")),
                "confidence": float(payload["confidence"])
                if isinstance(payload.get("confidence"), Decimal)
                else payload.get("confidence"),
                "salience_score": float(payload["salience_score"])
                if isinstance(payload.get("salience_score"), Decimal)
                else payload.get("salience_score"),
                "salience_class": payload.get("salience_class"),
                "trust_class": payload["trust_class"],
                "metadata": _parse_json(payload.get("metadata_json")) or {},
                "relation_metadata": _parse_json(payload.get("relation_metadata_json")) or {},
                "neighbor_entity_id": payload["neighbor_entity_id"],
            }
        )
    return {
        "anchor": anchor,
        "neighbors": list(neighbors_by_id.values()),
        "edges": edges,
        "truncated": truncated,
    }


async def find_paths(
    session: AsyncSession,
    *,
    project_id: str,
    src_entity_id: str,
    dst_entity_id: str,
    relation_types: list[str] | None,
    max_depth: int,
    current_only: bool,
    valid_at: str | datetime | None,
    as_of_system_time: str | datetime | None,
    limit_paths: int,
) -> dict:
    src_resolution = await resolve_entity_redirect(
        session,
        project_id=project_id,
        entity_id=src_entity_id,
    )
    dst_resolution = await resolve_entity_redirect(
        session,
        project_id=project_id,
        entity_id=dst_entity_id,
    )
    src_entity_id = str(src_resolution["canonical_entity_id"])
    dst_entity_id = str(dst_resolution["canonical_entity_id"])

    clauses = ["fv.project_id = :project_id", "fv.object_entity_id is not null"]
    params: dict[str, Any] = {
        "project_id": project_id,
        "src_entity_id": src_entity_id,
        "dst_entity_id": dst_entity_id,
        "max_depth": max_depth,
        "limit_paths_plus_one": limit_paths + 1,
        "candidate_cap": 200,
    }

    if relation_types:
        clauses.append("(fv.relation_type_id in :relation_types or rt.name in :relation_types)")
        params["relation_types"] = [str(item) for item in relation_types]

    if current_only:
        clauses.append("fv.status = 'CURRENT'")
        clauses.append("fv.superseded_at is null")
    if valid_at is not None:
        params["valid_at"] = _coerce_timestamptz(valid_at)
        clauses.append("(fv.valid_from is null or fv.valid_from <= :valid_at)")
        clauses.append("(fv.valid_to is null or fv.valid_to > :valid_at)")
    if as_of_system_time is not None:
        params["as_of_system_time"] = _coerce_timestamptz(as_of_system_time)
        clauses.append("fv.recorded_at <= :as_of_system_time")
        clauses.append("(fv.superseded_at is null or fv.superseded_at > :as_of_system_time)")

    query = text(
        f"""
        with recursive eligible_edges as (
          select
            fv.fact_version_id,
            fv.fact_group_id,
            fv.subject_entity_id,
            fv.object_entity_id,
            fv.statement,
            fv.recorded_at,
            fv.trust_class,
            coalesce(fv.confidence, 0)::double precision as confidence_score,
            coalesce(fv.salience_score, 0)::double precision as salience_score_value,
            fv.salience_class,
            rt.relation_type_id,
            rt.name as relation_type
          from fact_versions fv
          join relation_types rt
            on rt.relation_type_id = fv.relation_type_id
          where {' and '.join(clauses)}
        ),
        paths as (
          select
            1 as hop_count,
            step.next_entity_id as current_entity_id,
            array[cast(:src_entity_id as text), step.next_entity_id::text] as entity_ids,
            array[ee.fact_version_id::text] as fact_version_ids,
            jsonb_build_array(
              jsonb_build_object(
                'fact_version_id', ee.fact_version_id,
                'fact_group_id', ee.fact_group_id,
                'relation_type_id', ee.relation_type_id,
                'relation_type', ee.relation_type,
                'direction', step.direction,
                'statement', ee.statement,
                'confidence', ee.confidence_score,
                'salience_score', ee.salience_score_value,
                'salience_class', ee.salience_class,
                'trust_class', ee.trust_class,
                'recorded_at', ee.recorded_at
              )
            ) as edge_steps,
            concat_ws('|', :src_entity_id, ee.fact_version_id, step.next_entity_id) as path_signature,
            ee.confidence_score as confidence_sum,
            ee.salience_score_value as salience_sum,
            ee.recorded_at as newest_recorded_at
          from eligible_edges ee
          cross join lateral (
            select
              case
                when ee.subject_entity_id = :src_entity_id then ee.object_entity_id
                else ee.subject_entity_id
              end as next_entity_id,
              case
                when ee.subject_entity_id = :src_entity_id then 'OUT'
                else 'IN'
              end as direction
          ) step
          where :src_entity_id in (ee.subject_entity_id, ee.object_entity_id)
            and step.next_entity_id is not null
            and step.next_entity_id <> :src_entity_id

          union all

          select
            p.hop_count + 1 as hop_count,
            step.next_entity_id as current_entity_id,
            p.entity_ids || step.next_entity_id::text as entity_ids,
            p.fact_version_ids || ee.fact_version_id::text as fact_version_ids,
            p.edge_steps || jsonb_build_array(
              jsonb_build_object(
                'fact_version_id', ee.fact_version_id,
                'fact_group_id', ee.fact_group_id,
                'relation_type_id', ee.relation_type_id,
                'relation_type', ee.relation_type,
                'direction', step.direction,
                'statement', ee.statement,
                'confidence', ee.confidence_score,
                'salience_score', ee.salience_score_value,
                'salience_class', ee.salience_class,
                'trust_class', ee.trust_class,
                'recorded_at', ee.recorded_at
              )
            ) as edge_steps,
            concat_ws('|', p.path_signature, ee.fact_version_id, step.next_entity_id) as path_signature,
            p.confidence_sum + ee.confidence_score as confidence_sum,
            p.salience_sum + ee.salience_score_value as salience_sum,
            greatest(p.newest_recorded_at, ee.recorded_at) as newest_recorded_at
          from paths p
          join eligible_edges ee
            on p.current_entity_id in (ee.subject_entity_id, ee.object_entity_id)
          cross join lateral (
            select
              case
                when ee.subject_entity_id = p.current_entity_id then ee.object_entity_id
                else ee.subject_entity_id
              end as next_entity_id,
              case
                when ee.subject_entity_id = p.current_entity_id then 'OUT'
                else 'IN'
              end as direction
          ) step
          where p.hop_count < :max_depth
            and step.next_entity_id is not null
            and not step.next_entity_id = any(p.entity_ids)
        ),
        destination_paths as (
          select
            hop_count,
            current_entity_id,
            entity_ids,
            fact_version_ids,
            edge_steps,
            path_signature,
            (confidence_sum / hop_count::double precision) as avg_confidence,
            (salience_sum / hop_count::double precision) as avg_salience,
            newest_recorded_at
          from paths
          where current_entity_id = :dst_entity_id
        ),
        bounded_candidates as (
          select *
          from destination_paths
          order by
            avg_confidence desc,
            hop_count asc,
            avg_salience desc,
            newest_recorded_at desc,
            path_signature asc
          limit :candidate_cap
        )
        select
          hop_count,
          entity_ids,
          fact_version_ids,
          edge_steps,
          path_signature,
          avg_confidence,
          avg_salience,
          newest_recorded_at
        from bounded_candidates
        order by
          avg_confidence desc,
          hop_count asc,
          avg_salience desc,
          newest_recorded_at desc,
          path_signature asc
        limit :limit_paths_plus_one
        """
    )
    if relation_types:
        query = query.bindparams(bindparam("relation_types", expanding=True))
    result = await session.execute(query, params)
    rows = [dict(row) for row in result.mappings().all()]

    truncated = len(rows) > limit_paths
    rows = rows[:limit_paths]
    entity_ids: list[str] = []
    for row in rows:
        entity_ids.extend(str(entity_id) for entity_id in (row.get("entity_ids") or []))
    entity_lookup = await get_entities_by_ids(
        session,
        project_id=project_id,
        entity_ids=list(dict.fromkeys(entity_ids)),
    )

    paths: list[dict] = []
    for row in rows:
        raw_entity_ids = [str(entity_id) for entity_id in (row.get("entity_ids") or [])]
        raw_fact_version_ids = [str(fact_version_id) for fact_version_id in (row.get("fact_version_ids") or [])]
        raw_edges = _parse_json(row.get("edge_steps")) or []
        steps: list[dict] = []
        for index, entity_id in enumerate(raw_entity_ids):
            entity_payload = entity_lookup.get(entity_id)
            if entity_payload is None:
                steps.append(
                    {
                        "step_kind": "entity",
                        "entity_id": entity_id,
                        "name": entity_id,
                        "entity_kind": "Unknown",
                    }
                )
            else:
                steps.append(
                    {
                        "step_kind": "entity",
                        "entity_id": entity_payload["entity_id"],
                        "name": entity_payload["display_name"],
                        "entity_kind": entity_payload["entity_kind"],
                        "salience_score": entity_payload.get("salience_score"),
                        "salience_class": entity_payload.get("salience_class"),
                    }
                )
            if index < len(raw_edges):
                edge = raw_edges[index]
                steps.append(
                    {
                        "step_kind": "fact",
                        "fact_version_id": edge.get("fact_version_id"),
                        "fact_group_id": edge.get("fact_group_id"),
                        "relation_type_id": edge.get("relation_type_id"),
                        "relation_type": edge.get("relation_type"),
                        "direction": edge.get("direction"),
                        "statement": edge.get("statement"),
                        "confidence": edge.get("confidence"),
                        "salience_score": edge.get("salience_score"),
                        "salience_class": edge.get("salience_class"),
                        "trust_class": edge.get("trust_class"),
                        "recorded_at": _iso(edge.get("recorded_at")),
                    }
                )
        avg_confidence = row.get("avg_confidence")
        paths.append(
            {
                "score": float(avg_confidence) if isinstance(avg_confidence, Decimal) else avg_confidence,
                "hop_count": int(row["hop_count"]),
                "entity_ids": raw_entity_ids,
                "fact_version_ids": raw_fact_version_ids,
                "steps": steps,
            }
        )

    return {
        "paths": paths,
        "truncated": truncated,
    }


async def get_fact_version(
    session: AsyncSession,
    *,
    project_id: str,
    fact_version_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select fv.fact_version_id, fv.fact_group_id, fv.statement, fv.normalized_statement,
                   fv.subject_entity_id, fv.relation_type_id, fv.object_entity_id, fv.value_json,
                   fv.valid_from, fv.valid_to, fv.recorded_at, fv.superseded_at, fv.status,
                   fv.confidence, fv.salience_score, fv.salience_class, fv.trust_class, fv.created_from_episode_id,
                   fv.replaces_fact_version_id, fv.metadata_json
            from fact_versions fv
            where fv.project_id = :project_id
              and fv.fact_version_id = :fact_version_id
            """
        ),
        {
            "project_id": project_id,
            "fact_version_id": fact_version_id,
        },
    )
    row = result.mappings().first()
    return _fact_payload_from_row(dict(row)) if row else None


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
                   fv.confidence, fv.salience_score, fv.salience_class, fv.trust_class, fv.created_from_episode_id,
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
                   fv.confidence, fv.salience_score, fv.salience_class, fv.trust_class, fv.created_from_episode_id,
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


async def list_fact_supporting_episodes(
    session: AsyncSession,
    *,
    project_id: str,
    fact_group_id: str,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            with episode_links as (
              select distinct
                pl.source_id as episode_id,
                pl.role,
                pl.metadata_json,
                pl.created_at
              from provenance_links pl
              where pl.project_id = :project_id
                and pl.source_kind = 'episode'
                and (
                  (pl.target_kind = 'fact_group' and pl.target_id = :fact_group_id)
                  or (
                    pl.target_kind = 'fact_version'
                    and pl.target_id in (
                      select fact_version_id
                      from fact_versions
                      where project_id = :project_id
                        and fact_group_id = :fact_group_id
                    )
                  )
                )
            )
            select
              e.episode_id,
              e.reference_time,
              e.ingested_at,
              e.summary,
              e.metadata_json,
              e.salience_score,
              e.salience_class,
              episode_links.role,
              episode_links.metadata_json as provenance_metadata_json,
              episode_links.created_at as provenance_created_at
            from episode_links
            join episodes e
              on e.episode_id = episode_links.episode_id
            order by coalesce(e.reference_time, e.ingested_at) desc, e.episode_id desc
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
        rows.append(
            {
                "episode_id": payload["episode_id"],
                "reference_time": _iso(payload.get("reference_time")),
                "ingested_at": _iso(payload.get("ingested_at")),
                "summary": payload.get("summary"),
                "metadata": _parse_json(payload.get("metadata_json")) or {},
                "salience_score": float(payload["salience_score"])
                if isinstance(payload.get("salience_score"), Decimal)
                else payload.get("salience_score"),
                "salience_class": payload.get("salience_class"),
                "role": payload.get("role"),
                "provenance_metadata": _parse_json(payload.get("provenance_metadata_json")) or {},
                "linked_at": _iso(payload.get("provenance_created_at")),
            }
        )
    return rows


async def update_fact_version_salience(
    session: AsyncSession,
    *,
    project_id: str,
    fact_version_id: str,
    salience_score: float,
    salience_class: str,
    metadata_json: dict,
) -> dict | None:
    result = await session.execute(
        text(
            """
            update fact_versions
            set salience_score = :salience_score,
                salience_class = :salience_class,
                metadata_json = cast(:metadata_json as jsonb)
            where project_id = :project_id
              and fact_version_id = :fact_version_id
            returning
              fact_version_id, fact_group_id, statement, normalized_statement,
              subject_entity_id, relation_type_id, object_entity_id, value_json,
              valid_from, valid_to, recorded_at, superseded_at, status,
              confidence, salience_score, salience_class, trust_class, created_from_episode_id,
              replaces_fact_version_id, metadata_json
            """
        ),
        {
            "project_id": project_id,
            "fact_version_id": fact_version_id,
            "salience_score": salience_score,
            "salience_class": salience_class,
            "metadata_json": _json(metadata_json),
        },
    )
    row = result.mappings().first()
    return _fact_payload_from_row(dict(row)) if row else None


async def update_entity_salience(
    session: AsyncSession,
    *,
    project_id: str,
    entity_id: str,
    salience_score: float,
    salience_class: str,
    metadata_json: dict,
) -> dict | None:
    result = await session.execute(
        text(
            """
            update entities
            set salience_score = :salience_score,
                salience_class = :salience_class,
                metadata_json = cast(:metadata_json as jsonb)
            where project_id = :project_id
              and entity_id = :entity_id
            returning
              entity_id, entity_kind, canonical_name, display_name,
              salience_score, salience_class, state, metadata_json,
              coalesce(
                (
                  select jsonb_agg(alias_value order by alias_value)
                  from (
                    select distinct ea.alias_value
                    from entity_aliases ea
                    where ea.project_id = entities.project_id
                      and ea.entity_id = entities.entity_id
                      and ea.active = true
                  ) alias_rows
                ),
                '[]'::jsonb
              ) as aliases
            """
        ),
        {
            "project_id": project_id,
            "entity_id": entity_id,
            "salience_score": salience_score,
            "salience_class": salience_class,
            "metadata_json": _json(metadata_json),
        },
    )
    row = result.mappings().first()
    if row is None:
        return None
    payload = _entity_payload_from_row(dict(row))
    payload["support_count"] = 0
    payload["latest_support_time"] = None
    payload["latest_supporting_fact"] = None
    payload["summary_snippet"] = None
    payload["confidence"] = None
    payload["salience"] = None
    return payload


async def get_relation_type(
    session: AsyncSession,
    *,
    relation_type_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select relation_type_id, name, inverse_name, relation_class, is_transitive, metadata_json, created_at
            from relation_types
            where relation_type_id = :relation_type_id
            """
        ),
        {"relation_type_id": relation_type_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    payload = dict(row)
    payload["metadata"] = _parse_json(payload.pop("metadata_json", None)) or {}
    payload["created_at"] = _iso(payload.get("created_at"))
    return payload


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
