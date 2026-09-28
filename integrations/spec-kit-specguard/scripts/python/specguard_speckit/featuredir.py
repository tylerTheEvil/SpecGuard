"""Locate the feature being checked, mirroring Spec Kit's own resolution.

Order (Spec Kit ``scripts/python/common.py:get_feature_paths``, v1.0):
explicit path argument > ``SPECIFY_FEATURE_DIRECTORY`` > ``.specify/feature.json``.
Unlike Spec Kit's helper this never writes ``feature.json`` — a checker must
not change which feature is active.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .config import find_repo_root


class ResolutionError(Exception):
    pass


@dataclass
class FeatureTarget:
    feature_dir: Path
    spec_path: Path
    tasks_path: Path
    repo_root: Path | None
    how: str

    def display(self, path: Path) -> str:
        """Path relative to the repo root (or cwd) for stable report output."""
        for base in (self.repo_root, Path.cwd()):
            if base is None:
                continue
            try:
                return path.resolve().relative_to(base.resolve()).as_posix()
            except ValueError:
                continue
        return path.as_posix()


def _target(feature_dir: Path, repo_root: Path | None, how: str, spec: Path | None = None):
    feature_dir = feature_dir.resolve()
    return FeatureTarget(
        feature_dir=feature_dir,
        spec_path=(spec.resolve() if spec else feature_dir / "spec.md"),
        tasks_path=feature_dir / "tasks.md",
        repo_root=repo_root,
        how=how,
    )


def resolve_feature(arg: str | None, cwd: Path | None = None,
                    env: dict | None = None) -> FeatureTarget:
    cwd = cwd or Path.cwd()
    env = os.environ if env is None else env
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            p = cwd / p
        root = find_repo_root(p if p.is_dir() else p.parent)
        if p.is_file() and p.name == "tasks.md":
            return _target(p.parent, root, "argument")  # trace given the tasks file
        if p.is_file():
            return _target(p.parent, root, "argument", spec=p)
        if p.is_dir():
            return _target(p, root, "argument")
        raise ResolutionError(f"{arg}: no such file or directory")

    root = find_repo_root(cwd)
    raw = env.get("SPECIFY_FEATURE_DIRECTORY", "")
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (root or cwd) / p
        return _target(p, root, "SPECIFY_FEATURE_DIRECTORY")

    if root is not None:
        fj = root / ".specify" / "feature.json"
        if fj.is_file():
            try:
                data = json.loads(fj.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ResolutionError(f"{fj}: unreadable ({exc})") from exc
            value = data.get("feature_directory") if isinstance(data, dict) else None
            if isinstance(value, str) and value:
                p = Path(value)
                if not p.is_absolute():
                    p = root / p
                return _target(p, root, ".specify/feature.json")

    raise ResolutionError(
        "Could not determine the feature directory. Pass it explicitly "
        "(e.g. specs/001-my-feature), set SPECIFY_FEATURE_DIRECTORY, or run "
        "/speckit.specify first so .specify/feature.json exists."
    )
