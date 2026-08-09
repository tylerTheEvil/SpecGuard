"""Build results/edge_extraction_variance.json from per-run eval artifacts.

Aggregates the canonical eval artifact plus the runs in
``results/variance_runs/`` into per-provider, per-edge-type run-to-run
variance statistics. Replaces the hand-assembled 2026-08-08 artifact, which
mixed one un-seeded Ollama run with two seed=42 runs (the P1.4 data
inconsistency) and predated both the typed REFERS_TO split and the P0.2
proposal guards; that artifact remains reproducible from git history
(commit 4253fb7) but is superseded — pre-fix and post-fix runs must never
be pooled, because the extractor they measure is different.

Decision: seed consistency is ENFORCED, not described. Every Ollama run
must carry ``seed=42, temperature=0`` in its recorded config or the build
fails — the artifact can no longer claim "pinned" while containing an
unpinned run. Anthropic runs are unpinnable by API design (no sampling
params accepted); their config must record ``temperature: "api_default"``.

Usage:
    python experiments/edge_extraction_variance_build.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

RUN_FILES = {
    "anthropic": [
        RESULTS / "edge_extraction_eval_anthropic_opus48.json",
        RESULTS / "variance_runs" / "anthropic_opus48_run2.json",
        RESULTS / "variance_runs" / "anthropic_opus48_run3.json",
    ],
    "ollama": [
        RESULTS / "edge_extraction_eval_ollama_gemma4.json",
        RESULTS / "variance_runs" / "ollama_gemma4_run2.json",
        RESULTS / "variance_runs" / "ollama_gemma4_run3.json",
    ],
}

SCORED_TYPES = ("MENTIONS", "REFERS_TO", "DERIVES_FROM")


def _check_config(provider: str, run: dict, path: Path) -> None:
    cfg = run["config"]
    if provider == "ollama" and (
        cfg.get("seed") != 42 or cfg.get("temperature") != 0
    ):
        raise AssertionError(
            f"{path.name}: ollama run not pinned (seed={cfg.get('seed')}, "
            f"temperature={cfg.get('temperature')}) — every ollama "
            "variance run must be seed=42, temperature=0"
        )
    if provider == "anthropic" and cfg.get("temperature") != "api_default":
        raise AssertionError(
            f"{path.name}: anthropic config must record temperature="
            f"'api_default', got {cfg.get('temperature')!r}"
        )


def _spread(values: list[float | None]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"mean": None, "min": None, "max": None, "stdev": None}
    return {
        "mean": statistics.mean(clean),
        "min": min(clean),
        "max": max(clean),
        "stdev": statistics.stdev(clean) if len(clean) > 1 else 0.0,
    }


def main() -> int:
    runs_out: list[dict] = []
    summary: dict[str, dict] = {}

    for provider, paths in RUN_FILES.items():
        runs = []
        for path in paths:
            run = json.loads(path.read_text())
            _check_config(provider, run, path)
            runs.append(run)
            entry: dict = {
                "provider": run["provider"],
                "model": run["model"],
                "config": run["config"],
                "evidence_guard_rejections": run["evidence_guard_rejections"],
                # Per-reason breakdown (Section V.D); required — a run
                # without it predates the breakdown and must be re-run,
                # not silently aggregated.
                "guard_rejections": run["guard_rejections"],
                "timestamp_utc": run["config"]["timestamp_utc"],
                "file": str(path.relative_to(ROOT)),
                "per_edge_type": {},
            }
            for et in SCORED_TYPES:
                m = run["per_edge_type"][et]
                entry["per_edge_type"][et] = {
                    k: m[k]
                    for k in (
                        "proposed",
                        "ground_truth",
                        "true_positives",
                        "false_positives",
                        "false_negatives",
                        "precision",
                        "recall",
                    )
                }
            runs_out.append(entry)

        summary[provider] = {"n_runs": len(runs)}
        by_reason_total: dict[str, int] = {}
        for run in runs:
            for reason, count in run["guard_rejections"]["by_reason"].items():
                by_reason_total[reason] = by_reason_total.get(reason, 0) + count
        summary[provider]["guard_rejections"] = {
            "total_per_run": [run["guard_rejections"]["total"] for run in runs],
            "by_reason_total": by_reason_total,
        }
        for et in SCORED_TYPES:
            per = [r["per_edge_type"][et] for r in runs]
            summary[provider][et] = {
                "precision": _spread([p["precision"] for p in per]),
                "recall": _spread([p["recall"] for p in per]),
                "proposed": [p["proposed"] for p in per],
            }

    out = {
        "_note": (
            "Run-to-run variance of the TYPED edge-extraction eval (post "
            "REFERS_TO split + P0.2 proposal guards), MENTIONS/REFERS_TO/"
            "DERIVES_FROM scored per type. All Ollama runs are pinned "
            "(seed=42, temperature=0) — enforced by the build script, which "
            "fails on any unpinned run; even pinned, Metal-backend "
            "floating-point non-associativity means bit-reproducibility is "
            "not guaranteed. Anthropic sampling is api_default (Opus rejects "
            "sampling params) and unpinnable by design. MENTIONS and "
            "REFERS_TO references are dictionary-matched surrogates "
            "(circular vs the builder); only DERIVES_FROM is hand-annotated. "
            "Supersedes the 2026-08-08 artifact (git 4253fb7), which mixed "
            "seeded and un-seeded Ollama runs AND measured the pre-fix "
            "extractor — old and new runs are not poolable. 'stdev' is the "
            "sample standard deviation (n-1)."
        ),
        "requirements_evaluated": 64,
        "runs": runs_out,
        "summary": summary,
    }
    path = RESULTS / "edge_extraction_variance.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {path}")
    for provider, s in summary.items():
        for et in SCORED_TYPES:
            p = s[et]["precision"]
            r = s[et]["recall"]
            print(
                f"{provider:10s} {et:12s} P mean={p['mean']} "
                f"[{p['min']}, {p['max']}]  R mean={r['mean']} "
                f"proposed={s[et]['proposed']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
