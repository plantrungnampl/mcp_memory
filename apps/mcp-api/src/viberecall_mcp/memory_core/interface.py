from __future__ import annotations

from typing import Protocol


class MemoryCore(Protocol):
    async def ingest_episode(self, project_id: str, episode: dict) -> dict: ...

    async def search(
        self,
        project_id: str,
        *,
        query: str,
        filters: dict,
        sort: str,
        limit: int,
        offset: int,
    ) -> list[dict]: ...

    async def get_facts(
        self,
        project_id: str,
        *,
        filters: dict,
        limit: int,
        offset: int,
    ) -> list[dict]: ...

    async def update_fact(
        self,
        project_id: str,
        *,
        fact_id: str,
        new_fact_id: str,
        new_text: str,
        effective_time: str,
        reason: str | None,
    ) -> dict: ...

    async def purge_project(self, project_id: str) -> None: ...

    async def reset(self) -> None: ...


def entity_identity(entity_type: str, name: str) -> str:
    import hashlib

    normalized = f"{entity_type}:{name.strip().lower()}"
    return f"ent_{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:24]}"
