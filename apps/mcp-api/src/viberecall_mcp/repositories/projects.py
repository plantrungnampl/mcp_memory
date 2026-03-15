from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_project(session: AsyncSession, project_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            select id, name, owner_id, plan, retention_days, isolation_mode, created_at
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
            select id, name, owner_id, plan, retention_days, isolation_mode, created_at
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
    isolation_mode: str = "falkordb_graph",
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


async def create_project_memory_link(
    session: AsyncSession,
    *,
    project_id: str,
    linked_project_id: str,
) -> dict:
    left_id, right_id = sorted((project_id, linked_project_id))
    result = await session.execute(
        text(
            """
            insert into project_memory_links (project_id, linked_project_id)
            values (:project_id, :linked_project_id)
            on conflict (project_id, linked_project_id) do update
            set linked_project_id = excluded.linked_project_id
            returning project_id, linked_project_id, created_at
            """
        ),
        {
            "project_id": left_id,
            "linked_project_id": right_id,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else {}


async def delete_project_memory_link(
    session: AsyncSession,
    *,
    project_id: str,
    linked_project_id: str,
) -> bool:
    left_id, right_id = sorted((project_id, linked_project_id))
    result = await session.execute(
        text(
            """
            delete from project_memory_links
            where project_id = :project_id
              and linked_project_id = :linked_project_id
            """
        ),
        {
            "project_id": left_id,
            "linked_project_id": right_id,
        },
    )
    return bool(result.rowcount)


async def list_project_memory_links(
    session: AsyncSession,
    *,
    project_id: str,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            select p.id, p.name, p.owner_id, p.plan, p.retention_days, p.isolation_mode, p.created_at
            from project_memory_links l
            join projects p
              on p.id = case
                    when l.project_id = :project_id then l.linked_project_id
                    else l.project_id
                  end
            where l.project_id = :project_id
               or l.linked_project_id = :project_id
            order by p.created_at desc, p.id desc
            """
        ),
        {"project_id": project_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def resolve_memory_scope_project_ids(
    session: AsyncSession,
    *,
    project_id: str,
    requested_scope: str,
) -> tuple[list[str], str]:
    if requested_scope == "project":
        return [project_id], "project"

    project = await get_project(session, project_id)
    if project is None:
        return [project_id], "project"

    if requested_scope == "org":
        owner_id = project.get("owner_id")
        if not owner_id:
            return [project_id], "project"
        result = await session.execute(
            text(
                """
                select id
                from projects
                where owner_id = :owner_id
                order by created_at desc, id desc
                """
            ),
            {"owner_id": owner_id},
        )
        project_ids = [str(row["id"]) for row in result.mappings().all()]
        return project_ids or [project_id], "org"

    if requested_scope == "linked":
        result = await session.execute(
            text(
                """
                select distinct case
                    when project_id = :project_id then linked_project_id
                    else project_id
                  end as project_id
                from project_memory_links
                where project_id = :project_id
                   or linked_project_id = :project_id
                order by project_id
                """
            ),
            {"project_id": project_id},
        )
        linked_ids = [str(row["project_id"]) for row in result.mappings().all()]
        ordered = [project_id, *[candidate for candidate in linked_ids if candidate != project_id]]
        return ordered, "linked"

    return [project_id], "project"


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
