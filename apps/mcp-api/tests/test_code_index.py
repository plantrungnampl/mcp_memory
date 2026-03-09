from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from viberecall_mcp import code_index


def _build_bundle(*, members: dict[str, str], manifest_files: list[str] | None = None) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        file_entries = manifest_files if manifest_files is not None else list(members.keys())
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format_version": 1,
                    "files": [{"path": path} for path in file_entries],
                }
            ),
        )
        for path, content in members.items():
            archive.writestr(path, content)
    return payload.getvalue()


def test_validate_workspace_bundle_archive_rejects_path_traversal() -> None:
    payload = _build_bundle(members={"../escape.py": "print('bad')"})

    with pytest.raises(ValueError, match="invalid path entries"):
        code_index.validate_workspace_bundle_archive(payload)


def test_validate_workspace_bundle_archive_rejects_symlink_entries() -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"format_version": 1, "files": [{"path": "src/app.py"}]}),
        )
        link = zipfile.ZipInfo("src/app.py")
        link.external_attr = 0o120777 << 16
        archive.writestr(link, "ignored")

    with pytest.raises(ValueError, match="may not contain symlinks"):
        code_index.validate_workspace_bundle_archive(payload.getvalue())


def test_materialize_index_emits_expected_entities_chunks_and_stats() -> None:
    materialized = code_index._materialize_index(
        project_id="proj_demo",
        repo_path=Path("/tmp/demo-repo"),
        indexed_at="2026-03-09T00:00:00+00:00",
        mode="snapshot",
        source="indexing",
        file_rows=[
            {
                "path": "demo.py",
                "language": "python",
                "module": "root",
                "sha1": "sha1-demo",
                "symbols": [
                    {
                        "name": "do_work",
                        "kind": "function",
                        "line_start": 1,
                        "line_end": 2,
                        "snippet": "def do_work():\n    return 'ok'",
                        "tokens": ["do_work", "return"],
                    }
                ],
                "imports": ["json"],
                "snippet": "def do_work():\n    return 'ok'",
                "tokens": ["do_work", "json"],
            }
        ],
    )

    assert materialized["stats"] == {
        "file_count": 1,
        "symbol_count": 1,
        "entity_count": 4,
        "relationship_count": 3,
        "chunk_count": 2,
    }
    assert materialized["architecture"]["top_modules"] == [
        {"module": "root", "file_count": 1, "symbol_count": 1}
    ]
    assert materialized["architecture"]["top_files"] == [
        {"file_path": "demo.py", "symbol_count": 1}
    ]
    assert {entity["entity_id"] for entity in materialized["entities"]} == {
        "module:root",
        "file:demo.py",
        "import:json",
        "symbol:demo.py:do_work:1",
    }
