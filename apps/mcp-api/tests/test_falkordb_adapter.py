from __future__ import annotations

from viberecall_mcp.memory_core.interface import entity_identity
from viberecall_mcp.memory_core.falkordb_adapter import FalkorDBMemoryCore


def test_entity_identity_is_deterministic() -> None:
    left = entity_identity("File", "apps/web/src/proxy.ts")
    right = entity_identity("File", "apps/web/src/proxy.ts")
    different = entity_identity("Tag", "auth")

    assert left == right
    assert left.startswith("ent_")
    assert left != different


def test_build_entities_maps_episode_metadata() -> None:
    metadata = {
        "files": ["apps/web/src/proxy.ts"],
        "tags": ["auth"],
        "repo": "viberecall",
        "branch": "main",
        "type": "bugfix",
    }

    entities = FalkorDBMemoryCore._build_entities(metadata)

    assert [entity["type"] for entity in entities] == [
        "File",
        "Tag",
        "Repository",
        "Branch",
        "EpisodeType",
    ]
    assert len({entity["entity_id"] for entity in entities}) == 5
