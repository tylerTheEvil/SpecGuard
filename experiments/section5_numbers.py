"""Emit the per-type P/R/F1 numbers for the paper's Section V tables.

Reads the typed post-fix artifacts (the variance artifact for the live
providers, the canonical mock artifact for the offline smoke reference) and
writes ``results/section5_numbers.json`` — the single place the manuscript
tables should be updated from, replacing the superseded combined-taxonomy
figures (``retaxonomy_rescore.py``).

Honesty constraints encoded here rather than left to prose:

* Every metric row carries a ``reference`` field labelling its ground truth:
  MENTIONS and REFERS_TO are dictionary-matched surrogates (builder output —
  circular, agreement metrics, not validated truth); DERIVES_FROM is the
  3-pair hand-annotated set (non-circular but illustrative only).
* F1 is computed per run and aggregated (mean/min/max), never from averaged
  P and R.
* Prompt-variant rows are explicitly NOT emitted: the committed grid
  artifacts predate the typed REFERS_TO split (standards were collapsed into
  MENTIONS at proposal time), so no typed variant numbers exist. If Section V
  keeps variant rows, the grid must be re-run under the typed extractor —
  this script refuses to dress pre-fix numbers up as typed ones.

Usage:
    python experiments/section5_numbers.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

SCORED_TYPES = ("MENTIONS", "REFERS_TO", "DERIVES_FROM")

REFERENCE_LABELS = {
    "MENTIONS": (
        "dictionary-matched surrogate (builder KNOWN_COMPONENTS, 75 edges; "
        "circular — agreement with the deterministic matcher, not validated "
        "truth)"
    ),
    "REFERS_TO": (
        "dictionary-matched surrogate (builder KNOWN_STANDARDS, 21 edges; "
        "same circularity as MENTIONS)"
    ),
    "DERIVES_FROM": (
        "hand-annotated, 3 pairs (non-circular but illustrative only — CVA6 "
        "is structurally flat)"
    ),
}


def _f1(p: float | None, r: float | None) -> float | None:
    """F1 per run. None only when precision is undefined (nothing proposed);
    a run with P=0 or R=0 scores F1=0.0 — excluding it would inflate means."""
    if p is None or r is None:
        return None
    if (p + r) == 0:
        return 0.0
    return 2 * p * r / (p + r)


def _spread(values: list[float | None]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"mean": None, "min": None, "max": None}
    return {"mean": statistics.mean(clean), "min": min(clean), "max": max(clean)}


def _rows_from_runs(runs: list[dict], source: str) -> dict:
    rows: dict[str, dict] = {}
    for et in SCORED_TYPES:
        per = [r["per_edge_type"][et] for r in runs]
        rows[et] = {
            "reference": REFERENCE_LABELS[et],
            "n_runs": len(runs),
            "ground_truth_size": per[0]["ground_truth"],
            "proposed": [p["proposed"] for p in per],
            "true_positives": [p["true_positives"] for p in per],
            "false_positives": [p["false_positives"] for p in per],
            "false_negatives": [p["false_negatives"] for p in per],
            "precision": _spread([p["precision"] for p in per]),
            "recall": _spread([p["recall"] for p in per]),
            "f1": _spread([_f1(p["precision"], p["recall"]) for p in per]),
            "source": source,
        }
    return rows


def main() -> int:
    variance = json.loads((RESULTS / "edge_extraction_variance.json").read_text())
    mock = json.loads((RESULTS / "edge_extraction_eval.json").read_text())

    providers: dict[str, dict] = {}
    for provider in ("anthropic", "ollama"):
        runs = [r for r in variance["runs"] if r["provider"] == provider]
        model = runs[0]["model"]
        providers[provider] = {
            "model": model,
            "sampling": runs[0]["config"].get("temperature"),
            "seed": runs[0]["config"].get("seed"),
            # Section V.D: which guard fired, measured — not assumed.
            "guard_rejections": variance["summary"][provider]["guard_rejections"],
            # Flag-and-route: unbound-evidence proposals survive and are
            # scored; the flagged set is NOT adjudicated — it may contain
            # both semantic aliases (lexicon coverage gaps) and genuinely
            # irrelevant spans; no claim either way until human adjudication.
            "unbound_evidence_flags": variance["summary"][provider][
                "unbound_evidence_flags"
            ],
            **_rows_from_runs(runs, "results/edge_extraction_variance.json"),
        }
    providers["mock"] = {
        "model": None,
        "note": "deterministic offline replay of the dictionary matcher",
        **_rows_from_runs([mock], "results/edge_extraction_eval.json"),
    }

    out = {
        "_note": (
            "Per-type P/R/F1 for Section V, from the TYPED post-fix extractor "
            "(REFERS_TO first-class, P0.2 proposal guards active). Live "
            "providers: n=3 runs each (see variance artifact); mock: n=1, "
            "deterministic. F1 computed per run, then aggregated. These "
            "REPLACE the combined-taxonomy figures from "
            "retaxonomy_rescore.json (superseded)."
        ),
        "prompt_variants": (
            "NOT AVAILABLE under the typed extractor. The committed grid "
            "(results/prompt_variants/, git 8d6828e) measured the pre-fix "
            "extractor with standards collapsed into MENTIONS; its numbers "
            "are not comparable to the typed rows above and must not be "
            "placed in the same table. The typed grid re-run (Task 2, "
            "~$4 Anthropic + Ollama hours) was NOT executed — live budget "
            "not approved at generation time. Re-run the grid under the "
            "typed extractor into results/prompt_variants_typed/ if "
            "Section V keeps variant rows."
        ),
        "providers": providers,
    }
    path = RESULTS / "section5_numbers.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {path}")
    for name, prov in providers.items():
        for et in SCORED_TYPES:
            row = prov[et]
            p, r, f = row["precision"]["mean"], row["recall"]["mean"], row["f1"]["mean"]
            fmt = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
            print(
                f"{name:10s} {et:12s} P={fmt(p)} R={fmt(r)} F1={fmt(f)} "
                f"proposed={row['proposed']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
