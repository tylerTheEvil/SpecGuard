"""Aggregate the prompt-variant grid into results/prompt_variants/summary.json.

Scans the per-run artifacts written by ``edge_extraction_eval.py
--prompt-variant ...`` and reports, per (variant x provider): precision/recall
spread over runs, proposed/FP counts, guard rejections, critique-pass
removals (with recall damage), and MENTIONS false-positive suppression
relative to the baseline runs.

Methodological guard (honest interpretation): the three few-shot negative
examples baked into the STRICT prompt (``IN_PROMPT_FP_PAIRS``) are part of
the prompt itself, so their suppression is memorisation, not generalisation.
Suppression is therefore reported separately for "in_prompt" pairs vs the
remaining "held_out" baseline FPs. The same split is applied to the critique
variant for comparability (its instruction does not name the pairs, but the
categories it lists were derived from them).

Usage:
    python experiments/prompt_variant_summary.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edge_extraction_eval import IN_PROMPT_FP_PAIRS  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "prompt_variants"

_IN_PROMPT = {(src, tgt) for et, src, tgt in IN_PROMPT_FP_PAIRS if et == "MENTIONS"}


def _spread(values: list[float]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"mean": None, "min": None, "max": None}
    return {"mean": statistics.mean(clean), "min": min(clean), "max": max(clean)}


def _fp_pairs(run: dict, edge_type: str) -> set[tuple[str, str]]:
    return {
        (e["source_id"], e["target"])
        for e in run["per_edge_type"][edge_type]["edges"]
        if e["verdict"] == "FP"
    }


def load_runs() -> dict[tuple[str, str], list[dict]]:
    """Group artifacts by (provider, variant), sorted by filename (run order)."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for path in sorted(RESULTS_DIR.glob("edge_extraction_eval_*.json")):
        run = json.loads(path.read_text())
        # Baseline run-1 files are verbatim copies of the pre-variant canonical
        # artifacts; their config predates the prompt_variant field.
        variant = run["config"].get("prompt_variant", "baseline")
        run["_file"] = path.name
        groups.setdefault((run["provider"], variant), []).append(run)
    return groups


def summarise() -> dict:
    groups = load_runs()

    baseline_fps: dict[str, set[tuple[str, str]]] = {}
    for (provider, variant), runs in groups.items():
        if variant == "baseline":
            union: set[tuple[str, str]] = set()
            for r in runs:
                union |= _fp_pairs(r, "MENTIONS")
            baseline_fps[provider] = union

    cells: dict[str, dict] = {}
    for (provider, variant), runs in sorted(groups.items()):
        cell: dict = {"n_runs": len(runs), "files": [r["_file"] for r in runs]}
        for et in ("MENTIONS", "DERIVES_FROM"):
            per = [r["per_edge_type"][et] for r in runs]
            cell[et] = {
                "precision": _spread([p["precision"] for p in per]),
                "recall": _spread([p["recall"] for p in per]),
                "proposed": [p["proposed"] for p in per],
                "false_positives": [p["false_positives"] for p in per],
            }
        cell["evidence_guard_rejections"] = [
            r["evidence_guard_rejections"] for r in runs
        ]

        # MENTIONS FP suppression vs this provider's baseline union. A
        # baseline FP counts as suppressed only if absent from EVERY run of
        # the variant.
        if variant != "baseline" and provider in baseline_fps:
            variant_fp_union: set[tuple[str, str]] = set()
            for r in runs:
                variant_fp_union |= _fp_pairs(r, "MENTIONS")
            base = baseline_fps[provider]
            suppressed = base - variant_fp_union
            cell["mentions_fp_suppression_vs_baseline"] = {
                "baseline_fp_pairs": len(base),
                "in_prompt": {
                    "total": len(base & _IN_PROMPT),
                    "suppressed": len(suppressed & _IN_PROMPT),
                },
                "held_out": {
                    "total": len(base - _IN_PROMPT),
                    "suppressed": len(suppressed - _IN_PROMPT),
                },
                "new_fps_not_in_baseline": sorted(
                    f"{s}->{t}" for s, t in (variant_fp_union - base)
                ),
            }

        if variant == "critique":
            removed_tp = [
                e
                for r in runs
                for e in r.get("critique", {}).get("removed", [])
                if e.get("in_ground_truth")
            ]
            cell["critique"] = {
                "pre_critique_proposed": [
                    r["critique"]["pre_critique_proposed"] for r in runs
                ],
                "post_critique_proposed": [
                    r["critique"]["post_critique_proposed"] for r in runs
                ],
                "removed_pairs": [len(r["critique"]["removed"]) for r in runs],
                "added_by_critique": [
                    r["critique"]["added_by_critique"] for r in runs
                ],
                "removed_true_positives": [
                    f"{e['edge_type']}:{e['source_id']}->{e['target']}"
                    for e in removed_tp
                ],
            }

        cells[f"{provider}/{variant}"] = cell

    return {
        "_note": (
            "Prompt-variant grid over the edge-extraction eval. Guard, scoring "
            "and ground truth identical across variants; only the system "
            "prompt (strict) or a second same-provider pass (critique) "
            "differs. 'in_prompt' FP suppression is memorisation of the three "
            "few-shot negatives shown verbatim in the strict prompt "
            f"({sorted(f'{s}->{t}' for s, t in _IN_PROMPT)}) and must not be "
            "read as generalisation; 'held_out' suppression is the "
            "generalisation signal. A baseline FP counts as suppressed only "
            "if absent from every run of the variant. Baseline run-1 files "
            "are verbatim copies of the committed canonical artifacts "
            "(config-identical reuse)."
        ),
        "cells": cells,
    }


def main() -> int:
    out = summarise()
    path = RESULTS_DIR / "summary.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {path}")
    for name, cell in out["cells"].items():
        m = cell["MENTIONS"]
        print(
            f"{name:22s} n={cell['n_runs']}  "
            f"P={m['precision']['mean']!r} R={m['recall']['mean']!r} "
            f"proposed={m['proposed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
