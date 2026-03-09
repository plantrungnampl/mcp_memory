from __future__ import annotations

import os

from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient


def ensure_graphiti_openai_env(api_key: str | None) -> None:
    key = (api_key or "").strip()
    if not key:
        return
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = key


def build_graphiti_openai_components(
    *,
    api_key: str | None,
    llm_model: str,
    embedder_model: str,
) -> tuple[OpenAIClient, OpenAIEmbedder, OpenAIRerankerClient]:
    ensure_graphiti_openai_env(api_key)

    llm_config = LLMConfig(
        api_key=api_key,
        model=llm_model,
        small_model=llm_model,
    )
    llm_client = OpenAIClient(config=llm_config)
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=api_key,
            embedding_model=embedder_model,
        )
    )
    reranker = OpenAIRerankerClient(
        config=LLMConfig(api_key=api_key),
        client=llm_client,
    )
    return llm_client, embedder, reranker
