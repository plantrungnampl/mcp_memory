from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def insert_audit_log(
    session: AsyncSession,
    *,
    request_id: str,
    action: str,
    status: str,
    project_id: str | None = None,
    token_id: str | None = None,
    tool_name: str | None = None,
    args_hash: str | None = None,
) -> None:
    await session.execute(
        text(
            """
            insert into audit_logs (
                request_id, project_id, token_id, tool_name, action, args_hash, status
            ) values (
                :request_id, :project_id, :token_id, :tool_name, :action, :args_hash, :status
            )
            """
        ),
        {
            "request_id": request_id,
            "project_id": project_id,
            "token_id": token_id,
            "tool_name": tool_name,
            "action": action,
            "args_hash": args_hash,
            "status": status,
        },
    )
    await session.commit()


async def list_audit_logs_for_project(
    session: AsyncSession,
    *,
    project_id: str,
    limit: int,
    cursor: int | None = None,
) -> list[dict]:
    if cursor is None:
        result = await session.execute(
            text(
                """
                select
                  id,
                  request_id,
                  project_id,
                  token_id,
                  tool_name,
                  action,
                  args_hash,
                  status,
                  created_at
                from audit_logs
                where project_id = :project_id
                order by id desc
                limit :limit
                """
            ),
            {"project_id": project_id, "limit": limit},
        )
    else:
        result = await session.execute(
            text(
                """
                select
                  id,
                  request_id,
                  project_id,
                  token_id,
                  tool_name,
                  action,
                  args_hash,
                  status,
                  created_at
                from audit_logs
                where project_id = :project_id
                  and id < :cursor
                order by id desc
                limit :limit
                """
            ),
            {"project_id": project_id, "cursor": cursor, "limit": limit},
        )
    return [dict(row) for row in result.mappings().all()]
