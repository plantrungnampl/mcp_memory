from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools import FunctionTool, ToolResult
from fastapi import HTTPException, status
from mcp import types

from viberecall_mcp.auth import (
    AuthenticatedToken,
    authenticate_bearer_token,
    hash_payload,
)
from viberecall_mcp.config import get_settings
from viberecall_mcp.db import open_db_session
from viberecall_mcp.errors import ToolRuntimeError
from viberecall_mcp.ids import new_id
from viberecall_mcp.metrics import mcp_initialize_latency_ms, tool_call_latency_ms
from viberecall_mcp.mcp_server import tool_error
from viberecall_mcp.graph_routing import project_graph_name
from viberecall_mcp.repositories.audit_logs import insert_audit_log
from viberecall_mcp.repositories.tokens import touch_token_usage
from viberecall_mcp.request_context import (
    RequestContext,
    get_request_context,
    reset_request_context,
    set_request_context,
)
from viberecall_mcp.tool_access import filter_tools_for_plan
from viberecall_mcp.tool_handlers import (
    handle_delete_episode,
    handle_get_context_pack,
    handle_get_fact,
    handle_get_status,
    handle_get_operation,
    handle_get_facts,
    handle_index_repo,
    handle_index_status,
    handle_save,
    handle_search,
    handle_search_entities,
    handle_timeline,
    handle_update_fact,
    handle_working_memory_get,
    handle_working_memory_patch,
)
from viberecall_mcp.tool_registry import TOOL_DEFINITIONS

settings = get_settings()
logger = structlog.get_logger(__name__)


def build_initialize_result_model() -> types.InitializeResult:
    return types.InitializeResult(
        protocolVersion="2025-06-18",
        capabilities=types.ServerCapabilities(
            tools=types.ToolsCapability(listChanged=True),
        ),
        serverInfo=types.Implementation(
            name="viberecall-mcp",
            title="VibeRecall MCP",
            version="0.1.0",
        ),
    )


def runtime_error_to_envelope(request_id: str, exc: Exception) -> dict:
    if isinstance(exc, ToolRuntimeError):
        return tool_error(request_id, exc.code, exc.message, exc.details)
    if isinstance(exc, PermissionError):
        return tool_error(request_id, "FORBIDDEN", str(exc))
    if isinstance(exc, ValueError):
        return tool_error(request_id, "INVALID_ARGUMENT", str(exc))
    if isinstance(exc, KeyError):
        return tool_error(request_id, "INVALID_ARGUMENT", f"Unknown fact: {exc.args[0]}")
    if isinstance(exc, HTTPException):
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return tool_error(request_id, "UNAUTHENTICATED", str(exc.detail))
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            return tool_error(request_id, "FORBIDDEN", str(exc.detail))
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            return tool_error(request_id, "RATE_LIMITED", str(exc.detail))
        if exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            return tool_error(request_id, "PAYLOAD_TOO_LARGE", str(exc.detail))
        return tool_error(request_id, "INTERNAL", str(exc.detail))
    if isinstance(exc, RuntimeError):
        try:
            details = json.loads(str(exc))
            code = details.pop("code")
            return tool_error(request_id, code, code.replace("_", " ").title(), details)
        except Exception:  # noqa: BLE001
            return tool_error(request_id, "INTERNAL", str(exc))
    return tool_error(request_id, "INTERNAL", str(exc))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal, Enum)):
        return str(value)
    return value


def as_tool_result(payload: dict) -> ToolResult:
    return ToolResult(
        content=[types.TextContent(type="text", text=json.dumps(_json_safe(payload)))],
    )


def context_request_id(context: MiddlewareContext[Any]) -> str:
    message_id = getattr(context.message, "id", None)
    if message_id is not None:
        return str(message_id)
    if context.fastmcp_context is not None and context.fastmcp_context.request_context is not None:
        return context.fastmcp_context.request_id
    return new_id("req")


def get_authenticated_request_context() -> RequestContext:
    request_context = get_request_context()
    if request_context is None or request_context.project_id is None:
        raise RuntimeError("Missing request context")
    return request_context


def token_from_request_context(request_context: RequestContext) -> AuthenticatedToken:
    if request_context.token_id is None or request_context.plan is None:
        raise RuntimeError("Missing authenticated token context")
    return AuthenticatedToken(
        token_id=request_context.token_id,
        project_id=request_context.project_id or "",
        scopes=list(request_context.scopes),
        plan=request_context.plan,
        db_name=request_context.db_name or project_graph_name(request_context.project_id or ""),
    )


class VibeRecallMiddleware(Middleware):
    async def on_request(
        self,
        context: MiddlewareContext[Any],
        call_next: Callable[[MiddlewareContext[Any]], Awaitable[Any]],
    ) -> Any:
        request = get_http_request()
        project_id = request.path_params.get("project_id")
        origin = request.headers.get("origin")
        if settings.allowed_origins.strip() and origin:
            allowed = {item.strip() for item in settings.allowed_origins.split(",") if item.strip()}
            if allowed and origin not in allowed:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin is not allowed")

        if request.method.upper() == "POST":
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > settings.max_payload_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="Request payload too large",
                        )
                except ValueError:
                    pass

        protocol_version = request.headers.get("MCP-Protocol-Version") or request.headers.get(
            "mcp-protocol-version"
        )
        if context.method != "initialize":
            if protocol_version and protocol_version != "2025-06-18":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported MCP-Protocol-Version",
                )
            if protocol_version is None:
                logger.warning(
                    "missing_mcp_protocol_version_header",
                    project_id=project_id,
                )

        request_id = context_request_id(context)
        request_context = RequestContext(
            request_id=request_id,
            project_id=project_id,
            db_name=project_graph_name(project_id) if project_id else None,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )

        if context.method != "initialize":
            async with open_db_session() as session:
                token = await authenticate_bearer_token(
                    session,
                    authorization=request.headers.get("authorization"),
                    project_id=project_id or "",
                )
                await touch_token_usage(session, token.token_id)
            request_context = replace(
                request_context,
                token_id=token.token_id,
                plan=token.plan,
                scopes=tuple(token.scopes),
                db_name=token.db_name,
            )

        marker = set_request_context(request_context)
        try:
            return await call_next(context)
        finally:
            reset_request_context(marker)

    async def on_initialize(
        self,
        context: MiddlewareContext[types.InitializeRequest],
        call_next: Callable[[MiddlewareContext[types.InitializeRequest]], Awaitable[types.InitializeResult | None]],
    ) -> types.InitializeResult | None:
        start = time.perf_counter()
        await call_next(context)
        request_context = get_request_context()
        if request_context is not None:
            async with open_db_session() as session:
                await insert_audit_log(
                    session,
                    request_id=request_context.request_id,
                    action="initialize",
                    status="ok",
                    project_id=request_context.project_id,
                )
        mcp_initialize_latency_ms.observe((time.perf_counter() - start) * 1000)
        return build_initialize_result_model()

    async def on_list_tools(
        self,
        context: MiddlewareContext[types.ListToolsRequest],
        call_next: Callable[[MiddlewareContext[types.ListToolsRequest]], Awaitable[list[Any]]],
    ) -> list[Any]:
        request_context = get_authenticated_request_context()
        tools = filter_tools_for_plan(request_context.plan or "free", list(await call_next(context)))
        async with open_db_session() as session:
            await insert_audit_log(
                session,
                request_id=request_context.request_id,
                action="tools/list",
                status="ok",
                project_id=request_context.project_id,
                token_id=request_context.token_id,
            )
        return tools


async def run_tool(tool_name: str, arguments: dict[str, Any]) -> ToolResult:
    request_context = get_authenticated_request_context()
    token = token_from_request_context(request_context)
    args_hash = hash_payload(json.dumps(arguments, sort_keys=True, default=str))
    tool_context = replace(request_context, tool_name=tool_name)
    marker = set_request_context(tool_context)

    try:
        start = time.perf_counter()
        async with open_db_session() as session:
            handler_arguments = {**arguments, "session": session}
            try:
                if tool_name == "viberecall_save":
                    payload = await handle_save(
                        tool_name=tool_name,
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                        payload_hash=args_hash,
                        idempotency_key=request_context.idempotency_key
                        or arguments.get("idempotency_key"),
                    )
                elif tool_name == "viberecall_save_episode":
                    payload = await handle_save(
                        tool_name=tool_name,
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                        payload_hash=args_hash,
                        idempotency_key=request_context.idempotency_key
                        or arguments.get("idempotency_key"),
                    )
                elif tool_name == "viberecall_search":
                    payload = await handle_search(
                        tool_name=tool_name,
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_search_memory":
                    payload = await handle_search(
                        tool_name=tool_name,
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_get_facts":
                    payload = await handle_get_facts(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_update_fact":
                    payload = await handle_update_fact(
                        tool_name=tool_name,
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                        payload_hash=args_hash,
                        idempotency_key=request_context.idempotency_key
                        or arguments.get("idempotency_key"),
                    )
                elif tool_name == "viberecall_timeline":
                    payload = await handle_timeline(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_get_status":
                    payload = await handle_get_status(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_get_operation":
                    payload = await handle_get_operation(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_delete_episode":
                    payload = await handle_delete_episode(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_index_repo":
                    payload = await handle_index_repo(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_index_status":
                    payload = await handle_index_status(
                        tool_name=tool_name,
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_get_index_status":
                    payload = await handle_index_status(
                        tool_name=tool_name,
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_get_fact":
                    payload = await handle_get_fact(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_search_entities":
                    payload = await handle_search_entities(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_get_context_pack":
                    payload = await handle_get_context_pack(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_working_memory_get":
                    payload = await handle_working_memory_get(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                elif tool_name == "viberecall_working_memory_patch":
                    payload = await handle_working_memory_patch(
                        request_id=request_context.request_id,
                        project_id=request_context.project_id or "",
                        token=token,
                        arguments=handler_arguments,
                    )
                else:
                    payload = tool_error(
                        request_context.request_id,
                        "INVALID_ARGUMENT",
                        f"Unknown tool: {tool_name}",
                    )
            except Exception as exc:  # noqa: BLE001
                payload = runtime_error_to_envelope(request_context.request_id, exc)
                try:
                    await session.rollback()
                except Exception as rollback_exc:  # noqa: BLE001
                    logger.warning(
                        "tool_call_rollback_failed",
                        request_id=request_context.request_id,
                        project_id=request_context.project_id,
                        tool_name=tool_name,
                        error=str(rollback_exc),
                    )
                elapsed_ms = (time.perf_counter() - start) * 1000
                try:
                    await insert_audit_log(
                        session,
                        request_id=request_context.request_id,
                        action="tools/call",
                        status="error",
                        project_id=request_context.project_id,
                        token_id=request_context.token_id,
                        tool_name=tool_name,
                        args_hash=args_hash,
                        latency_ms=elapsed_ms,
                    )
                except Exception as audit_exc:  # noqa: BLE001
                    logger.warning(
                        "tool_call_error_audit_failed",
                        request_id=request_context.request_id,
                        project_id=request_context.project_id,
                        tool_name=tool_name,
                        error=str(audit_exc),
                    )
                tool_call_latency_ms.labels(tool=tool_name).observe(elapsed_ms)
                logger.info(
                    "tool_call",
                    request_id=request_context.request_id,
                    mcp_session_id=get_http_request().headers.get("mcp-session-id"),
                    project_id=request_context.project_id,
                    token_id=request_context.token_id,
                    tool_name=tool_name,
                    args_hash=args_hash,
                    latency_ms=elapsed_ms,
                    status="error",
                    error_code=payload.get("error", {}).get("code"),
                )
                return as_tool_result(payload)

            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                await insert_audit_log(
                    session,
                    request_id=request_context.request_id,
                    action="tools/call",
                    status="ok",
                    project_id=request_context.project_id,
                    token_id=request_context.token_id,
                    tool_name=tool_name,
                    args_hash=args_hash,
                    latency_ms=elapsed_ms,
                )
            except Exception as audit_exc:  # noqa: BLE001
                logger.warning(
                    "tool_call_success_audit_failed",
                    request_id=request_context.request_id,
                    project_id=request_context.project_id,
                    tool_name=tool_name,
                    error=str(audit_exc),
                )
            tool_call_latency_ms.labels(tool=tool_name).observe(elapsed_ms)
            logger.info(
                "tool_call",
                request_id=request_context.request_id,
                mcp_session_id=get_http_request().headers.get("mcp-session-id"),
                project_id=request_context.project_id,
                token_id=request_context.token_id,
                tool_name=tool_name,
                args_hash=args_hash,
                latency_ms=elapsed_ms,
                status="ok",
                error_code=None,
            )
            return as_tool_result(payload)
    finally:
        reset_request_context(marker)


def make_tool_wrapper(tool_name: str):
    async def wrapper(**kwargs: Any) -> ToolResult:
        return await run_tool(tool_name, kwargs)

    return wrapper


def build_fastmcp_server() -> FastMCP:
    server = FastMCP("viberecall-mcp")
    server.add_middleware(VibeRecallMiddleware())

    for tool in TOOL_DEFINITIONS:
        server.add_tool(
            FunctionTool(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_schema,
                output_schema=None,
                fn=make_tool_wrapper(tool.name),
            )
        )

    return server


def build_fastmcp_http_app(
    *,
    path: str = "/p/{project_id}/mcp",
    stateless_http: bool = False,
):
    server = build_fastmcp_server()
    return server.http_app(
        path=path,
        transport="streamable-http",
        stateless_http=stateless_http,
    )
