from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from viberecall_mcp.memory_core.falkordb_admin import FalkorDBGraphManager
from viberecall_mcp.memory_core.interface import DeleteEpisodeResult, entity_identity
from viberecall_mcp.metrics import graph_db_latency_ms


_SEPARATOR_MAP = str.maketrans(
    {
        ",": " ",
        ".": " ",
        "<": " ",
        ">": " ",
        "{": " ",
        "}": " ",
        "[": " ",
        "]": " ",
        '"': " ",
        "'": " ",
        ":": " ",
        ";": " ",
        "!": " ",
        "@": " ",
        "#": " ",
        "$": " ",
        "%": " ",
        "^": " ",
        "&": " ",
        "*": " ",
        "(": " ",
        ")": " ",
        "-": " ",
        "+": " ",
        "=": " ",
        "~": " ",
        "?": " ",
        "|": " ",
        "/": " ",
        "\\": " ",
    }
)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _node_properties(node: Any) -> dict[str, Any]:
    if node is None:
        return {}
    if isinstance(node, dict):
        return node
    if hasattr(node, "properties"):
        props = getattr(node, "properties")
        if isinstance(props, dict):
            return props
    try:
        return dict(node)
    except Exception:  # noqa: BLE001
        return {}


class FalkorDBMemoryCore:
    def __init__(self, admin: FalkorDBGraphManager) -> None:
        self._admin = admin

    async def _query_records(
        self,
        graph_name: str,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        graph = self._admin.client.select_graph(graph_name)
        result = await graph.query(cypher, params or {})
        header = [column[1] for column in result.header]
        rows: list[dict[str, Any]] = []
        for raw in result.result_set:
            row: dict[str, Any] = {}
            for idx, field_name in enumerate(header):
                row[field_name] = raw[idx] if idx < len(raw) else None
            rows.append(row)
        return rows

    async def ingest_episode(self, project_id: str, episode: dict) -> dict:
        started = time.perf_counter()
        graph_name = await self._admin.ensure_project_graph(project_id)
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
            fact.confidence = 1.0,
            fact.episode_ids = $episode_ids
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

        await self._query_records(
            graph_name,
            query,
            {
                "episode_id": episode["episode_id"],
                "reference_time": _iso(episode.get("reference_time")),
                "ingested_at": _iso(episode.get("ingested_at")),
                "summary": summary,
                "content_ref": episode.get("content_ref") or episode["episode_id"],
                "metadata_json": json.dumps(metadata, default=str),
                "fact_id": fact_id,
                "text": episode["content"],
                "valid_at": _iso(episode.get("reference_time")) or _iso(episode.get("ingested_at")),
                "episode_ids": [episode["episode_id"]],
                "entities": entities,
            },
        )
        graph_db_latency_ms.labels(operation="falkordb.ingest_episode").observe((time.perf_counter() - started) * 1000)
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
        graph_name = await self._admin.ensure_project_graph(project_id)
        results: dict[str, dict] = {}
        sanitized_query = self._sanitize_query(query)

        fact_records = await self._query_records(
            graph_name,
            """
            CALL db.idx.fulltext.queryNodes('Fact', $query) YIELD node, score
            OPTIONAL MATCH (node)-[:ABOUT]->(entity:Entity)
            RETURN node, score, collect(distinct entity) AS entities
            ORDER BY score DESC
            LIMIT $limit
            """,
            {"query": sanitized_query, "limit": max(limit * 3, 20)},
        )
        for record in fact_records:
            item = self._record_to_search_result(record, base_score=float(record.get("score") or 0))
            if self._matches_filters(item, filters):
                results[item["fact"]["id"]] = item

        entity_records = await self._query_records(
            graph_name,
            """
            MATCH (entity:Entity)
            WHERE toLower(entity.name) CONTAINS toLower($query)
               OR any(alias IN coalesce(entity.aliases, []) WHERE toLower(alias) CONTAINS toLower($query))
            MATCH (fact:Fact)-[:ABOUT]->(entity)
            OPTIONAL MATCH (fact)-[:ABOUT]->(related:Entity)
            RETURN fact AS node, collect(distinct related) AS entities
            LIMIT $limit
            """,
            {"query": query, "limit": max(limit * 3, 20)},
        )
        for record in entity_records:
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
        graph_db_latency_ms.labels(operation="falkordb.search").observe((time.perf_counter() - started) * 1000)
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
        graph_name = await self._admin.ensure_project_graph(project_id)
        records = await self._query_records(
            graph_name,
            """
            MATCH (fact:Fact)
            OPTIONAL MATCH (fact)-[:ABOUT]->(entity:Entity)
            OPTIONAL MATCH (episode:Episode)-[:SUPPORTS]->(fact)
            RETURN fact,
                   collect(distinct entity) AS entities,
                   coalesce(fact.episode_ids, []) AS stored_episode_ids,
                   collect(distinct episode.episode_id) AS support_episode_ids
            ORDER BY fact.valid_at DESC, fact.ingested_at DESC, fact.fact_id DESC
            SKIP $offset
            LIMIT $limit
            """,
            {"offset": offset, "limit": limit},
        )
        items = []
        for record in records:
            item = self._fact_record_to_item(record)
            if self._matches_fact_filters(item, filters):
                items.append(item)

        graph_db_latency_ms.labels(operation="falkordb.get_facts").observe((time.perf_counter() - started) * 1000)
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
        graph_name = await self._admin.ensure_project_graph(project_id)
        rows = await self._query_records(
            graph_name,
            """
            MATCH (fact:Fact {fact_id: $fact_id})
            OPTIONAL MATCH (fact)-[:ABOUT]->(entity:Entity)
            WITH fact, collect(distinct entity.entity_id) AS entity_ids
            OPTIONAL MATCH (episode:Episode)-[:SUPPORTS]->(fact)
            RETURN fact.invalid_at AS invalid_at,
                   entity_ids,
                   coalesce(fact.episode_ids, []) AS stored_episode_ids,
                   collect(distinct episode.episode_id) AS support_episode_ids
            """,
            {"fact_id": fact_id},
        )
        if not rows:
            raise KeyError(fact_id)

        row = rows[0]
        if row.get("invalid_at") is not None:
            raise ValueError(f"Fact {fact_id} is already invalidated")

        await self._query_records(
            graph_name,
            """
            MATCH (old:Fact {fact_id: $fact_id})
            SET old.invalid_at = $effective_time
            """,
            {"fact_id": fact_id, "effective_time": effective_time},
        )
        await self._query_records(
            graph_name,
            """
            CREATE (new:Fact {
                fact_id: $new_fact_id,
                text: $new_text,
                valid_at: $effective_time,
                invalid_at: null,
                ingested_at: $ingested_at,
                confidence: 1.0,
                reason: $reason,
                episode_ids: $episode_ids
            })
            """,
            {
                "new_fact_id": new_fact_id,
                "new_text": new_text,
                "effective_time": effective_time,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "episode_ids": self._merge_episode_ids(
                    row.get("stored_episode_ids"),
                    row.get("support_episode_ids"),
                ),
            },
        )

        entity_ids = [str(value) for value in (row.get("entity_ids") or []) if value]
        if entity_ids:
            await self._query_records(
                graph_name,
                """
                MATCH (new:Fact {fact_id: $new_fact_id})
                UNWIND $entity_ids AS entity_id
                MATCH (entity:Entity {entity_id: entity_id})
                MERGE (new)-[:ABOUT]->(entity)
                """,
                {"new_fact_id": new_fact_id, "entity_ids": entity_ids},
            )

        episode_ids = self._merge_episode_ids(
            row.get("stored_episode_ids"),
            row.get("support_episode_ids"),
        )
        if episode_ids:
            await self._query_records(
                graph_name,
                """
                MATCH (new:Fact {fact_id: $new_fact_id})
                UNWIND $episode_ids AS episode_id
                MATCH (episode:Episode {episode_id: episode_id})
                MERGE (episode)-[:SUPPORTS]->(new)
                """,
                {"new_fact_id": new_fact_id, "episode_ids": episode_ids},
            )

        graph_db_latency_ms.labels(operation="falkordb.update_fact").observe((time.perf_counter() - started) * 1000)
        return {
            "old_fact": {"id": fact_id, "invalid_at": effective_time},
            "new_fact": {"id": new_fact_id, "valid_at": effective_time},
        }

    async def delete_episode(self, project_id: str, *, episode_id: str) -> DeleteEpisodeResult:
        started = time.perf_counter()
        graph_name = await self._admin.ensure_project_graph(project_id)
        exists = await self._query_records(
            graph_name,
            """
            MATCH (episode:Episode {episode_id: $episode_id})
            RETURN count(episode) AS count
            """,
            {"episode_id": episode_id},
        )
        episode_exists = bool(exists and int(exists[0].get("count") or 0) > 0)

        property_rows = await self._query_records(
            graph_name,
            """
            MATCH (fact:Fact)
            WHERE $episode_id IN coalesce(fact.episode_ids, [])
            OPTIONAL MATCH (episode:Episode)-[:SUPPORTS]->(fact)
            RETURN fact.fact_id AS fact_id,
                   coalesce(fact.episode_ids, []) AS stored_episode_ids,
                   collect(distinct episode.episode_id) AS support_episode_ids
            """,
            {"episode_id": episode_id},
        )
        support_rows = await self._query_records(
            graph_name,
            """
            MATCH (:Episode {episode_id: $episode_id})-[:SUPPORTS]->(fact:Fact)
            OPTIONAL MATCH (episode:Episode)-[:SUPPORTS]->(fact)
            RETURN fact.fact_id AS fact_id,
                   coalesce(fact.episode_ids, []) AS stored_episode_ids,
                   collect(distinct episode.episode_id) AS support_episode_ids
            """,
            {"episode_id": episode_id},
        )

        candidate_rows: dict[str, dict[str, list[str]]] = {}
        for record in property_rows + support_rows:
            fact_id = str(record.get("fact_id") or "").strip()
            if not fact_id:
                continue
            bucket = candidate_rows.setdefault(
                fact_id,
                {"stored_episode_ids": [], "support_episode_ids": []},
            )
            bucket["stored_episode_ids"] = self._merge_episode_ids(
                bucket["stored_episode_ids"],
                record.get("stored_episode_ids"),
            )
            bucket["support_episode_ids"] = self._merge_episode_ids(
                bucket["support_episode_ids"],
                record.get("support_episode_ids"),
            )

        facts_to_delete: list[str] = []
        facts_to_update: list[dict[str, Any]] = []
        for fact_id, record in candidate_rows.items():
            episode_ids = self._merge_episode_ids(
                record.get("stored_episode_ids"),
                record.get("support_episode_ids"),
            )
            if episode_id not in episode_ids:
                continue
            remaining_episode_ids = [value for value in episode_ids if value != episode_id]
            if remaining_episode_ids:
                facts_to_update.append(
                    {
                        "fact_id": fact_id,
                        "episode_ids": remaining_episode_ids,
                    }
                )
                continue
            facts_to_delete.append(fact_id)

        if facts_to_delete:
            await self._query_records(
                graph_name,
                """
                UNWIND $fact_ids AS fact_id
                MATCH (fact:Fact {fact_id: fact_id})
                DETACH DELETE fact
                """,
                {"fact_ids": facts_to_delete},
            )
        if facts_to_update:
            await self._query_records(
                graph_name,
                """
                UNWIND $updates AS row
                MATCH (fact:Fact {fact_id: row.fact_id})
                SET fact.episode_ids = row.episode_ids
                """,
                {"updates": facts_to_update},
            )

        deleted_episode_node = False
        if episode_exists:
            await self._query_records(
                graph_name,
                """
                MATCH (episode:Episode {episode_id: $episode_id})
                DETACH DELETE episode
                """,
                {"episode_id": episode_id},
            )
            deleted_episode_node = True

        verify_rows = await self._query_records(
            graph_name,
            """
            OPTIONAL MATCH (episode:Episode {episode_id: $episode_id})
            WITH count(episode) AS episode_count
            OPTIONAL MATCH (fact:Fact)
            WHERE $episode_id IN coalesce(fact.episode_ids, [])
            RETURN episode_count, count(fact) AS remaining_fact_count
            """,
            {"episode_id": episode_id},
        )
        remaining_fact_count = int(verify_rows[0].get("remaining_fact_count") or 0) if verify_rows else 0
        deleted_episode_node = deleted_episode_node and bool(
            verify_rows and int(verify_rows[0].get("episode_count") or 0) == 0
        )
        graph_db_latency_ms.labels(operation="falkordb.delete_episode").observe((time.perf_counter() - started) * 1000)
        return DeleteEpisodeResult(
            found=episode_exists or bool(candidate_rows),
            deleted_episode_node=deleted_episode_node,
            deleted_fact_count=len(facts_to_delete),
            updated_fact_count=len(facts_to_update),
            remaining_fact_count=remaining_fact_count,
        )

    async def purge_project(self, project_id: str) -> None:
        await self._admin.drop_project_graph(project_id)

    async def reset(self) -> None:
        return None

    @staticmethod
    def _sanitize_query(query: str) -> str:
        sanitized = query.translate(_SEPARATOR_MAP)
        return " ".join(sanitized.split())

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
    def _record_to_search_result(record: dict, *, base_score: float, graph_boost: float = 0.0) -> dict:
        node = _node_properties(record.get("node"))
        raw_entities = record.get("entities") or []
        entities = [FalkorDBMemoryCore._entity_to_dict(entity) for entity in raw_entities if entity is not None]
        bm25 = max(min(base_score / 10 if base_score > 1 else base_score, 1.0), 0.0)
        time_boost = 0.15 if node.get("invalid_at") is None else 0.05
        score = min((0.70 * bm25) + graph_boost + time_boost, 1.0)
        return {
            "kind": "fact",
            "fact": {
                "id": node.get("fact_id", ""),
                "text": node.get("text", ""),
                "valid_at": node.get("valid_at"),
                "invalid_at": node.get("invalid_at"),
            },
            "entities": entities,
            "provenance": {
                "episode_ids": FalkorDBMemoryCore._normalize_episode_ids(node.get("episode_ids")),
                "reference_time": node.get("valid_at"),
                "ingested_at": node.get("ingested_at"),
            },
            "score": score,
        }

    @staticmethod
    def _fact_record_to_item(record: dict) -> dict:
        fact = _node_properties(record.get("fact"))
        raw_entities = record.get("entities") or []
        entities = [FalkorDBMemoryCore._entity_to_dict(entity) for entity in raw_entities if entity is not None]
        return {
            "id": fact.get("fact_id", ""),
            "text": fact.get("text", ""),
            "valid_at": fact.get("valid_at"),
            "invalid_at": fact.get("invalid_at"),
            "entities": entities,
            "provenance": {
                "episode_ids": FalkorDBMemoryCore._merge_episode_ids(
                    record.get("stored_episode_ids"),
                    record.get("support_episode_ids"),
                )
            },
            "ingested_at": fact.get("ingested_at"),
        }

    @staticmethod
    def _normalize_episode_ids(values: Any) -> list[str]:
        return [str(value) for value in (values or []) if value]

    @staticmethod
    def _merge_episode_ids(*groups: Any) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for value in FalkorDBMemoryCore._normalize_episode_ids(group):
                if value in seen:
                    continue
                seen.add(value)
                merged.append(value)
        return merged

    @staticmethod
    def _entity_to_dict(entity: Any) -> dict:
        props = _node_properties(entity)
        return {
            "id": props.get("entity_id", ""),
            "type": props.get("type", ""),
            "name": props.get("name", ""),
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
