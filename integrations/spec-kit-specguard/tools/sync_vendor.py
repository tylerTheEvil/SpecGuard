#!/usr/bin/env python3
"""Vendor the SpecGuard deterministic core into the extension, with a hash lock.

The extension ships a byte-exact copy of the two stdlib-only core modules it
needs (``smell_detector.py``, ``quality_scorer.py``). ``VENDOR.json`` records
where they came from (repository, commit, source paths) and their SHA-256, so
the exact detector version inside an installed extension is identifiable —
the configuration-identification discipline DO-330 asks of a qualified tool.

Usage (from the extension root):

    python tools/sync_vendor.py --source ../..          # copy + rewrite lock
    python tools/sync_vendor.py --source ../.. --check  # verify, no writes
    python tools/sync_vendor.py --check                 # verify lock only

Exit codes: 0 ok, 1 drift detected (``--check``), 2 usage/source error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

EXT_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = EXT_ROOT / "scripts" / "python" / "specguard_speckit" / "_vendor" / "specguard_core"
LOCK_PATH = VENDOR_DIR / "VENDOR.json"
CORE_FILES = ("smell_detector.py", "quality_scorer.py")
CORE_REL = Path("src") / "specguard" / "core"
UPSTREAM = "https://github.com/tylerTheEvil/SpecGuard"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(source: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(source), *args], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.stdout.strip()


def source_state(source: Path) -> dict:
    """Commit and cleanliness of the core files in the source checkout."""
    commit = git(source, "rev-parse", "HEAD")
    rels = [str(CORE_REL / name) for name in CORE_FILES]
    dirty = bool(git(source, "status", "--porcelain", "--", *rels)) if commit else None
    return {"commit": commit or None, "dirty": dirty}


def write_lock(source: Path) -> dict:
    state = source_state(source)
    lock = {
        "source_repository": UPSTREAM,
        "source_commit": state["commit"],
        "source_dirty": state["dirty"],
        "source_paths": {name: str(CORE_REL / name) for name in CORE_FILES},
        "files": {name: sha256(VENDOR_DIR / name) for name in CORE_FILES},
        "note": (
            "Byte-exact copies of the SpecGuard deterministic core. Do not edit "
            "here: fix upstream, then re-run tools/sync_vendor.py. "
            "source_dirty=true means the copy was taken from uncommitted "
            "upstream changes; re-sync after the upstream commit."
        ),
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock


def check(source: Path | None) -> list[str]:
    """Return a list of drift problems (empty = consistent)."""
    problems: list[str] = []
    if not LOCK_PATH.is_file():
        return [f"missing lock file {LOCK_PATH.relative_to(EXT_ROOT)}"]
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    for name in CORE_FILES:
        vendored = VENDOR_DIR / name
        if not vendored.is_file():
            problems.append(f"missing vendored file {name}")
            continue
        if sha256(vendored) != lock["files"].get(name):
            problems.append(f"{name}: vendored copy does not match VENDOR.json hash")
        if source is not None:
            upstream = source / CORE_REL / name
            if not upstream.is_file():
                problems.append(f"{name}: upstream file not found at {upstream}")
            elif sha256(upstream) != sha256(vendored):
                problems.append(f"{name}: vendored copy differs from upstream {upstream}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", type=Path, help="SpecGuard repository root")
    ap.add_argument("--check", action="store_true", help="verify only, no writes")
    args = ap.parse_args(argv)

    source = args.source.resolve() if args.source else None
    if source is not None and not (source / CORE_REL).is_dir():
        print(f"error: {source} is not a SpecGuard checkout (no {CORE_REL})", file=sys.stderr)
        return 2

    if args.check:
        problems = check(source)
        for p in problems:
            print(f"DRIFT: {p}", file=sys.stderr)
        if not problems:
            print("vendored core consistent with lock" + (" and upstream" if source else ""))
        return 1 if problems else 0

    if source is None:
        print("error: --source is required to sync", file=sys.stderr)
        return 2
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    for name in CORE_FILES:
        shutil.copyfile(source / CORE_REL / name, VENDOR_DIR / name)
    init = VENDOR_DIR / "__init__.py"
    if not init.exists():
        init.write_text('"""Vendored SpecGuard core — see VENDOR.json."""\n', encoding="utf-8")
    lock = write_lock(source)
    print(json.dumps(lock, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
