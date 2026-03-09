from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from viberecall_mcp.memory_core.graphiti_adapter import GraphitiMemoryCore
from viberecall_mcp.memory_core import graphiti_adapter


@pytest.mark.asyncio
async def test_ingest_episode_returns_skipped_provider_trace_when_graphiti_disabled(monkeypatch) -> None:
    core = GraphitiMemoryCore(SimpleNamespace())

    async def fake_ingest_episode(project_id: str, episode: dict) -> dict:
        _ = (project_id, episode)
        return {"fact_id": "fact_ep_test", "summary": "summary"}

    core._falkordb_core = SimpleNamespace(ingest_episode=fake_ingest_episode)
    monkeypatch.setattr(graphiti_adapter.settings, "graphiti_api_key", "")

    result = await core.ingest_episode(
        "proj_test",
        {"episode_id": "ep_test", "content": "hello", "metadata_json": {}},
    )

    assert result["fact_id"] == "fact_ep_test"
    assert result["provider_trace"]["sync_status"] == "skipped"
    assert result["provider_trace"]["provider"] is None
    assert result["provider_trace"]["api_key_fingerprint"] is None


@pytest.mark.asyncio
async def test_ingest_episode_returns_openai_provider_trace_for_legacy_graphiti(monkeypatch) -> None:
    core = GraphitiMemoryCore(SimpleNamespace())

    async def fake_ingest_episode(project_id: str, episode: dict) -> dict:
        _ = (project_id, episode)
        return {"fact_id": "fact_ep_test", "summary": "summary"}

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def add_episode(self, **kwargs) -> None:
            self.calls.append(kwargs)

    fake_client = FakeClient()

    async def fake_get_graphiti_client(project_id: str):
        _ = project_id
        return fake_client

    core._falkordb_core = SimpleNamespace(ingest_episode=fake_ingest_episode)
    monkeypatch.setattr(core, "_get_graphiti_client", fake_get_graphiti_client)
    monkeypatch.setattr(graphiti_adapter.settings, "graphiti_api_key", "sk-test-openai-key")
    monkeypatch.setattr(graphiti_adapter.settings, "graphiti_mcp_bridge_mode", "legacy")
    monkeypatch.setattr(graphiti_adapter.settings, "graphiti_llm_model", "gpt-4.1-mini")
    monkeypatch.setattr(graphiti_adapter.settings, "graphiti_embedder_model", "text-embedding-3-small")

    result = await core.ingest_episode(
        "proj_test",
        {
            "episode_id": "ep_test",
            "content": "hello",
            "reference_time": "2026-03-08T16:05:00Z",
            "metadata_json": {"type": "note"},
        },
    )

    assert fake_client.calls
    assert "uuid" not in fake_client.calls[0]
    assert result["provider_trace"]["sync_status"] == "succeeded"
    assert result["provider_trace"]["provider"] == "openai"
    assert result["provider_trace"]["llm_model"] == "gpt-4.1-mini"
    assert result["provider_trace"]["embedder_model"] == "text-embedding-3-small"
    assert result["provider_trace"]["api_key_fingerprint"]


@pytest.mark.asyncio
async def test_ingest_episode_accepts_datetime_reference_time(monkeypatch) -> None:
    core = GraphitiMemoryCore(SimpleNamespace())

    async def fake_ingest_episode(project_id: str, episode: dict) -> dict:
        _ = (project_id, episode)
        return {"fact_id": "fact_ep_test", "summary": "summary"}

    class FakeClient:
        async def add_episode(self, **kwargs) -> None:
            assert isinstance(kwargs["reference_time"], datetime)
            assert kwargs["reference_time"].tzinfo is not None

    async def fake_get_graphiti_client(project_id: str):
        _ = project_id
        return FakeClient()

    core._falkordb_core = SimpleNamespace(ingest_episode=fake_ingest_episode)
    monkeypatch.setattr(core, "_get_graphiti_client", fake_get_graphiti_client)
    monkeypatch.setattr(graphiti_adapter.settings, "graphiti_api_key", "sk-test-openai-key")
    monkeypatch.setattr(graphiti_adapter.settings, "graphiti_mcp_bridge_mode", "legacy")

    result = await core.ingest_episode(
        "proj_test",
        {
            "episode_id": "ep_test",
            "content": "hello",
            "reference_time": datetime(2026, 3, 8, 16, 30, tzinfo=timezone.utc),
            "metadata_json": {"type": "note"},
        },
    )

    assert result["provider_trace"]["sync_status"] == "succeeded"
