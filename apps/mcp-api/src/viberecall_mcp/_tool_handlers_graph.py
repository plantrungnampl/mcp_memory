from __future__ import annotations

from viberecall_mcp.auth import AuthenticatedToken

import viberecall_mcp.tool_handlers as root


async def handle_search_entities(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_search_entities")
    root.ensure_scope(token, "entities:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_search_entities")

    result = await root.search_canonical_entities(
        session=arguments["session"],
        project_id=project_id,
        query=str(arguments["query"]),
        entity_kinds=root._normalize_entity_kinds(arguments),
        salience_classes=root._normalize_salience_classes(arguments.get("salience_classes")),
        limit=int(arguments.get("limit", 20)),
    )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=result,
    )


async def handle_resolve_reference(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_resolve_reference")
    root.ensure_scope(token, "entities:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_resolve_reference")

    result = await root.resolve_canonical_reference(
        session=arguments["session"],
        project_id=project_id,
        mention_text=str(arguments["mention_text"]),
        observed_kind=str(arguments.get("observed_kind") or "").strip() or None,
        repo_scope=str(arguments.get("repo_scope") or "").strip() or None,
        include_code_index=bool(arguments.get("include_code_index", True)),
        limit=int(arguments.get("limit", 5)),
    )
    if result.get("unresolved_mention") is not None:
        await arguments["session"].commit()
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=result,
    )


async def handle_get_neighbors(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_get_neighbors")
    root.ensure_scope(token, "graph:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_get_neighbors")

    depth = int(arguments.get("depth", 1))
    if depth != 1:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "depth must equal 1 in this release",
            {"depth": depth},
        )

    result = await root.get_canonical_neighbors(
        session=arguments["session"],
        project_id=project_id,
        entity_id=str(arguments["entity_id"]),
        direction=str(arguments.get("direction") or "BOTH").upper(),
        relation_types=[str(item) for item in (arguments.get("relation_types") or [])],
        current_only=bool(arguments.get("current_only", True)),
        valid_at=arguments.get("valid_at"),
        as_of_system_time=arguments.get("as_of_system_time"),
        limit=int(arguments.get("limit", 20)),
    )
    if result is None:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Entity not found",
            {"entity_id": arguments["entity_id"]},
        )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=result,
    )


async def handle_find_paths(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_find_paths")
    root.ensure_scope(token, "graph:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_find_paths")

    src_entity_id = str(arguments["src_entity_id"])
    dst_entity_id = str(arguments["dst_entity_id"])
    max_depth = int(arguments.get("max_depth", 2))
    if src_entity_id == dst_entity_id:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "src_entity_id and dst_entity_id must differ",
            {
                "src_entity_id": src_entity_id,
                "dst_entity_id": dst_entity_id,
            },
        )
    if max_depth < 1 or max_depth > 3:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "max_depth must be between 1 and 3",
            {"max_depth": max_depth},
        )

    result = await root.find_canonical_paths(
        session=arguments["session"],
        project_id=project_id,
        src_entity_id=src_entity_id,
        dst_entity_id=dst_entity_id,
        relation_types=[str(item) for item in (arguments.get("relation_types") or [])],
        max_depth=max_depth,
        current_only=bool(arguments.get("current_only", True)),
        valid_at=arguments.get("valid_at"),
        as_of_system_time=arguments.get("as_of_system_time"),
        limit_paths=int(arguments.get("limit_paths", 5)),
    )
    missing_entity_id = result.pop("missing_entity_id", None)
    if missing_entity_id is not None:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Entity not found",
            {"entity_id": missing_entity_id},
        )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=result,
    )


async def handle_explain_fact(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_explain_fact")
    root.ensure_scope(token, "memory:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_explain_fact")

    result = await root.explain_canonical_fact(
        session=arguments["session"],
        project_id=project_id,
        fact_version_id=str(arguments["fact_version_id"]),
    )
    if result is None:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Fact version not found",
            {"fact_version_id": arguments["fact_version_id"]},
        )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=result,
    )
