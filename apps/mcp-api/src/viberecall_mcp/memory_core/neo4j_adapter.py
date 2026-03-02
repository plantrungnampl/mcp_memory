from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from viberecall_mcp.memory_core.interface import entity_identity
from viberecall_mcp.memory_core.neo4j_admin import Neo4jDatabaseManager
from viberecall_mcp.metrics import graph_db_latency_ms


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class Neo4jMemoryCore:
    def __init__(self, admin: Neo4jDatabaseManager) -> None:
        self._admin = admin

    async def ingest_episode(self, project_id: str, episode: dict) -> dict:
        started = time.perf_counter()
        db_name = await self._admin.ensure_project_database(project_id)
        metadata = episode["metadata_json"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        summary = (episode.get("summary") or episode["content"][:160]).strip()
        fact_id = f"fact_{episode['episode_id']}"
        entities = self._build_entities(metadata)

        query = """
        MERGE (episode:Episode {episode_id: $episode_id})
        SET episode.reference_time = $reference_time,
            episode.ingested_at = $ingested_at,
            episode.summary = $summary,
            episode.content_ref = $content_ref,
            episode.metadata_json = $metadata_json
        MERGE (fact:Fact {fact_id: $fact_id})
        SET fact.text = $text,
            fact.valid_at = $valid_at,
            fact.invalid_at = null,
            fact.ingested_at = $ingested_at,
            fact.confidence = 1.0
        MERGE (episode)-[:SUPPORTS]->(fact)
        WITH episode, fact
        UNWIND $entities AS entity
        MERGE (node:Entity {entity_id: entity.entity_id})
        SET node.type = entity.type,
            node.name = entity.name,
            node.aliases = entity.aliases
        MERGE (episode)-[:MENTIONS]->(node)
        MERGE (fact)-[:ABOUT]->(node)
        """
        async with self._admin.driver.session(database=db_name) as session:
            await session.run(
                query,
                episode_id=episode["episode_id"],
                reference_time=_iso(episode.get("reference_time")),
                ingested_at=_iso(episode.get("ingested_at")),
                summary=summary,
                content_ref=episode.get("content_ref") or episode["episode_id"],
                metadata_json=json.dumps(metadata, default=str),
                fact_id=fact_id,
                text=episode["content"],
                valid_at=_iso(episode.get("reference_time")) or _iso(episode.get("ingested_at")),
                entities=entities,
            )
        graph_db_latency_ms.labels(operation="neo4j.ingest_episode").observe((time.perf_counter() - started) * 1000)
        return {"fact_id": fact_id, "summary": summary}

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
        started = time.perf_counter()
        db_name = await self._admin.ensure_project_database(project_id)
        results: dict[str, dict] = {}

        async with self._admin.driver.session(database=db_name) as session:
            fact_records = await session.run(
                """
                CALL db.index.fulltext.queryNodes('fact_text_index', $query) YIELD node, score
                OPTIONAL MATCH (node)-[:ABOUT]->(entity:Entity)
                RETURN node, score, collect(distinct entity) AS entities
                ORDER BY score DESC
                LIMIT $limit
                """,
                query=query,
                limit=max(limit * 3, 20),
            )
            async for record in fact_records:
                item = self._record_to_search_result(record, base_score=float(record["score"] or 0))
                if self._matches_filters(item, filters):
                    results[item["fact"]["id"]] = item

            entity_records = await session.run(
                """
                MATCH (entity:Entity)
                WHERE toLower(entity.name) CONTAINS toLower($query)
                   OR any(alias IN coalesce(entity.aliases, []) WHERE toLower(alias) CONTAINS toLower($query))
                MATCH (fact:Fact)-[:ABOUT]->(entity)
                OPTIONAL MATCH (fact)-[:ABOUT]->(related:Entity)
                RETURN fact AS node, collect(distinct related) AS entities
                LIMIT $limit
                """,
                query=query,
                limit=max(limit * 3, 20),
            )
            async for record in entity_records:
                item = self._record_to_search_result(record, base_score=0.35, graph_boost=0.15)
                if self._matches_filters(item, filters):
                    existing = results.get(item["fact"]["id"])
                    if existing is None or item["score"] > existing["score"]:
                        results[item["fact"]["id"]] = item

        ordered = list(results.values())
        if sort == "RECENCY":
            ordered.sort(
                key=lambda item: (item["provenance"]["ingested_at"] or "", item["fact"]["id"]),
                reverse=True,
            )
        elif sort == "TIME":
            ordered.sort(
                key=lambda item: (
                    item["fact"]["valid_at"] or item["provenance"]["reference_time"] or "",
                    item["fact"]["id"],
                ),
                reverse=True,
            )
        else:
            ordered.sort(
                key=lambda item: (item["score"], item["provenance"]["ingested_at"] or "", item["fact"]["id"]),
                reverse=True,
            )
        graph_db_latency_ms.labels(operation="neo4j.search").observe((time.perf_counter() - started) * 1000)
        return ordered[offset : offset + limit]

    async def get_facts(
        self,
        project_id: str,
        *,
        filters: dict,
        limit: int,
        offset: int,
    ) -> list[dict]:
        started = time.perf_counter()
        db_name = await self._admin.ensure_project_database(project_id)
        async with self._admin.driver.session(database=db_name) as session:
            records = await session.run(
                """
                MATCH (fact:Fact)
                OPTIONAL MATCH (fact)-[:ABOUT]->(entity:Entity)
                OPTIONAL MATCH (episode:Episode)-[:SUPPORTS]->(fact)
                RETURN fact, collect(distinct entity) AS entities, collect(distinct episode.episode_id) AS episode_ids
                ORDER BY fact.valid_at DESC, fact.ingested_at DESC, fact.fact_id DESC
                SKIP $offset
                LIMIT $limit
                """,
                offset=offset,
                limit=limit,
            )
            items = []
            async for record in records:
                item = self._fact_record_to_item(record)
                if self._matches_fact_filters(item, filters):
                    items.append(item)
            graph_db_latency_ms.labels(operation="neo4j.get_facts").observe((time.perf_counter() - started) * 1000)
            return items

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
        started = time.perf_counter()
        db_name = await self._admin.ensure_project_database(project_id)
        async with self._admin.driver.session(database=db_name) as session:
            existing = await session.run(
                """
                MATCH (fact:Fact {fact_id: $fact_id})
                RETURN fact.invalid_at AS invalid_at
                """,
                fact_id=fact_id,
            )
            row = await existing.single()
            if row is None:
                raise KeyError(fact_id)
            if row["invalid_at"] is not None:
                raise ValueError(f"Fact {fact_id} is already invalidated")

            await session.run(
                """
                MATCH (old:Fact {fact_id: $fact_id})
                OPTIONAL MATCH (old)-[:ABOUT]->(entity:Entity)
                OPTIONAL MATCH (episode:Episode)-[:SUPPORTS]->(old)
                WITH old, collect(distinct entity) AS entities, collect(distinct episode) AS episodes
                SET old.invalid_at = $effective_time
                CREATE (new:Fact {
                    fact_id: $new_fact_id,
                    text: $new_text,
                    valid_at: $effective_time,
                    invalid_at: null,
                    ingested_at: $ingested_at,
                    confidence: 1.0,
                    reason: $reason
                })
                FOREACH (entity IN entities | MERGE (new)-[:ABOUT]->(entity))
                FOREACH (episode IN episodes | MERGE (episode)-[:SUPPORTS]->(new))
                """,
                fact_id=fact_id,
                new_fact_id=new_fact_id,
                new_text=new_text,
                effective_time=effective_time,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                reason=reason,
            )
        graph_db_latency_ms.labels(operation="neo4j.update_fact").observe((time.perf_counter() - started) * 1000)

        return {
            "old_fact": {"id": fact_id, "invalid_at": effective_time},
            "new_fact": {"id": new_fact_id, "valid_at": effective_time},
        }

    async def purge_project(self, project_id: str) -> None:
        await self._admin.drop_project_database(project_id)

    async def reset(self) -> None:
        return None

    @staticmethod
    def _build_entities(metadata: dict) -> list[dict]:
        items: list[dict] = []

        def append_entity(entity_type: str, name: str) -> None:
            items.append(
                {
                    "entity_id": entity_identity(entity_type, name),
                    "type": entity_type,
                    "name": name,
                    "aliases": [],
                }
            )

        for file_path in metadata.get("files", []):
            append_entity("File", file_path)
        for tag in metadata.get("tags", []):
            append_entity("Tag", tag)
        if metadata.get("repo"):
            append_entity("Repository", metadata["repo"])
        if metadata.get("branch"):
            append_entity("Branch", metadata["branch"])
        if metadata.get("type"):
            append_entity("EpisodeType", metadata["type"])
        return items

    @staticmethod
    def _record_to_search_result(record, *, base_score: float, graph_boost: float = 0.0) -> dict:
        node = record["node"]
        entities = [Neo4jMemoryCore._entity_to_dict(entity) for entity in record["entities"] if entity is not None]
        bm25 = max(min(base_score / 10 if base_score > 1 else base_score, 1.0), 0.0)
        time_boost = 0.15 if node.get("invalid_at") is None else 0.05
        score = min((0.70 * bm25) + graph_boost + time_boost, 1.0)
        return {
            "kind": "fact",
            "fact": {
                "id": node["fact_id"],
                "text": node["text"],
                "valid_at": node.get("valid_at"),
                "invalid_at": node.get("invalid_at"),
            },
            "entities": entities,
            "provenance": {
                "episode_ids": [],
                "reference_time": node.get("valid_at"),
                "ingested_at": node.get("ingested_at"),
            },
            "score": score,
        }

    @staticmethod
    def _fact_record_to_item(record) -> dict:
        fact = record["fact"]
        entities = [Neo4jMemoryCore._entity_to_dict(entity) for entity in record["entities"] if entity is not None]
        return {
            "id": fact["fact_id"],
            "text": fact["text"],
            "valid_at": fact.get("valid_at"),
            "invalid_at": fact.get("invalid_at"),
            "entities": entities,
            "provenance": {"episode_ids": [value for value in record["episode_ids"] if value]},
            "ingested_at": fact.get("ingested_at"),
        }

    @staticmethod
    def _entity_to_dict(entity) -> dict:
        return {
            "id": entity["entity_id"],
            "type": entity["type"],
            "name": entity["name"],
        }

    @staticmethod
    def _matches_filters(item: dict, filters: dict) -> bool:
        fact = item["fact"]
        entities = item["entities"]
        if filters.get("valid_at") and fact.get("invalid_at") and fact["invalid_at"] <= filters["valid_at"]:
            return False
        if filters.get("entity_types"):
            entity_types = set(filters["entity_types"])
            if not any(entity["type"] in entity_types for entity in entities):
                return False
        if filters.get("tags"):
            tags = set(filters["tags"])
            if not any(entity["type"] == "Tag" and entity["name"] in tags for entity in entities):
                return False
        if filters.get("files"):
            files = set(filters["files"])
            if not any(entity["type"] == "File" and entity["name"] in files for entity in entities):
                return False
        return True

    @staticmethod
    def _matches_fact_filters(item: dict, filters: dict) -> bool:
        if filters.get("entity_type"):
            if not any(entity["type"] == filters["entity_type"] for entity in item["entities"]):
                return False
        if filters.get("tag"):
            if not any(entity["type"] == "Tag" and entity["name"] == filters["tag"] for entity in item["entities"]):
                return False
        if filters.get("valid_at") and item["invalid_at"] is not None and item["invalid_at"] <= filters["valid_at"]:
            return False
        return True
