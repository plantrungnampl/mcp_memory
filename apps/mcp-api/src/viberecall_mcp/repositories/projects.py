from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_project(session: AsyncSession, project_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select id, name, plan, retention_days, isolation_mode, created_at
            from projects
            where id = :project_id
            """
        ),
        {"project_id": project_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_projects(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        text(
            """
            select id, name, plan, retention_days, isolation_mode, created_at
            from projects
            order by created_at desc, id desc
            """
        )
    )
    return [dict(row) for row in result.mappings().all()]


async def list_projects_for_owner(
    session: AsyncSession,
    *,
    owner_id: str,
    include_unowned: bool,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select id, name, owner_id, plan, retention_days, isolation_mode, created_at
            from projects
            where owner_id = :owner_id
               or (:include_unowned and owner_id is null)
            order by created_at desc, id desc
            """
        ),
        {
            "owner_id": owner_id,
            "include_unowned": include_unowned,
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def get_project_for_owner(
    session: AsyncSession,
    *,
    project_id: str,
    owner_id: str,
    include_unowned: bool,
) -> dict | None:
    result = await session.execute(
        text(
            """
            select id, name, owner_id, plan, retention_days, isolation_mode, created_at
            from projects
            where id = :project_id
              and (
                owner_id = :owner_id
                or (:include_unowned and owner_id is null)
              )
            """
        ),
        {
            "project_id": project_id,
            "owner_id": owner_id,
            "include_unowned": include_unowned,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def create_project(
    session: AsyncSession,
    *,
    project_id: str,
    owner_id: str,
    name: str,
    plan: str,
    retention_days: int = 30,
    isolation_mode: str = "neo4j_database",
) -> dict:
    result = await session.execute(
        text(
            """
            insert into projects (
                id, name, owner_id, plan, retention_days, isolation_mode
            ) values (
                :project_id, :name, :owner_id, :plan, :retention_days, :isolation_mode
            )
            returning id, name, owner_id, plan, retention_days, isolation_mode, created_at
            """
        ),
        {
            "project_id": project_id,
            "name": name,
            "owner_id": owner_id,
            "plan": plan,
            "retention_days": retention_days,
            "isolation_mode": isolation_mode,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else {}


async def claim_project_owner_if_unowned(
    session: AsyncSession,
    *,
    project_id: str,
    owner_id: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            update projects
            set owner_id = :owner_id
            where id = :project_id
              and owner_id is null
            returning id, name, owner_id, plan, retention_days, isolation_mode, created_at
            """
        ),
        {
            "project_id": project_id,
            "owner_id": owner_id,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def update_project_plan(
    session: AsyncSession,
    *,
    project_id: str,
    plan: str,
) -> dict | None:
    result = await session.execute(
        text(
            """
            update projects
            set plan = :plan
            where id = :project_id
            returning id, name, owner_id, plan, retention_days, isolation_mode, created_at
            """
        ),
        {
            "project_id": project_id,
            "plan": plan,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_project_overview_for_owner(
    session: AsyncSession,
    *,
    owner_id: str,
    include_unowned: bool,
    window_days: int,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            with usage_agg as (
              select
                ue.project_id,
                coalesce(sum(ue.vibe_tokens), 0) as vibe_tokens_window,
                max(ue.ts) as last_activity_at
              from usage_events ue
              where ue.ts >= now() - (:window_days * interval '1 day')
              group by ue.project_id
            ),
            latest_token as (
              select distinct on (mt.project_id)
                mt.project_id,
                mt.prefix,
                mt.revoked_at,
                mt.created_at
              from mcp_tokens mt
              order by mt.project_id, mt.created_at desc
            )
            select
              p.id,
              p.name,
              p.plan,
              p.created_at,
              ua.last_activity_at,
              coalesce(ua.vibe_tokens_window, 0) as vibe_tokens_window,
              lt.prefix as token_preview,
              case
                when lt.project_id is null then 'missing'
                when lt.revoked_at is null then 'active'
                when lt.revoked_at > now() then 'grace'
                else 'revoked'
              end as token_status,
              case
                when lt.project_id is null then 'error'
                when lt.revoked_at is not null and lt.revoked_at <= now() then 'error'
                when ua.last_activity_at is null then 'idle'
                when ua.last_activity_at >= now() - interval '1 hour' then 'active'
                else 'idle'
              end as health_status
            from projects p
            left join usage_agg ua on ua.project_id = p.id
            left join latest_token lt on lt.project_id = p.id
            where p.owner_id = :owner_id
               or (:include_unowned and p.owner_id is null)
            order by p.created_at desc, p.id desc
            """
        ),
        {
            "owner_id": owner_id,
            "include_unowned": include_unowned,
            "window_days": window_days,
        },
    )
    return [dict(row) for row in result.mappings().all()]
