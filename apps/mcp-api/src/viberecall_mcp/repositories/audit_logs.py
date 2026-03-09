from datetime import datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ApiLogStatusFilter = Literal["all", "success", "error"]


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
    latency_ms: float | None = None,
    commit: bool = True,
) -> None:
    await session.execute(
        text(
            """
            insert into audit_logs (
                request_id, project_id, token_id, tool_name, action, args_hash, status, latency_ms
            ) values (
                :request_id, :project_id, :token_id, :tool_name, :action, :args_hash, :status, :latency_ms
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
            "latency_ms": latency_ms,
        },
    )
    if commit:
        await session.commit()


def _build_audit_logs_filters(
    *,
    project_id: str,
    status_filter: ApiLogStatusFilter = "all",
    action_name: str | None = None,
    tool_name: str | None = None,
    search_query: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    table_alias: str | None = None,
) -> tuple[str, dict]:
    prefix = f"{table_alias}." if table_alias else ""
    filters = [f"{prefix}project_id = :project_id"]
    params: dict[str, object] = {"project_id": project_id}

    if start_at is not None:
        filters.append(f"{prefix}created_at >= :start_at")
        params["start_at"] = start_at
    if end_at is not None:
        filters.append(f"{prefix}created_at < :end_at")
        params["end_at"] = end_at

    if status_filter == "success":
        filters.append(f"{prefix}status = 'ok'")
    elif status_filter == "error":
        filters.append(f"{prefix}status <> 'ok'")

    if action_name:
        filters.append(f"{prefix}action = :action_name")
        params["action_name"] = action_name

    if tool_name:
        filters.append(f"{prefix}tool_name = :tool_name")
        params["tool_name"] = tool_name

    if search_query:
        filters.append(
            "("
            f"{prefix}request_id ilike :search_query "
            f"or {prefix}action ilike :search_query "
            f"or coalesce({prefix}tool_name, '') ilike :search_query "
            f"or coalesce({prefix}token_id, '') ilike :search_query"
            ")"
        )
        params["search_query"] = f"%{search_query}%"

    return " and ".join(filters), params


async def get_api_logs_summary(
    session: AsyncSession,
    *,
    project_id: str,
    status_filter: ApiLogStatusFilter = "all",
    action_name: str | None = None,
    tool_name: str | None = None,
    search_query: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> dict:
    where_sql, params = _build_audit_logs_filters(
        project_id=project_id,
        status_filter=status_filter,
        action_name=action_name,
        tool_name=tool_name,
        search_query=search_query,
        start_at=start_at,
        end_at=end_at,
    )
    result = await session.execute(
        text(
            f"""
            select
              count(*)::bigint as total_requests,
              coalesce(avg(case when status = 'ok' then 1.0 else 0.0 end) * 100.0, 0) as success_rate_pct,
              coalesce(sum(case when status <> 'ok' then 1 else 0 end), 0)::bigint as error_count,
              percentile_cont(0.95) within group (order by latency_ms) as p95_latency_ms
            from audit_logs
            where {where_sql}
            """
        ),
        params,
    )
    row = result.mappings().first()
    if row is None:
        return {
            "total_requests": 0,
            "success_rate_pct": 0,
            "error_count": 0,
            "p95_latency_ms": None,
        }
    return dict(row)


async def count_api_logs_rows(
    session: AsyncSession,
    *,
    project_id: str,
    status_filter: ApiLogStatusFilter = "all",
    action_name: str | None = None,
    tool_name: str | None = None,
    search_query: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> int:
    where_sql, params = _build_audit_logs_filters(
        project_id=project_id,
        status_filter=status_filter,
        action_name=action_name,
        tool_name=tool_name,
        search_query=search_query,
        start_at=start_at,
        end_at=end_at,
        table_alias="l",
    )
    result = await session.execute(
        text(
            f"""
            select count(*)::bigint as total
            from audit_logs l
            where {where_sql}
            """
        ),
        params,
    )
    row = result.mappings().first()
    return int(row["total"]) if row else 0


async def list_api_logs_rows(
    session: AsyncSession,
    *,
    project_id: str,
    offset: int,
    limit: int,
    status_filter: ApiLogStatusFilter = "all",
    action_name: str | None = None,
    tool_name: str | None = None,
    search_query: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[dict]:
    where_sql, params = _build_audit_logs_filters(
        project_id=project_id,
        status_filter=status_filter,
        action_name=action_name,
        tool_name=tool_name,
        search_query=search_query,
        start_at=start_at,
        end_at=end_at,
        table_alias="l",
    )
    params["offset"] = offset
    params["limit"] = limit
    result = await session.execute(
        text(
            f"""
            select
              l.id,
              l.request_id,
              l.project_id,
              l.token_id,
              l.tool_name,
              l.action,
              l.args_hash,
              l.status,
              l.created_at,
              l.latency_ms,
              t.prefix as token_prefix
            from audit_logs l
            left join mcp_tokens t on t.token_id = l.token_id
            where {where_sql}
            order by l.id desc
            offset :offset
            limit :limit
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


async def list_api_logs_tools(
    session: AsyncSession,
    *,
    project_id: str,
    action_name: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[str]:
    where_sql, params = _build_audit_logs_filters(
        project_id=project_id,
        action_name=action_name,
        start_at=start_at,
        end_at=end_at,
        table_alias="l",
    )
    result = await session.execute(
        text(
            f"""
            select distinct l.tool_name
            from audit_logs l
            where {where_sql}
              and l.tool_name is not null
            order by l.tool_name asc
            limit 64
            """
        ),
        params,
    )
    return [str(row["tool_name"]) for row in result.mappings().all()]


async def list_audit_logs_for_project(
    session: AsyncSession,
    *,
    project_id: str,
    limit: int,
    cursor: int | None = None,
    action_name: str | None = None,
) -> list[dict]:
    where_sql, params = _build_audit_logs_filters(
        project_id=project_id,
        action_name=action_name,
    )
    if cursor is not None:
        where_sql = f"{where_sql} and id < :cursor"
        params["cursor"] = cursor
    params["limit"] = limit
    result = await session.execute(
        text(
            f"""
            select
              id,
              request_id,
              project_id,
              token_id,
              tool_name,
              action,
              args_hash,
              status,
              created_at,
              latency_ms
            from audit_logs
            where {where_sql}
            order by id desc
            limit :limit
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]
