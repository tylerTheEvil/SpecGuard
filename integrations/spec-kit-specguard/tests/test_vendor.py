"""Vendored SpecGuard core: hash lock, upstream equality, stdlib-only package."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import pytest
from conftest import EXT_ROOT, SCRIPTS

VENDOR = SCRIPTS / "specguard_speckit" / "_vendor" / "specguard_core"
LOCK = json.loads((VENDOR / "VENDOR.json").read_text(encoding="utf-8"))
MONOREPO_CORE = EXT_ROOT.parents[1] / "src" / "specguard" / "core"


def test_lock_matches_vendored_files():
    for name, digest in LOCK["files"].items():
        assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == digest, name


def test_lock_provenance_fields():
    assert LOCK["source_repository"].startswith("https://")
    assert set(LOCK["files"]) == {"smell_detector.py", "quality_scorer.py"}
    assert LOCK["source_commit"] is None or len(LOCK["source_commit"]) == 40


@pytest.mark.skipif(not MONOREPO_CORE.is_dir(), reason="not inside the SpecGuard monorepo")
def test_vendored_equals_upstream_core():
    for name in LOCK["files"]:
        assert (VENDOR / name).read_bytes() == (MONOREPO_CORE / name).read_bytes(), (
            f"{name} drifted from upstream: run python tools/sync_vendor.py --source ../.."
        )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    return out


def test_package_is_stdlib_only():
    stdlib = set(getattr(sys, "stdlib_module_names", ())) or {
        "__future__", "argparse", "ast", "collections", "dataclasses", "enum", "hashlib",
        "json", "os", "pathlib", "re", "shutil", "subprocess", "sys", "typing",
    }
    allowed = stdlib | {"specguard_speckit"}
    for py in (SCRIPTS).rglob("*.py"):
        third_party = _imports(py) - allowed
        assert not third_party, f"{py.relative_to(EXT_ROOT)} imports {third_party}"
