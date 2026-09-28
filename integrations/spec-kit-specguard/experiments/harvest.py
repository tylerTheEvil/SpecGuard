#!/usr/bin/env python3
"""Harvest in-the-wild Spec Kit specs from repositories listed in Spec Kit catalogs.

Two disjoint repository sets:

calibration  every repository in ``extensions/catalog.community.json`` —
             extension authors build their extensions with Spec Kit, so their
             repos hold real ``specs/*/spec.md`` from many authors and models.
holdout      repositories in the presets / integrations / workflows / bundles
             catalogs that are NOT in the extension catalog. Profile rules were
             frozen before this set was first analysed.

Only provenance is committed (``corpus_manifest.json``: repo URL, commit SHA,
path). Spec texts are third-party content and stay in ``experiments/cache/``
(gitignored); ``--from-manifest`` re-fetches the exact pinned commits.

Usage:
    python experiments/harvest.py --speckit /path/to/spec-kit      # discover + pin
    python experiments/harvest.py --from-manifest                  # reproduce
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Shallow clones of ~200 repos take ~650 MB; point this outside the checkout if needed.
CACHE = Path(os.environ.get("SPECGUARD_CORPUS_CACHE", HERE / "cache"))
MANIFEST = HERE / "corpus_manifest.json"
FR_RE = re.compile(r"\bFR-\d{3}\b")
SKIP_PARTS = {"node_modules", ".git", "templates", ".specify"}
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}


def norm(url: str) -> str:
    url = url.strip().rstrip("/")
    return url[:-4] if url.endswith(".git") else url


def catalog_repos(speckit: Path) -> dict[str, list[str]]:
    ext = json.loads((speckit / "extensions" / "catalog.community.json").read_text())
    calibration = sorted({norm(v["repository"]) for v in ext["extensions"].values()
                          if v.get("repository")})
    others: set[str] = set()
    for path in sorted(speckit.glob("*/catalog*.json")):
        if path.parent.name == "extensions":
            continue
        for value in json.loads(path.read_text()).values():
            if isinstance(value, dict):
                others |= {norm(v["repository"]) for v in value.values()
                           if isinstance(v, dict) and v.get("repository")}
    lower = {u.lower() for u in calibration}
    holdout = sorted(u for u in others
                     if u.lower() not in lower and "/github/spec-kit" not in u.lower())
    return {"calibration": calibration, "holdout": holdout}


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          env=GIT_ENV, timeout=180)


def fetch(url: str, dest: Path, commit: str | None) -> str | None:
    """Shallow checkout of ``url`` (at ``commit`` if given); return HEAD SHA."""
    if dest.exists():
        shutil.rmtree(dest)
    if commit is None:
        if git("clone", "-q", "--depth", "1", url, str(dest)).returncode != 0:
            return None
    else:
        dest.mkdir(parents=True)
        steps = (("init", "-q"), ("remote", "add", "origin", url),
                 ("fetch", "-q", "--depth", "1", "origin", commit),
                 ("checkout", "-q", "FETCH_HEAD"))
        for step in steps:
            if git(*step, cwd=dest).returncode != 0:
                return None
    return git("rev-parse", "HEAD", cwd=dest).stdout.strip() or None


def is_fixture(rel: str) -> bool:
    """Specs inside test/fixture/example trees are parser fixtures, not features."""
    return re.search(r"(^|/)(tests?|fixtures?|examples?)/", rel) is not None


def collect(set_name: str, url: str, clone: Path, commit: str) -> list[dict]:
    rows = []
    owner_repo = "__".join(url.split("/")[-2:])
    for spec in sorted(clone.rglob("spec.md")):
        rel = spec.relative_to(clone).as_posix()
        if SKIP_PARTS & set(spec.relative_to(clone).parts):
            continue
        if not FR_RE.search(spec.read_text(encoding="utf-8", errors="replace")):
            continue
        out = CACHE / "corpus" / set_name / owner_repo / rel.replace("/", "__")
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(spec, out / "spec.md")
        tasks = spec.parent / "tasks.md"
        if tasks.is_file():
            shutil.copyfile(tasks, out / "tasks.md")
        rows.append({"set": set_name, "repo": url, "commit": commit, "path": rel,
                     "fixture": is_fixture(rel), "tasks": tasks.is_file(),
                     "cache": out.relative_to(CACHE / "corpus").as_posix()})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--speckit", type=Path, help="spec-kit checkout with the catalogs")
    src.add_argument("--from-manifest", action="store_true", help="re-fetch pinned commits")
    args = ap.parse_args(argv)

    clones = CACHE / "clones"
    clones.mkdir(parents=True, exist_ok=True)
    if (CACHE / "corpus").exists():
        shutil.rmtree(CACHE / "corpus")

    if args.from_manifest:
        manifest = json.loads(MANIFEST.read_text())
        jobs = sorted({(r["set"], r["repo"], r["commit"]) for r in manifest["specs"]})
    else:
        sets = catalog_repos(args.speckit)
        sk_commit = git("rev-parse", "HEAD", cwd=args.speckit).stdout.strip()
        jobs = [(s, url, None) for s, urls in sets.items() for url in urls]

    def work(job):
        set_name, url, commit = job
        dest = clones / set_name / "__".join(url.split("/")[-2:])
        head = fetch(url, dest, commit)
        return (set_name, url, head, collect(set_name, url, dest, head) if head else [])

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(work, jobs))

    failed = [url for _, url, head, _ in results if head is None]
    specs = sorted((row for *_, rows in results for row in rows),
                   key=lambda r: (r["set"], r["repo"], r["path"]))
    if args.from_manifest:
        pinned = {(r["repo"], r["commit"], r["path"]) for r in manifest["specs"]}
        fetched = {(r["repo"], r["commit"], r["path"]) for r in specs}
        if pinned != fetched:
            print(f"WARNING: re-fetch differs from manifest: missing {len(pinned - fetched)}, "
                  f"extra {len(fetched - pinned)}", file=sys.stderr)
        else:  # identical corpus: refresh derived fields only
            manifest["specs"] = specs
            MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    else:
        MANIFEST.write_text(json.dumps({
            "speckit_catalog_commit": sk_commit,
            "repositories": {s: len(u) for s, u in sets.items()},
            "clone_failures": failed,
            "specs": specs,
        }, indent=1) + "\n")
    for set_name in ("calibration", "holdout"):
        sel = [r for r in specs if r["set"] == set_name]
        print(f"{set_name}: {len(sel)} spec.md files ({sum(r['fixture'] for r in sel)} fixtures) "
              f"from {len({r['repo'] for r in sel})} repos", file=sys.stderr)
    if failed:
        print(f"clone failures: {len(failed)}: {failed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
