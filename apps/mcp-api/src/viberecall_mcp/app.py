from __future__ import annotations

import hashlib
from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, status
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from viberecall_mcp.auth import authenticate_bearer_token
from viberecall_mcp.code_index import validate_workspace_bundle_archive
from viberecall_mcp.config import get_settings
from viberecall_mcp.control_plane import router as control_plane_router
from viberecall_mcp.db import get_db_session
from viberecall_mcp.ids import new_id
from viberecall_mcp.logging import configure_logging
from viberecall_mcp.mcp_app import build_fastmcp_http_app
from viberecall_mcp.metrics import metrics_response
from viberecall_mcp.object_storage import bundle_storage_key, put_bytes
from viberecall_mcp.repositories.audit_logs import insert_audit_log
from viberecall_mcp.repositories.index_bundles import create_index_bundle
from viberecall_mcp.runtime import probe_runtime_dependencies
from viberecall_mcp.tool_access import token_has_scope


settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _combined_lifespan(*apps):
    async with AsyncExitStack() as stack:
        for app in apps:
            await stack.enter_async_context(app.router.lifespan_context(app))
        yield


def create_app() -> FastAPI:
    mcp_http_app = build_fastmcp_http_app(path="/p/{project_id}/mcp")
    mcp_v2_http_app = build_fastmcp_http_app(
        path="/p/{project_id}/mcp/v2",
        stateless_http=True,
    )
    application = FastAPI(
        title="VibeRecall MCP API",
        version="0.1.0",
        lifespan=lambda _app: _combined_lifespan(mcp_http_app, mcp_v2_http_app),
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

    @application.post("/p/{project_id}/index-bundles")
    async def upload_runtime_index_bundle(
        project_id: str,
        request: Request,
        file: UploadFile = File(...),
        authorization: str | None = Header(default=None),
        session: AsyncSession = Depends(get_db_session),
    ) -> dict:
        token = await authenticate_bearer_token(
            session,
            authorization=authorization,
            project_id=project_id,
        )
        if not token_has_scope(token.scopes, "index:run"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing required scope: index:run",
            )

        filename = (file.filename or "").strip()
        if not filename.lower().endswith(".zip"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Index bundle must be a .zip archive",
            )
        payload = await file.read()
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Index bundle is empty",
            )
        if len(payload) > settings.index_bundle_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Index bundle exceeds size limit",
            )
        try:
            validate_workspace_bundle_archive(payload)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        bundle_id = new_id("bundle")
        object_key = bundle_storage_key(project_id, bundle_id)
        await put_bytes(object_key=object_key, content=payload, content_type="application/zip")
        bundle = await create_index_bundle(
            session,
            bundle_id=bundle_id,
            project_id=project_id,
            object_key=object_key,
            filename=filename,
            byte_size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            uploaded_by_user_id=token.token_id,
        )
        await insert_audit_log(
            session,
            request_id=getattr(request.state, "request_id", None),
            action="runtime/index-bundle.create",
            status="ok",
            project_id=project_id,
            token_id=token.token_id,
        )
        await session.commit()
        return {
            "bundle": {
                "bundle_id": bundle["bundle_id"],
                "bundle_ref": f"bundle://{bundle['bundle_id']}",
                "filename": bundle["filename"],
                "byte_size": int(bundle["byte_size"]),
                "sha256": bundle["sha256"],
                "created_at": bundle["created_at"],
                "expires_at": bundle.get("expires_at"),
            }
        }

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

    application.router.routes.extend(mcp_v2_http_app.routes)
    application.mount("/", mcp_http_app)
    return application


app = create_app()
