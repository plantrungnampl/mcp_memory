from __future__ import annotations

from fastapi import FastAPI
from fastapi import Response

from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane import router as control_plane_router
from viberecall_mcp.logging import configure_logging
from viberecall_mcp.mcp_app import build_fastmcp_http_app
from viberecall_mcp.metrics import metrics_response


settings = get_settings()
configure_logging(settings.log_level)


def create_app() -> FastAPI:
    mcp_http_app = build_fastmcp_http_app()
    application = FastAPI(
        title="VibeRecall MCP API",
        version="0.1.0",
        lifespan=mcp_http_app.lifespan,
    )
    application.include_router(control_plane_router)

    @application.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok", "service": "viberecall-mcp"}

    @application.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = metrics_response()
        return Response(content=payload, media_type=content_type)

    application.mount("/", mcp_http_app)
    return application


app = create_app()
