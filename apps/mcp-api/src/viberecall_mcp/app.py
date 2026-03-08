from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi import Response

from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane import router as control_plane_router
from viberecall_mcp.ids import new_id
from viberecall_mcp.logging import configure_logging
from viberecall_mcp.mcp_app import build_fastmcp_http_app
from viberecall_mcp.metrics import metrics_response
from viberecall_mcp.runtime import probe_runtime_dependencies


settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    mcp_http_app = build_fastmcp_http_app()
    application = FastAPI(
        title="VibeRecall MCP API",
        version="0.1.0",
        lifespan=mcp_http_app.lifespan,
    )

    @application.middleware("http")
    async def attach_request_id(request, call_next):
        request_id = request.headers.get("X-Request-Id", "").strip() or new_id("req")
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "http_request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            )
            raise
        response.headers["X-Request-Id"] = request_id
        return response

    application.include_router(control_plane_router)

    @application.get("/healthz")
    async def healthz() -> dict:
        dependency_state = await probe_runtime_dependencies()
        return {
            "status": dependency_state["status"],
            "service": "viberecall-mcp",
            "runtime": dependency_state["runtime"],
            "checks": dependency_state["checks"],
        }

    @application.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = metrics_response()
        return Response(content=payload, media_type=content_type)

    application.mount("/", mcp_http_app)
    return application


app = create_app()
