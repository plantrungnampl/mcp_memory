from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone

import structlog
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EpisodeType, EpisodicNode

from viberecall_mcp.config import get_settings
from viberecall_mcp.graphiti_upstream_bridge import UpstreamGraphitiBridge
from viberecall_mcp.memory_core.falkordb_adapter import FalkorDBMemoryCore
from viberecall_mcp.memory_core.falkordb_admin import FalkorDBGraphManager
from viberecall_mcp.memory_core.interface import DeleteEpisodeResult
from viberecall_mcp.metrics import graph_db_latency_ms


logger = structlog.get_logger(__name__)
settings = get_settings()


def _to_datetime(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class GraphitiMemoryCore:
    """
    Graphiti adapter boundary.

    Canonical fact/entity storage remains in FalkorDBMemoryCore so existing tool contracts
    and temporal semantics stay stable. Graphiti sync is optional and best-effort.
    """

    def __init__(self, admin: FalkorDBGraphManager) -> None:
        self._admin = admin
        self._falkordb_core = FalkorDBMemoryCore(admin)
        self._clients: dict[str, Graphiti] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._ingest_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._disabled_projects_logged: set[str] = set()
        self._upstream_bridge = UpstreamGraphitiBridge(admin)

    @staticmethod
    def _graphiti_enabled() -> bool:
        return bool((settings.graphiti_api_key or "").strip())

    async def _get_graphiti_client(self, project_id: str) -> Graphiti | None:
        if not self._graphiti_enabled():
            return None

        graph_name = await self._admin.ensure_project_graph(project_id)
        if graph_name in self._clients:
            return self._clients[graph_name]

        async with self._locks[graph_name]:
            if graph_name in self._clients:
                return self._clients[graph_name]

            llm_config = LLMConfig(
                api_key=settings.graphiti_api_key,
                model=settings.graphiti_llm_model,
                small_model=settings.graphiti_llm_model,
            )
            llm_client = OpenAIClient(config=llm_config)
            embedder = OpenAIEmbedder(
                config=OpenAIEmbedderConfig(
                    api_key=settings.graphiti_api_key,
                    embedding_model=settings.graphiti_embedder_model,
                )
            )
            graph_driver = FalkorDriver(
                host=settings.falkordb_host,
                port=settings.falkordb_port,
                username=settings.falkordb_username or None,
                password=settings.falkordb_password or None,
                falkor_db=self._admin.client,
                database=graph_name,
            )
            client = Graphiti(
                llm_client=llm_client,
                embedder=embedder,
                graph_driver=graph_driver,
                store_raw_episode_content=False,
            )
            await client.build_indices_and_constraints()
            self._clients[graph_name] = client
            return client

    async def ingest_episode(self, project_id: str, episode: dict) -> dict:
        result = await self._falkordb_core.ingest_episode(project_id, episode)

        if not self._graphiti_enabled():
            if project_id not in self._disabled_projects_logged:
                logger.info(
                    "graphiti_episode_sync_disabled",
                    project_id=project_id,
                    reason="GRAPHITI_API_KEY is empty",
                )
                self._disabled_projects_logged.add(project_id)
            return result

        async with self._ingest_locks[project_id]:
            start = datetime.now(timezone.utc)
            try:
                if settings.graphiti_mcp_bridge_mode == "upstream_bridge":
                    await self._upstream_bridge.add_episode_from_record(project_id, episode)
                    return result

                client = await self._get_graphiti_client(project_id)
                if client is None:
                    return result

                reference_time = _to_datetime(episode.get("reference_time") or episode.get("ingested_at"))
                metadata = episode.get("metadata_json") or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except ValueError:
                        metadata = {}
                source_description = str(metadata.get("type") or "viberecall_save")

                await asyncio.wait_for(
                    client.add_episode(
                        name=f"episode:{episode['episode_id']}",
                        episode_body=episode["content"],
                        source_description=source_description,
                        reference_time=reference_time,
                        source=EpisodeType.text,
                        group_id=project_id,
                        uuid=episode["episode_id"],
                    ),
                    timeout=settings.graphiti_add_episode_timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                # Keep canonical persistence available even if Graphiti enrichment fails.
                logger.warning(
                    "graphiti_episode_sync_failed",
                    project_id=project_id,
                    episode_id=episode.get("episode_id"),
                    error=str(exc),
                )
            finally:
                elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                graph_db_latency_ms.labels(operation="graphiti.add_episode").observe(elapsed_ms)

        return result

    async def search(
        self,
        project_id: str,
        *,
        query: str,
        filters: dict,
        sort: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        # v0.1 keeps deterministic canonical ranking in the canonical graph adapter.
        return await self._falkordb_core.search(
            project_id,
            query=query,
            filters=filters,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def get_facts(
        self,
        project_id: str,
        *,
        filters: dict,
        limit: int,
        offset: int,
    ) -> list[dict]:
        return await self._falkordb_core.get_facts(
            project_id,
            filters=filters,
            limit=limit,
            offset=offset,
        )

    async def update_fact(
        self,
        project_id: str,
        *,
        fact_id: str,
        new_fact_id: str,
        new_text: str,
        effective_time: str,
        reason: str | None,
    ) -> dict:
        return await self._falkordb_core.update_fact(
            project_id,
            fact_id=fact_id,
            new_fact_id=new_fact_id,
            new_text=new_text,
            effective_time=effective_time,
            reason=reason,
        )

    async def delete_episode(self, project_id: str, *, episode_id: str) -> DeleteEpisodeResult:
        deleted = await self._falkordb_core.delete_episode(project_id, episode_id=episode_id)
        if not deleted.found or not self._graphiti_enabled():
            return deleted

        try:
            if settings.graphiti_mcp_bridge_mode == "upstream_bridge":
                await self._upstream_bridge.delete_episode(project_id, episode_id=episode_id)
                return deleted

            client = await self._get_graphiti_client(project_id)
            if client is None:
                return deleted
            node = await EpisodicNode.get_by_uuid(client.driver, episode_id)
            await node.delete(client.driver)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "graphiti_episode_delete_sync_failed",
                project_id=project_id,
                episode_id=episode_id,
                error=str(exc),
            )
        return deleted

    async def purge_project(self, project_id: str) -> None:
        graph_name = await self._admin.ensure_project_graph(project_id)
        client = self._clients.pop(graph_name, None)
        if client is not None:
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                pass
        await self._falkordb_core.purge_project(project_id)

    async def reset(self) -> None:
        await self._falkordb_core.reset()
        await self._upstream_bridge.close()
