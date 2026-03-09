from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _json(value: dict | None) -> str:
    return json.dumps(value or {}, default=str)


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


def _state_from_row(row: dict | None) -> dict | None:
    if row is None:
        return None
    state = row.get("state_json")
    return {
        "project_id": row["project_id"],
        "task_id": row["task_id"],
        "session_id": row["session_id"],
        "state": state if isinstance(state, dict) else {},
        "checkpoint_note": row.get("checkpoint_note"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "expires_at": row.get("expires_at"),
    }


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, value in patch.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


async def get_working_memory(
    session: AsyncSession,
    *,
    project_id: str,
    task_id: str,
    session_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select project_id, task_id, session_id, state_json, checkpoint_note,
                   created_at, updated_at, expires_at
            from working_memory
            where project_id = :project_id
              and task_id = :task_id
              and session_id = :session_id
              and (expires_at is null or expires_at > now())
            """
        ),
        {
            "project_id": project_id,
            "task_id": task_id,
            "session_id": session_id,
        },
    )
    row = result.mappings().first()
    return _state_from_row(dict(row) if row else None)


async def upsert_working_memory(
    session: AsyncSession,
    *,
    project_id: str,
    task_id: str,
    session_id: str,
    state: dict,
    checkpoint_note: str | None = None,
    expires_at: str | datetime | None = None,
    commit: bool = True,
) -> dict:
    result = await session.execute(
        text(
            """
            insert into working_memory (
                project_id, task_id, session_id, state_json, checkpoint_note, expires_at
            ) values (
                :project_id, :task_id, :session_id, cast(:state_json as jsonb), :checkpoint_note, :expires_at
            )
            on conflict (project_id, task_id, session_id)
            do update set
                state_json = cast(:state_json as jsonb),
                checkpoint_note = :checkpoint_note,
                updated_at = now(),
                expires_at = :expires_at
            returning project_id, task_id, session_id, state_json, checkpoint_note,
                      created_at, updated_at, expires_at
            """
        ),
        {
            "project_id": project_id,
            "task_id": task_id,
            "session_id": session_id,
            "state_json": _json(state),
            "checkpoint_note": checkpoint_note,
            "expires_at": _coerce_timestamptz(expires_at),
        },
    )
    row = result.mappings().first()
    if commit:
        await session.commit()
    return _state_from_row(dict(row)) or {
        "project_id": project_id,
        "task_id": task_id,
        "session_id": session_id,
        "state": state,
        "checkpoint_note": checkpoint_note,
        "created_at": None,
        "updated_at": None,
        "expires_at": _coerce_timestamptz(expires_at),
    }


async def patch_working_memory(
    session: AsyncSession,
    *,
    project_id: str,
    task_id: str,
    session_id: str,
    patch: dict,
    checkpoint_note: str | None = None,
    expires_at: str | datetime | None = None,
    commit: bool = True,
) -> dict:
    current = await get_working_memory(
        session,
        project_id=project_id,
        task_id=task_id,
        session_id=session_id,
    )
    merged = _deep_merge(current.get("state") if current else {}, patch)
    return await upsert_working_memory(
        session,
        project_id=project_id,
        task_id=task_id,
        session_id=session_id,
        state=merged,
        checkpoint_note=checkpoint_note if checkpoint_note is not None else (current or {}).get("checkpoint_note"),
        expires_at=expires_at if expires_at is not None else (current or {}).get("expires_at"),
        commit=commit,
    )
