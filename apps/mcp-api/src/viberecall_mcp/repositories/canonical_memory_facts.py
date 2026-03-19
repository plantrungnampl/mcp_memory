from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.repositories.canonical_memory_common import (
    _entity_payload_from_row,
    _fact_payload_from_row,
    _iso,
    _json,
    _parse_json,
)


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
