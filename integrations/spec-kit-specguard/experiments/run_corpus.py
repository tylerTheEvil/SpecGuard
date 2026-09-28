#!/usr/bin/env python3
"""Run the gate over the harvested corpora and write aggregate results.

Configurations (ablation, each over the same parsed requirements):

  core-prefix   ``--profile default`` with a pre-G6–G9 core (``--prefix-core DIR``,
                e.g. ``git show 0f4a305:src/specguard/core/<file>`` into DIR)
  core          ``--profile default`` with the vendored core (G6–G9 included)
  speckit       ``--profile speckit`` (extension default)

Only aggregates and single trigger words are written — no requirement texts —
so results can be committed without redistributing third-party specs.

Usage:
    python experiments/run_corpus.py [--prefix-core DIR] [--set calibration|holdout|all]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT = HERE.parent
sys.path.insert(0, str(EXT / "scripts" / "python"))

CACHE = Path(os.environ.get("SPECGUARD_CORPUS_CACHE", HERE / "cache"))
RESULTS = HERE / "results"
VENDOR_PKG = "specguard_speckit._vendor.specguard_core"


def load_package(core_dir: Path | None):
    """Import the extension, optionally with the vendored core swapped for core_dir."""
    for name in [m for m in sys.modules if m.startswith("specguard_speckit")]:
        del sys.modules[name]
    if core_dir is not None:
        import specguard_speckit._vendor  # noqa: F401  (parent package)

        spec = importlib.util.spec_from_file_location(
            VENDOR_PKG, core_dir / "__init__.py", submodule_search_locations=[str(core_dir)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[VENDOR_PKG] = module
        spec.loader.exec_module(module)
    from specguard_speckit import assess, model, parse_spec, structure

    return assess, model, parse_spec, structure


def analyse_trace(specs: list[dict]) -> dict:
    """spec <-> tasks checks (profile/core independent) on every pair with tasks.md."""
    _, model, parse_spec, _ = load_package(None)
    from specguard_speckit.parse_tasks import parse_tasks
    from specguard_speckit.trace import check_trace

    verdicts, checks, pairs = Counter(), Counter(), 0
    for row in specs:
        folder = CACHE / "corpus" / row["cache"]
        if not (folder / "tasks.md").is_file():
            continue
        pairs += 1
        spec = parse_spec.parse_spec((folder / "spec.md").read_text(errors="replace"))
        tasks = parse_tasks((folder / "tasks.md").read_text(errors="replace"))
        findings, _ = check_trace(spec, tasks)
        verdicts[model.verdict_from(findings, [])] += 1
        checks.update(f"{f.check_id}:{f.severity}" for f in findings)
    return {"pairs": pairs, "verdict": dict(sorted(verdicts.items())),
            "findings": dict(sorted(checks.items()))}


def analyse(specs: list[dict], profile: str, core_dir: Path | None) -> dict:
    assess, model, parse_spec, structure = load_package(core_dir)
    req_rows, spec_rows = [], []
    for row in specs:
        text = (CACHE / "corpus" / row["cache"] / "spec.md").read_text(
            encoding="utf-8", errors="replace")
        doc = parse_spec.parse_spec(text)
        results = assess.assess_all(doc.requirements, profile)
        findings = structure.check_structure(doc, results)
        verdict = model.verdict_from(findings, [r.gate for r in results])
        spec_rows.append({"repo": row["repo"], "verdict": verdict,
                          "n_fr": len(doc.ids("FR")),
                          "checks": sorted({f.check_id for f in findings})})
        for r in results:
            req_rows.append({
                "repo": row["repo"], "kind": r.requirement.kind, "gate": r.gate,
                "sc_class": r.sc_class,
                "hits": [(h.smell_type.value, h.trigger.lower()) for h in r.hits],
                "suppressed": [s.rule for s in r.suppressed],
            })
    return summarize(req_rows, spec_rows)


def rate(rows: list[dict], key: str, value: str) -> float:
    return round(sum(r[key] == value for r in rows) / len(rows), 3) if rows else 0.0


def summarize(req_rows: list[dict], spec_rows: list[dict]) -> dict:
    out: dict = {"requirements": {}, "specs": {}}
    for kind in ("FR", "SC", "NFR", "ALL"):
        sel = [r for r in req_rows if kind == "ALL" or r["kind"] == kind]
        if not sel:
            continue
        by_repo = defaultdict(list)
        for r in sel:
            by_repo[r["repo"]].append(r)
        out["requirements"][kind] = {
            "n": len(sel),
            "gate": {g: rate(sel, "gate", g) for g in ("PASS", "WARN", "FAIL")},
            "pass_rate_macro_by_repo": round(statistics.mean(
                rate(rows, "gate", "PASS") for rows in by_repo.values()), 3),
            "smells_per_req": round(sum(len(r["hits"]) for r in sel) / len(sel), 3),
        }
    out["specs"] = {
        "n": len(spec_rows),
        "verdict": {v: rate(spec_rows, "verdict", v) for v in ("PASS", "WARN", "FAIL")},
        "zero_fr_parsed": sum(s["n_fr"] == 0 for s in spec_rows),
        "check_prevalence": {c: round(n / len(spec_rows), 3) for c, n in sorted(
            Counter(c for s in spec_rows for c in s["checks"]).items())},
    }
    out["smell_types"] = dict(Counter(h[0] for r in req_rows for h in r["hits"]).most_common())
    out["top_triggers"] = [[t, w, n] for (t, w), n in Counter(
        tuple(h) for r in req_rows for h in r["hits"]).most_common(20)]
    out["suppressed"] = dict(sorted(Counter(s for r in req_rows for s in r["suppressed"]).items()))
    out["sc_classes"] = dict(sorted(Counter(r["sc_class"] for r in req_rows
                                            if r["sc_class"]).items()))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prefix-core", type=Path, help="directory with the pre-G6–G9 core")
    ap.add_argument("--set", choices=("calibration", "holdout", "all"), default="all")
    args = ap.parse_args(argv)

    manifest = json.loads((HERE / "corpus_manifest.json").read_text())
    RESULTS.mkdir(exist_ok=True)
    sets = ("calibration", "holdout") if args.set == "all" else (args.set,)
    for set_name in sets:
        specs = [r for r in manifest["specs"] if r["set"] == set_name and not r["fixture"]]
        payload = {
            "set": set_name,
            "specs": len(specs),
            "repositories": len({r["repo"] for r in specs}),
            "fixtures_excluded": sum(r["set"] == set_name and r["fixture"]
                                     for r in manifest["specs"]),
            "configs": {},
        }
        if args.prefix_core:
            payload["configs"]["core-prefix"] = analyse(specs, "default", args.prefix_core)
        payload["configs"]["core"] = analyse(specs, "default", None)
        payload["configs"]["speckit"] = analyse(specs, "speckit", None)
        payload["trace"] = analyse_trace(specs)
        path = RESULTS / f"{set_name}.json"
        path.write_text(json.dumps(payload, indent=1) + "\n")
        print(f"wrote {path.relative_to(EXT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
