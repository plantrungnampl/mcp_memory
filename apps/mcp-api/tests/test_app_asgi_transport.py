from __future__ import annotations

import httpx
import pytest

from viberecall_mcp import app as app_module


@pytest.mark.asyncio
async def test_create_app_healthz_works_via_asgi_transport(monkeypatch) -> None:
    async def fake_probe_runtime_dependencies() -> dict:
        return {
            "status": "ok",
            "runtime": {"mode": "test"},
            "checks": {"database": {"status": "ok"}},
        }

    monkeypatch.setattr(
        app_module,
        "probe_runtime_dependencies",
        fake_probe_runtime_dependencies,
    )

    app = app_module.create_app()
    transport = httpx.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "viberecall-mcp",
        "runtime": {"mode": "test"},
        "checks": {"database": {"status": "ok"}},
    }
