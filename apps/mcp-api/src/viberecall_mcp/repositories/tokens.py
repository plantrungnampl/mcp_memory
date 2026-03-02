from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_token_by_hash(session: AsyncSession, token_hash: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select token_id, prefix, token_hash, project_id, scopes, plan,
                   created_at, last_used_at, revoked_at, expires_at
            from mcp_tokens
            where token_hash = :token_hash
            """
        ),
        {"token_hash": token_hash},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def touch_token_usage(session: AsyncSession, token_id: str) -> None:
    await session.execute(
        text(
            """
            update mcp_tokens
            set last_used_at = :last_used_at
            where token_id = :token_id
            """
        ),
        {"token_id": token_id, "last_used_at": datetime.now(timezone.utc)},
    )
    await session.commit()


async def get_latest_active_token_preview(session: AsyncSession, project_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select token_id, prefix, created_at, last_used_at, revoked_at, expires_at
            from mcp_tokens
            where project_id = :project_id
              and (revoked_at is null or revoked_at > :now)
            order by created_at desc, token_id desc
            limit 1
            """
        ),
        {"project_id": project_id, "now": datetime.now(timezone.utc)},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_tokens_for_project(session: AsyncSession, project_id: str) -> list[dict]:
    result = await session.execute(
        text(
            """
            select token_id, prefix, created_at, last_used_at, revoked_at, expires_at, plan, scopes
            from mcp_tokens
            where project_id = :project_id
            order by created_at desc, token_id desc
            """
        ),
        {"project_id": project_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def get_token_for_project(
    session: AsyncSession,
    *,
    project_id: str,
    token_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select token_id, prefix, token_hash, project_id, scopes, plan,
                   created_at, last_used_at, revoked_at, expires_at
            from mcp_tokens
            where project_id = :project_id
              and token_id = :token_id
            """
        ),
        {"project_id": project_id, "token_id": token_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def create_token(
    session: AsyncSession,
    *,
    token_id: str,
    prefix: str,
    token_hash: str,
    project_id: str,
    scopes: list[str],
    plan: str,
    expires_at: datetime | None = None,
) -> dict:
    result = await session.execute(
        text(
            """
            insert into mcp_tokens (
                token_id, prefix, token_hash, project_id, scopes, plan, expires_at
            ) values (
                :token_id, :prefix, :token_hash, :project_id, :scopes, :plan, :expires_at
            )
            returning token_id, prefix, project_id, scopes, plan,
                      created_at, last_used_at, revoked_at, expires_at
            """
        ),
        {
            "token_id": token_id,
            "prefix": prefix,
            "token_hash": token_hash,
            "project_id": project_id,
            "scopes": scopes,
            "plan": plan,
            "expires_at": expires_at,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else {}


async def set_token_revoked_at(
    session: AsyncSession,
    *,
    project_id: str,
    token_id: str,
    revoked_at: datetime,
) -> dict | None:
    result = await session.execute(
        text(
            """
            update mcp_tokens
            set revoked_at = :revoked_at
            where project_id = :project_id
              and token_id = :token_id
            returning token_id, prefix, project_id, scopes, plan,
                      created_at, last_used_at, revoked_at, expires_at
            """
        ),
        {
            "project_id": project_id,
            "token_id": token_id,
            "revoked_at": revoked_at,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None
