from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from viberecall_mcp.config import get_settings
from viberecall_mcp.graph_routing import project_graph_name

if TYPE_CHECKING:
    from falkordb.asyncio import FalkorDB


def _is_schema_already_present(exc: Exception) -> bool:
    message = str(exc).lower()
    return "already indexed" in message or "already exists" in message


class FalkorDBGraphManager:
    def __init__(self) -> None:
        settings = get_settings()
        self._host = settings.falkordb_host
        self._port = settings.falkordb_port
        self._username = settings.falkordb_username.strip() or None
        self._password = settings.falkordb_password.strip() or None
        self._client: FalkorDB | None = None
        self._initialized: set[str] = set()
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def client(self) -> FalkorDB:
        if self._client is None:
            from falkordb.asyncio import FalkorDB

            self._client = FalkorDB(
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
            )
        return self._client

    async def ensure_project_graph(self, project_id: str) -> str:
        graph_name = project_graph_name(project_id)
        if graph_name in self._initialized:
            return graph_name

        async with self._locks[graph_name]:
            if graph_name in self._initialized:
                return graph_name

            graph = self.client.select_graph(graph_name)
            await graph.query("RETURN 1")
            await self._ensure_schema(graph_name)
            self._initialized.add(graph_name)
            return graph_name

    async def _ensure_schema(self, graph_name: str) -> None:
        graph = self.client.select_graph(graph_name)
        statements = [
            "CREATE INDEX FOR (n:Entity) ON (n.entity_id)",
            "CREATE INDEX FOR (n:Entity) ON (n.type, n.name)",
            "CREATE INDEX FOR (n:Fact) ON (n.fact_id)",
            "CREATE INDEX FOR (n:Fact) ON (n.valid_at)",
            "CREATE INDEX FOR (n:Fact) ON (n.invalid_at)",
            "CREATE INDEX FOR (n:Episode) ON (n.episode_id)",
            "CREATE INDEX FOR (n:Episode) ON (n.ingested_at)",
            (
                "CALL db.idx.fulltext.createNodeIndex("
                "{label:'Fact', stopwords:['a','an','and','are','as','at','be','by','for','from',"
                "'in','is','it','of','on','or','that','the','to','was','with']}, 'text')"
            ),
        ]
        for statement in statements:
            try:
                await graph.query(statement)
            except Exception as exc:  # noqa: BLE001
                if _is_schema_already_present(exc):
                    continue
                raise

    async def reset_graph(self, project_id: str) -> None:
        graph_name = await self.ensure_project_graph(project_id)
        graph = self.client.select_graph(graph_name)
        await graph.query("MATCH (n) DETACH DELETE n")

    async def drop_project_graph(self, project_id: str) -> None:
        graph_name = project_graph_name(project_id)
        graph = self.client.select_graph(graph_name)
        deleted = False

        delete_func = getattr(graph, "delete", None)
        if callable(delete_func):
            await delete_func()
            deleted = True

        if not deleted:
            await self._delete_graph_fallback(graph_name)

        self._initialized.discard(graph_name)

    async def _delete_graph_fallback(self, graph_name: str) -> None:
        # Fallback for client versions that don't expose Graph.delete().
        client = self.client
        connection = getattr(client, "connection", None)
        if connection is not None and hasattr(connection, "execute_command"):
            await connection.execute_command("GRAPH.DELETE", graph_name)
            return

        execute_command = getattr(client, "execute_command", None)
        if callable(execute_command):
            await execute_command("GRAPH.DELETE", graph_name)
            return

        raise RuntimeError("Unable to delete FalkorDB graph: no supported command API found")

    async def verify_connectivity(self) -> None:
        graph = self.client.select_graph("healthcheck")
        await graph.query("RETURN 1")

    async def close(self) -> None:
        if self._client is None:
            return

        # Different client versions expose different close methods.
        if hasattr(self._client, "aclose"):
            await self._client.aclose()  # type: ignore[reportUnknownMemberType]
            return

        connection: Any = getattr(self._client, "connection", None)
        if connection is not None and hasattr(connection, "aclose"):
            await connection.aclose()
            return
        if connection is not None and hasattr(connection, "close"):
            await connection.close()
