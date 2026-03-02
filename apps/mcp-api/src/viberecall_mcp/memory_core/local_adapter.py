from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from viberecall_mcp.ids import new_id
from viberecall_mcp.memory_core.interface import entity_identity


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class LocalMemoryCore:
    def __init__(self) -> None:
        self._facts: dict[str, dict[str, dict]] = defaultdict(dict)

    async def ingest_episode(self, project_id: str, episode: dict) -> dict:
        metadata = episode["metadata_json"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        entities = []
        for file_path in metadata.get("files", []):
            entities.append({"id": entity_identity("File", file_path), "type": "File", "name": file_path})
        for tag in metadata.get("tags", []):
            entities.append({"id": entity_identity("Tag", tag), "type": "Tag", "name": tag})
        if metadata.get("repo"):
            entities.append(
                {"id": entity_identity("Repository", metadata["repo"]), "type": "Repository", "name": metadata["repo"]}
            )
        if metadata.get("branch"):
            entities.append(
                {"id": entity_identity("Branch", metadata["branch"]), "type": "Branch", "name": metadata["branch"]}
            )
        if metadata.get("type"):
            entities.append(
                {"id": entity_identity("EpisodeType", metadata["type"]), "type": "EpisodeType", "name": metadata["type"]}
            )

        fact_id = new_id("fact")
        summary = (episode.get("summary") or episode["content"][:160]).strip()
        fact = {
            "id": fact_id,
            "text": episode["content"],
            "valid_at": _iso(episode.get("reference_time")) or _iso(episode.get("ingested_at")),
            "invalid_at": None,
            "ingested_at": _iso(episode.get("ingested_at")),
            "entities": entities,
            "provenance": {
                "episode_ids": [episode["episode_id"]],
                "reference_time": _iso(episode.get("reference_time")),
                "ingested_at": _iso(episode.get("ingested_at")),
            },
            "summary": summary,
        }
        self._facts[project_id][fact_id] = fact
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
        query_lower = query.lower()
        results = []
        for fact in self._facts[project_id].values():
            if fact["invalid_at"] is not None and filters.get("valid_at") is None:
                continue

            entity_types = set(filters.get("entity_types") or [])
            tags = set(filters.get("tags") or [])
            files = set(filters.get("files") or [])
            if entity_types and not any(entity["type"] in entity_types for entity in fact["entities"]):
                continue
            if tags and not any(entity["type"] == "Tag" and entity["name"] in tags for entity in fact["entities"]):
                continue
            if files and not any(entity["type"] == "File" and entity["name"] in files for entity in fact["entities"]):
                continue

            haystack = " ".join(
                [fact["text"], fact["summary"]]
                + [entity["name"] for entity in fact["entities"]]
            ).lower()
            if query_lower not in haystack:
                continue

            score = 0.7
            if query_lower in fact["text"].lower():
                score += 0.2
            if any(query_lower in entity["name"].lower() for entity in fact["entities"]):
                score += 0.1

            results.append(
                {
                    "kind": "fact",
                    "fact": {
                        "id": fact["id"],
                        "text": fact["text"],
                        "valid_at": fact["valid_at"],
                        "invalid_at": fact["invalid_at"],
                    },
                    "entities": fact["entities"],
                    "provenance": fact["provenance"],
                    "score": min(score, 1.0),
                    "ingested_at": fact["ingested_at"],
                }
            )

        if sort == "RECENCY":
            results.sort(key=lambda item: (item["ingested_at"] or "", item["fact"]["id"]), reverse=True)
        elif sort == "TIME":
            results.sort(
                key=lambda item: (
                    item["fact"]["valid_at"] or item["provenance"]["reference_time"] or "",
                    item["fact"]["id"],
                ),
                reverse=True,
            )
        else:
            results.sort(key=lambda item: (item["score"], item["ingested_at"] or "", item["fact"]["id"]), reverse=True)

        return results[offset : offset + limit]

    async def get_facts(
        self,
        project_id: str,
        *,
        filters: dict,
        limit: int,
        offset: int,
    ) -> list[dict]:
        items = []
        for fact in self._facts[project_id].values():
            entity_type = filters.get("entity_type")
            tag = filters.get("tag")
            valid_at = filters.get("valid_at")
            if entity_type and not any(entity["type"] == entity_type for entity in fact["entities"]):
                continue
            if tag and not any(entity["type"] == "Tag" and entity["name"] == tag for entity in fact["entities"]):
                continue
            if valid_at and fact["invalid_at"] is not None and fact["invalid_at"] <= valid_at:
                continue
            items.append(
                {
                    "id": fact["id"],
                    "text": fact["text"],
                    "valid_at": fact["valid_at"],
                    "invalid_at": fact["invalid_at"],
                    "entities": fact["entities"],
                    "provenance": fact["provenance"],
                    "ingested_at": fact["ingested_at"],
                }
            )

        items.sort(key=lambda fact: (fact["valid_at"] or "", fact["ingested_at"] or "", fact["id"]), reverse=True)
        return items[offset : offset + limit]

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
        old_fact = self._facts[project_id].get(fact_id)
        if old_fact is None:
            raise KeyError(fact_id)

        old_fact["invalid_at"] = effective_time
        self._facts[project_id][new_fact_id] = {
            **old_fact,
            "id": new_fact_id,
            "text": new_text,
            "valid_at": effective_time,
            "invalid_at": None,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        return {
            "old_fact": {"id": fact_id, "invalid_at": effective_time},
            "new_fact": {"id": new_fact_id, "valid_at": effective_time},
        }

    async def purge_project(self, project_id: str) -> None:
        self._facts.pop(project_id, None)

    async def reset(self) -> None:
        self._facts.clear()
