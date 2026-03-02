from __future__ import annotations

import asyncio
from collections import defaultdict

from neo4j import AsyncDriver, AsyncGraphDatabase

from viberecall_mcp.config import get_settings
from viberecall_mcp.neo4j_routing import project_db_name


def _quoted_identifier(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


class Neo4jDatabaseManager:
    def __init__(self) -> None:
        settings = get_settings()
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._initialized: set[str] = set()
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def driver(self) -> AsyncDriver:
        return self._driver

    async def ensure_project_database(self, project_id: str) -> str:
        db_name = project_db_name(project_id)
        if db_name in self._initialized:
            return db_name

        async with self._locks[db_name]:
            if db_name in self._initialized:
                return db_name

            async with self._driver.session(database="system") as session:
                await session.run(f"CREATE DATABASE {_quoted_identifier(db_name)} IF NOT EXISTS")

            await self._ensure_schema(db_name)
            self._initialized.add(db_name)
            return db_name

    async def _ensure_schema(self, db_name: str) -> None:
        statements = [
            "CREATE CONSTRAINT episode_id_unique IF NOT EXISTS FOR (n:Episode) REQUIRE n.episode_id IS UNIQUE",
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE",
            "CREATE CONSTRAINT fact_id_unique IF NOT EXISTS FOR (n:Fact) REQUIRE n.fact_id IS UNIQUE",
            "CREATE INDEX entity_type_name IF NOT EXISTS FOR (n:Entity) ON (n.type, n.name)",
            "CREATE INDEX fact_valid_at IF NOT EXISTS FOR (n:Fact) ON (n.valid_at)",
            "CREATE INDEX fact_invalid_at IF NOT EXISTS FOR (n:Fact) ON (n.invalid_at)",
            "CREATE INDEX episode_ingested_at IF NOT EXISTS FOR (n:Episode) ON (n.ingested_at)",
            "CREATE FULLTEXT INDEX fact_text_index IF NOT EXISTS FOR (n:Fact) ON EACH [n.text]",
        ]
        async with self._driver.session(database=db_name) as session:
            for statement in statements:
                await session.run(statement)

    async def reset_database(self, project_id: str) -> None:
        db_name = await self.ensure_project_database(project_id)
        async with self._driver.session(database=db_name) as session:
            await session.run("MATCH (n) DETACH DELETE n")

    async def drop_project_database(self, project_id: str) -> None:
        db_name = project_db_name(project_id)
        async with self._driver.session(database="system") as session:
            await session.run(f"DROP DATABASE {_quoted_identifier(db_name)} IF EXISTS")
        self._initialized.discard(db_name)

    async def close(self) -> None:
        await self._driver.close()
