from __future__ import annotations

from viberecall_mcp import graphiti_clients


def test_ensure_graphiti_openai_env_backfills_openai_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    graphiti_clients.ensure_graphiti_openai_env("sk-test-graphiti")

    assert graphiti_clients.os.environ["OPENAI_API_KEY"] == "sk-test-graphiti"


def test_build_graphiti_openai_components_wires_reranker_to_configured_client(monkeypatch) -> None:
    created: dict[str, object] = {}

    class FakeOpenAIClient:
        def __init__(self, *, config):
            created["llm_config"] = config
            self.client = object()

    class FakeOpenAIEmbedder:
        def __init__(self, *, config):
            created["embedder_config"] = config

    class FakeOpenAIRerankerClient:
        def __init__(self, *, config, client):
            created["reranker_config"] = config
            created["reranker_client"] = client

    monkeypatch.setattr(graphiti_clients, "OpenAIClient", FakeOpenAIClient)
    monkeypatch.setattr(graphiti_clients, "OpenAIEmbedder", FakeOpenAIEmbedder)
    monkeypatch.setattr(graphiti_clients, "OpenAIRerankerClient", FakeOpenAIRerankerClient)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm_client, embedder, reranker = graphiti_clients.build_graphiti_openai_components(
        api_key="sk-test-graphiti",
        llm_model="gpt-4.1-mini",
        embedder_model="text-embedding-3-small",
    )

    assert isinstance(llm_client, FakeOpenAIClient)
    assert isinstance(embedder, FakeOpenAIEmbedder)
    assert isinstance(reranker, FakeOpenAIRerankerClient)
    assert created["llm_config"].api_key == "sk-test-graphiti"
    assert created["embedder_config"].api_key == "sk-test-graphiti"
    assert created["reranker_config"].api_key == "sk-test-graphiti"
    assert created["reranker_client"] is llm_client
    assert graphiti_clients.os.environ["OPENAI_API_KEY"] == "sk-test-graphiti"
