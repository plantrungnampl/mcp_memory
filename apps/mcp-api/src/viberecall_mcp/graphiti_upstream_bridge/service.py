from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import structlog
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EpisodeType, EpisodicNode

from viberecall_mcp.config import get_settings
from viberecall_mcp.memory_core.falkordb_admin import FalkorDBGraphManager
from viberecall_mcp.metrics import graph_db_latency_ms


logger = structlog.get_logger(__name__)
settings = get_settings()


def _parse_iso_or_none(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class UpstreamGraphitiBridge:
    """
    Bridge layer that ports selected behavior from upstream Graphiti MCP server
    while preserving VibeRecall public tool contracts.
    """

    def __init__(self, admin: FalkorDBGraphManager) -> None:
        self._admin = admin
        self._clients: dict[str, Graphiti] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @staticmethod
    def can_use_graphiti() -> bool:
        return bool((settings.graphiti_api_key or "").strip())

    async def _get_client(self, project_id: str) -> Graphiti:
        graph_name = await self._admin.ensure_project_graph(project_id)
        cached = self._clients.get(graph_name)
        if cached is not None:
            return cached

        async with self._locks[graph_name]:
            cached = self._clients.get(graph_name)
            if cached is not None:
                return cached

            llm = OpenAIClient(
                config=LLMConfig(
                    api_key=settings.graphiti_api_key,
                    model=settings.graphiti_llm_model,
                    small_model=settings.graphiti_llm_model,
                )
            )
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
                llm_client=llm,
                embedder=embedder,
                graph_driver=graph_driver,
                store_raw_episode_content=False,
            )
            await client.build_indices_and_constraints()
            self._clients[graph_name] = client
            return client

    async def add_episode_from_record(self, project_id: str, episode: dict) -> None:
        if not self.can_use_graphiti():
            return

        started = time.perf_counter()
        try:
            client = await self._get_client(project_id)
            source_description = "viberecall_save"
            metadata = episode.get("metadata_json")
            if isinstance(metadata, str):
                try:
                    import json

                    metadata = json.loads(metadata)
                except ValueError:
                    metadata = {}
            if isinstance(metadata, dict):
                source_description = str(metadata.get("type") or source_description)

            reference_time = _parse_iso_or_none(episode.get("reference_time")) or _parse_iso_or_none(
                episode.get("ingested_at")
            )
            await client.add_episode(
                name=f"episode:{episode['episode_id']}",
                episode_body=str(episode.get("content") or ""),
                source_description=source_description,
                reference_time=reference_time or datetime.now(timezone.utc),
                source=EpisodeType.text,
                group_id=project_id,
                uuid=str(episode["episode_id"]),
            )
        finally:
            graph_db_latency_ms.labels(operation="graphiti.bridge.add_episode").observe(
                (time.perf_counter() - started) * 1000
            )

    async def search_facts(
        self,
        project_id: str,
        *,
        query: str,
        limit: int,
        offset: int,
        sort: str,
        filters: dict,
    ) -> list[dict]:
        if not self.can_use_graphiti():
            return []

        started = time.perf_counter()
        try:
            client = await self._get_client(project_id)
            raw_edges = await client.search(
                group_ids=[project_id],
                query=query,
                num_results=max(limit + offset, 20),
            )
            formatted = [self._edge_to_search_item(edge) for edge in raw_edges]
            filtered = [item for item in formatted if self._matches_filters(item, filters)]

            if sort == "RECENCY":
                filtered.sort(
                    key=lambda item: (item["provenance"].get("ingested_at") or "", item["fact"]["id"]),
                    reverse=True,
                )
            elif sort == "TIME":
                filtered.sort(
                    key=lambda item: (item["fact"].get("valid_at") or "", item["fact"]["id"]),
                    reverse=True,
                )
            else:
                filtered.sort(
                    key=lambda item: (item["score"], item["provenance"].get("ingested_at") or "", item["fact"]["id"]),
                    reverse=True,
                )

            return filtered[offset : offset + limit]
        finally:
            graph_db_latency_ms.labels(operation="graphiti.bridge.search").observe(
                (time.perf_counter() - started) * 1000
            )

    async def list_facts(
        self,
        project_id: str,
        *,
        filters: dict,
        limit: int,
        offset: int,
    ) -> list[dict]:
        query = str(filters.get("tag") or filters.get("entity_type") or "memory")
        rows = await self.search_facts(
            project_id,
            query=query,
            limit=limit,
            offset=offset,
            sort="TIME",
            filters=filters,
        )
        return [
            {
                "id": row["fact"]["id"],
                "text": row["fact"]["text"],
                "valid_at": row["fact"]["valid_at"],
                "invalid_at": row["fact"]["invalid_at"],
                "entities": row["entities"],
                "provenance": row["provenance"],
                "ingested_at": row["provenance"].get("ingested_at"),
            }
            for row in rows
        ]

    async def list_timeline(
        self,
        project_id: str,
        *,
        from_time: str | None,
        to_time: str | None,
        limit: int,
        offset: int,
    ) -> list[dict]:
        if not self.can_use_graphiti():
            return []

        started = time.perf_counter()
        try:
            client = await self._get_client(project_id)
            rows = await EpisodicNode.get_by_group_ids(client.driver, [project_id], limit=max(limit + offset, 20))
            start_dt = _parse_iso_or_none(from_time)
            end_dt = _parse_iso_or_none(to_time)

            episodes: list[dict] = []
            for episode in rows:
                ingested = episode.created_at
                ingested_iso = _iso(ingested)
                ingested_dt = _parse_iso_or_none(ingested_iso)
                if start_dt is not None and ingested_dt is not None and ingested_dt < start_dt:
                    continue
                if end_dt is not None and ingested_dt is not None and ingested_dt > end_dt:
                    continue
                content = str(getattr(episode, "content", "") or "")
                source = getattr(episode, "source", None)
                episodes.append(
                    {
                        "episode_id": str(episode.uuid),
                        "reference_time": ingested_iso,
                        "ingested_at": ingested_iso,
                        "summary": content[:160] or getattr(episode, "name", ""),
                        "metadata": {
                            "source": source.value if hasattr(source, "value") else str(source or "text"),
                            "source_description": getattr(episode, "source_description", ""),
                        },
                    }
                )

            episodes.sort(
                key=lambda item: (item.get("reference_time") or item.get("ingested_at") or "", item["episode_id"]),
                reverse=True,
            )
            return episodes[offset : offset + limit]
        finally:
            graph_db_latency_ms.labels(operation="graphiti.bridge.timeline").observe(
                (time.perf_counter() - started) * 1000
            )

    async def delete_episode(self, project_id: str, *, episode_id: str) -> bool:
        if not self.can_use_graphiti():
            return False
        started = time.perf_counter()
        try:
            client = await self._get_client(project_id)
            try:
                node = await EpisodicNode.get_by_uuid(client.driver, episode_id)
            except Exception:  # noqa: BLE001
                return False
            await node.delete(client.driver)
            return True
        finally:
            graph_db_latency_ms.labels(operation="graphiti.bridge.delete_episode").observe(
                (time.perf_counter() - started) * 1000
            )

    async def status(self, project_id: str) -> tuple[str, str]:
        if not self.can_use_graphiti():
            return "degraded", "GRAPHITI_API_KEY is empty"
        try:
            client = await self._get_client(project_id)
            await client.driver.health_check()
            return "ok", "Graphiti bridge ready"
        except Exception as exc:  # noqa: BLE001
            return "degraded", str(exc)

    @staticmethod
    def _edge_to_search_item(edge: EntityEdge) -> dict:
        payload = edge.model_dump(
            mode="json",
            exclude={"fact_embedding"},
        )
        attributes = dict(payload.get("attributes") or {})
        attributes.pop("fact_embedding", None)
        score = 0.62
        if payload.get("invalid_at") is None:
            score += 0.15

        entities = []
        source_uuid = payload.get("source_node_uuid")
        target_uuid = payload.get("target_node_uuid")
        if source_uuid:
            entities.append({"id": source_uuid, "type": "Entity", "name": source_uuid})
        if target_uuid and target_uuid != source_uuid:
            entities.append({"id": target_uuid, "type": "Entity", "name": target_uuid})

        return {
            "kind": "fact",
            "fact": {
                "id": str(payload.get("uuid")),
                "text": str(payload.get("fact") or payload.get("name") or ""),
                "valid_at": payload.get("valid_at") or payload.get("created_at"),
                "invalid_at": payload.get("invalid_at"),
            },
            "entities": entities,
            "provenance": {
                "episode_ids": [str(value) for value in (payload.get("episodes") or []) if value],
                "reference_time": payload.get("valid_at") or payload.get("created_at"),
                "ingested_at": payload.get("created_at"),
                "attributes": attributes,
            },
            "score": min(score, 1.0),
        }

    @staticmethod
    def _matches_filters(item: dict, filters: dict) -> bool:
        fact = item["fact"]
        entities = item["entities"]
        valid_at = filters.get("valid_at")
        if valid_at and fact.get("invalid_at") and fact["invalid_at"] <= valid_at:
            return False

        entity_type = filters.get("entity_type")
        if entity_type and not any(entity["type"] == entity_type for entity in entities):
            return False

        if filters.get("entity_types"):
            allowed = set(filters["entity_types"])
            if not any(entity["type"] in allowed for entity in entities):
                return False
        return True

    async def close(self) -> None:
        for client in self._clients.values():
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                logger.warning("graphiti_bridge_close_failed")
        self._clients.clear()
