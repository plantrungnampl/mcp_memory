from __future__ import annotations

from viberecall_mcp.auth import AuthenticatedToken

import viberecall_mcp.tool_handlers as root


async def handle_get_status(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    _ = arguments
    root.ensure_plan_access(token, "viberecall_get_status")
    root.ensure_scope(token, "ops:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_get_operation")

    graphiti_enabled = bool((root.settings.graphiti_api_key or "").strip())
    status = "ok"
    detail = "ready"
    dependency_detail = await root.get_graph_dependency_failure_detail()
    if dependency_detail is not None:
        status = "degraded"
        detail = dependency_detail
    elif root.settings.memory_backend == "graphiti":
        if root.settings.graphiti_mcp_bridge_mode == "upstream_bridge":
            status, detail = await root.get_graphiti_upstream_bridge().status(project_id)
        elif not graphiti_enabled:
            status = "degraded"
            detail = "GRAPHITI_API_KEY is empty"

    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "status": status,
            "service": "viberecall-mcp",
            "project_id": project_id,
            "backends": {
                "memory_backend": root.settings.memory_backend,
                "queue_backend": root.settings.queue_backend,
            },
            "graphiti": {
                "enabled": graphiti_enabled,
                "detail": detail,
            },
        },
    )


async def handle_get_operation(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_get_operation")
    root.ensure_scope(token, "ops:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_get_operation")
    await root.dispatch_outbox_events(arguments["session"], operation_id=str(arguments["operation_id"]), limit=1)
    operation = await root.get_operation_record(
        arguments["session"],
        project_id=project_id,
        operation_id=str(arguments["operation_id"]),
    )
    if operation is None:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Operation not found",
            {"operation_id": arguments["operation_id"]},
        )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={"operation": root._operation_payload(operation)},
    )


async def handle_working_memory_get(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_working_memory_get")
    root.ensure_scope(token, "memory:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_working_memory_get")

    task_id = str(arguments["task_id"])
    session_id = str(arguments["session_id"])
    row = await root.get_working_memory(
        arguments["session"],
        project_id=project_id,
        task_id=task_id,
        session_id=session_id,
    )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=root._working_memory_response(row, task_id=task_id, session_id=session_id),
    )


async def handle_working_memory_patch(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_working_memory_patch")
    root.ensure_scope(token, "memory:write")
    await root.enforce_rate_limit(token, project_id, "viberecall_working_memory_patch")

    task_id = str(arguments["task_id"])
    session_id = str(arguments["session_id"])
    row = await root.patch_working_memory(
        arguments["session"],
        project_id=project_id,
        task_id=task_id,
        session_id=session_id,
        patch=dict(arguments.get("patch") or {}),
        checkpoint_note=arguments.get("checkpoint_note"),
        expires_at=arguments.get("expires_at"),
        commit=True,
    )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=root._working_memory_response(row, task_id=task_id, session_id=session_id),
    )
