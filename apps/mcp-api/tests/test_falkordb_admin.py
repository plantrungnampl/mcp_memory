from __future__ import annotations

from viberecall_mcp.memory_core.falkordb_admin import FalkorDBGraphManager


class FakeGraph:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def query(self, statement: str, params=None):  # noqa: ANN001
        self.queries.append(statement)
        return []


class FakeClient:
    def __init__(self) -> None:
        self.graphs: dict[str, FakeGraph] = {}

    def select_graph(self, name: str) -> FakeGraph:
        graph = self.graphs.get(name)
        if graph is None:
            graph = FakeGraph()
            self.graphs[name] = graph
        return graph


class DummyAdmin(FalkorDBGraphManager):
    def __init__(self) -> None:
        super().__init__()
        self.fake_client = FakeClient()
        self.client_access_count = 0

    @property
    def client(self):  # type: ignore[override]
        self.client_access_count += 1
        return self.fake_client


async def test_verify_connectivity_uses_lazy_client_property() -> None:
    admin = DummyAdmin()

    await admin.verify_connectivity()

    assert admin.client_access_count >= 1
    assert "healthcheck" in admin.fake_client.graphs
    assert admin.fake_client.graphs["healthcheck"].queries == ["RETURN 1"]


async def test_ensure_project_graph_uses_lazy_client_property() -> None:
    admin = DummyAdmin()

    graph_name = await admin.ensure_project_graph("proj_test")

    assert graph_name == "vr-proj-test"
    assert admin.client_access_count >= 2
    graph = admin.fake_client.graphs[graph_name]
    assert graph.queries[0] == "RETURN 1"
