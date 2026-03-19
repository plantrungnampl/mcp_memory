from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


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
