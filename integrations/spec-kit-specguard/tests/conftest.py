"""Shared test setup: make the extension package importable without installing it."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = EXT_ROOT / "scripts" / "python"
FIXTURES = Path(__file__).parent / "fixtures"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def fixture_text():
    def read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return read


@pytest.fixture
def feature_dir(tmp_path):
    """Build a feature directory from fixture files: feature_dir(spec=..., tasks=...)."""

    def make(spec: str | None = None, tasks: str | None = None, name: str = "001-demo") -> Path:
        d = tmp_path / "specs" / name
        d.mkdir(parents=True, exist_ok=True)
        if spec:
            (d / "spec.md").write_text((FIXTURES / spec).read_text(encoding="utf-8"),
                                       encoding="utf-8")
        if tasks:
            (d / "tasks.md").write_text((FIXTURES / tasks).read_text(encoding="utf-8"),
                                        encoding="utf-8")
        return d

    return make
