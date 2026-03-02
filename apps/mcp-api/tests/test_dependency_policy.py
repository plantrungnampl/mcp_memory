from __future__ import annotations

from pathlib import Path
import tomllib


def _load_pyproject() -> dict:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))


def test_graphiti_dependency_is_pinned() -> None:
    config = _load_pyproject()
    dependencies: list[str] = config["project"]["dependencies"]
    assert "graphiti-core==0.28.1" in dependencies


def test_graphiti_source_is_vendored_local_editable_path() -> None:
    config = _load_pyproject()
    source = config["tool"]["uv"]["sources"]["graphiti-core"]
    assert source.get("path") == "vendor/graphiti"
    assert source.get("editable") is True
    assert "git" not in source
    assert "rev" not in source
    vendor_root = Path(__file__).resolve().parents[1] / "vendor" / "graphiti"
    assert vendor_root.exists()
    assert (vendor_root / "graphiti_core").exists()
