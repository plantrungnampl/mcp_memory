from __future__ import annotations

import asyncio
import secrets

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from viberecall_mcp.auth import hash_token
from viberecall_mcp.config import get_settings
from viberecall_mcp.ids import new_id


def generate_pat() -> str:
    return f"vr_mcp_sk_{secrets.token_urlsafe(32)}"


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)

    project_id = new_id("proj")
    token_id = new_id("tok")
    token = generate_pat()
    prefix = token[:16]
    token_hash = hash_token(token)
    scopes = ["memory:read", "memory:write", "facts:read", "facts:write", "timeline:read"]

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                insert into projects (id, name, owner_id, plan, retention_days, isolation_mode)
                values (:id, :name, :owner_id, :plan, :retention_days, :isolation_mode)
                """
            ),
            {
                "id": project_id,
                "name": "Local Dev Project",
                "owner_id": "dev-user",
                "plan": "pro",
                "retention_days": 30,
                "isolation_mode": "neo4j_database",
            },
        )
        await conn.execute(
            text(
                """
                insert into mcp_tokens (token_id, prefix, token_hash, project_id, scopes, plan)
                values (:token_id, :prefix, :token_hash, :project_id, :scopes, :plan)
                """
            ),
            {
                "token_id": token_id,
                "prefix": prefix,
                "token_hash": token_hash,
                "project_id": project_id,
                "scopes": scopes,
                "plan": "pro",
            },
        )

    print(f"project_id={project_id}")
    print(f"token_id={token_id}")
    print(f"token={token}")


if __name__ == "__main__":
    asyncio.run(main())
