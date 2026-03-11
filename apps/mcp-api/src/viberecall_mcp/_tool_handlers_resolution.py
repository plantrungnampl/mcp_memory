from __future__ import annotations

from viberecall_mcp.auth import AuthenticatedToken

import viberecall_mcp.tool_handlers as root


async def handle_merge_entities(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_merge_entities")
    root.ensure_scope(token, "resolution:write")
    await root.enforce_rate_limit(token, project_id, "viberecall_merge_entities")

    target_entity_id = str(arguments["target_entity_id"])
    source_entity_ids = [str(item) for item in (arguments.get("source_entity_ids") or []) if str(item).strip()]
    if target_entity_id in source_entity_ids:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "target_entity_id must not appear in source_entity_ids",
            {
                "target_entity_id": target_entity_id,
                "source_entity_ids": source_entity_ids,
            },
        )

    session = arguments["session"]
    operation_id = root.new_id("op")
    resolution_event_id = root.new_id("res")
    await root.create_operation(
        session,
        operation_id=operation_id,
        project_id=project_id,
        token_id=token.token_id,
        request_id=request_id,
        kind="ENTITY_RESOLUTION",
        resource_type="entity_resolution",
        resource_id=resolution_event_id,
        metadata={
            "event_kind": "MERGE",
            "target_entity_id": target_entity_id,
            "source_entity_ids": source_entity_ids,
        },
    )
    try:
        result = await root.merge_canonical_entities(
            session,
            project_id=project_id,
            operation_id=operation_id,
            resolution_event_id=resolution_event_id,
            target_entity_id=target_entity_id,
            source_entity_ids=source_entity_ids,
            reason=str(arguments.get("reason") or "").strip() or None,
        )
    except KeyError as exc:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Entity not found",
            {"entity_id": str(exc.args[0])},
        ) from exc
    except ValueError as exc:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            str(exc),
            {},
        ) from exc

    outbox_payload = {
        "request_id": request_id,
        "token_id": token.token_id,
        "resolution_event_id": resolution_event_id,
        "event_kind": "MERGE",
        "canonical_target_entity_id": result["canonical_target_entity_id"],
        "entity_ids": [result["canonical_target_entity_id"], *result["redirected_entity_ids"]],
        "result_payload": {
            "resolution_event_id": resolution_event_id,
            "event_kind": "MERGE",
            "canonical_target_entity_id": result["canonical_target_entity_id"],
            "redirected_entity_ids": list(result["redirected_entity_ids"]),
        },
    }
    await root.create_outbox_event(
        session,
        event_id=root.new_id("evt"),
        operation_id=operation_id,
        project_id=project_id,
        event_type="entity_resolution.search_reproject",
        payload=outbox_payload,
    )
    await root.create_outbox_event(
        session,
        event_id=root.new_id("evt"),
        operation_id=operation_id,
        project_id=project_id,
        event_type="entity_resolution.graph_reproject",
        payload=outbox_payload,
    )
    await session.commit()
    await root.dispatch_outbox_events(session, operation_id=operation_id, limit=10)
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "accepted": True,
            "operation_id": operation_id,
            "resolution_event_id": resolution_event_id,
            "canonical_target_entity_id": result["canonical_target_entity_id"],
            "redirected_entity_ids": list(result["redirected_entity_ids"]),
        },
    )


async def handle_split_entity(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_split_entity")
    root.ensure_scope(token, "resolution:write")
    await root.enforce_rate_limit(token, project_id, "viberecall_split_entity")

    session = arguments["session"]
    operation_id = root.new_id("op")
    resolution_event_id = root.new_id("res")
    source_entity_id = str(arguments["source_entity_id"])
    partitions = list(arguments.get("partitions") or [])

    await root.create_operation(
        session,
        operation_id=operation_id,
        project_id=project_id,
        token_id=token.token_id,
        request_id=request_id,
        kind="ENTITY_RESOLUTION",
        resource_type="entity_resolution",
        resource_id=resolution_event_id,
        metadata={
            "event_kind": "SPLIT",
            "source_entity_id": source_entity_id,
        },
    )
    try:
        result = await root.split_canonical_entity(
            session,
            project_id=project_id,
            operation_id=operation_id,
            resolution_event_id=resolution_event_id,
            source_entity_id=source_entity_id,
            partitions=partitions,
            reason=str(arguments.get("reason") or "").strip() or None,
        )
    except KeyError as exc:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Entity or fact not found",
            {"id": str(exc.args[0])},
        ) from exc
    except ValueError as exc:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            str(exc),
            {},
        ) from exc

    outbox_payload = {
        "request_id": request_id,
        "token_id": token.token_id,
        "resolution_event_id": resolution_event_id,
        "event_kind": "SPLIT",
        "source_entity_id": source_entity_id,
        "entity_ids": [source_entity_id, *result["created_entity_ids"]],
        "result_payload": {
            "resolution_event_id": resolution_event_id,
            "event_kind": "SPLIT",
            "source_entity_id": source_entity_id,
            "created_entity_ids": list(result["created_entity_ids"]),
            "reassigned_aliases": int(result["reassigned_aliases"]),
            "reassigned_facts": int(result["reassigned_facts"]),
        },
    }
    await root.create_outbox_event(
        session,
        event_id=root.new_id("evt"),
        operation_id=operation_id,
        project_id=project_id,
        event_type="entity_resolution.search_reproject",
        payload=outbox_payload,
    )
    await root.create_outbox_event(
        session,
        event_id=root.new_id("evt"),
        operation_id=operation_id,
        project_id=project_id,
        event_type="entity_resolution.graph_reproject",
        payload=outbox_payload,
    )
    await session.commit()
    await root.dispatch_outbox_events(session, operation_id=operation_id, limit=10)
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "accepted": True,
            "operation_id": operation_id,
            "resolution_event_id": resolution_event_id,
            "created_entity_ids": list(result["created_entity_ids"]),
            "reassigned_aliases": int(result["reassigned_aliases"]),
            "reassigned_facts": int(result["reassigned_facts"]),
        },
    )
