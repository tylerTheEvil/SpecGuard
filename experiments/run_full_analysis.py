"""Full CVA6 analysis: smell pipeline + linguistic metrics.

Outputs results/full_analysis_with_linguistic.json with per-requirement
smell reports, quality scores, gate decisions, and linguistic metrics.

Prints summary statistics and Spearman correlations between:
  - MDL vs verifiability score
  - Flesch Reading Ease vs overall quality score

Usage:
    pip install -e '.[linguistic]'
    python -m spacy download en_core_web_sm
    python experiments/run_full_analysis.py
"""

from __future__ import annotations

import json
import logging
import statistics
import sys
from pathlib import Path

# Allow running from any directory
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from specguard.core.extended_pipeline import assess_dataset_extended
from specguard.data.cva6_requirements import get_all_requirements

# ---------------------------------------------------------------------------
# Stdlib Spearman rank correlation (no scipy dependency)
# ---------------------------------------------------------------------------

def _spearman(x: list[float], y: list[float]) -> float:
    """Compute Spearman rank correlation coefficient (stdlib only)."""
    n = len(x)
    if n < 2:
        return float("nan")

    def _ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and vals[order[j + 1]] == vals[order[j]]:
                j += 1
            avg_rank = (i + j) / 2.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks

    rx = _ranks(x)
    ry = _ranks(y)
    d_sq = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    denom = n * (n ** 2 - 1)
    return 1.0 - 6.0 * d_sq / denom


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _smell_hit_to_dict(hit) -> dict:
    return {
        "smell_type": hit.smell_type.value,
        "trigger": hit.trigger,
        "position": hit.position,
        "severity": hit.severity,
        "explanation": hit.explanation,
    }


def _result_to_dict(result) -> dict:
    base = result.base
    entry: dict = {
        "requirement_id": base.requirement_id,
        "requirement_text": base.requirement_text,
        "metadata": base.metadata,
        "gate_decision": base.gate_decision,
        "quality_scores": {
            "completeness": base.quality_scores.completeness,
            "consistency": base.quality_scores.consistency,
            "verifiability": base.quality_scores.verifiability,
            "overall": base.quality_scores.overall,
        },
        "smell_report": {
            "smell_count": base.smell_report.smell_count,
            "hits": [_smell_hit_to_dict(h) for h in base.smell_report.hits],
        },
    }
    if result.linguistic is not None:
        lm = result.linguistic
        entry["linguistic"] = {
            "flesch_reading_ease": lm.flesch_reading_ease,
            "flesch_kincaid_grade": lm.flesch_kincaid_grade,
            "mean_dependency_length": lm.mean_dependency_length,
            "max_dependency_length": lm.max_dependency_length,
            "token_count": lm.token_count,
            "sentence_count": lm.sentence_count,
            "mean_sentence_length": lm.mean_sentence_length,
            "lexical_density": lm.lexical_density,
        }
    else:
        entry["linguistic"] = None
    return entry


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def _print_summary(results) -> None:
    ling_results = [r for r in results if r.linguistic is not None]

    if not ling_results:
        logger.warning("No linguistic metrics available. Install specguard[linguistic].")
        return

    fields = [
        ("flesch_reading_ease", "Flesch Reading Ease"),
        ("flesch_kincaid_grade", "Flesch-Kincaid Grade"),
        ("mean_dependency_length", "Mean Dependency Length"),
        ("max_dependency_length", "Max Dependency Length"),
        ("token_count", "Token Count"),
        ("sentence_count", "Sentence Count"),
        ("mean_sentence_length", "Mean Sentence Length"),
        ("lexical_density", "Lexical Density"),
    ]

    print("\n" + "=" * 60)
    print(f"LINGUISTIC METRICS — SUMMARY (CVA6, n={len(ling_results)})")
    print("=" * 60)
    print(f"{'Metric':<28} {'Mean':>8} {'Median':>8} {'StDev':>8}")
    print("-" * 60)

    for attr, label in fields:
        vals = [float(getattr(r.linguistic, attr)) for r in ling_results]
        mean = statistics.mean(vals)
        median = statistics.median(vals)
        stdev = statistics.stdev(vals) if len(vals) > 1 else 0.0
        print(f"{label:<28} {mean:>8.3f} {median:>8.3f} {stdev:>8.3f}")

    # Spearman correlations
    mdl_vals = [r.linguistic.mean_dependency_length for r in ling_results]
    fre_vals = [r.linguistic.flesch_reading_ease for r in ling_results]
    verif_vals = [r.base.quality_scores.verifiability for r in ling_results]
    overall_vals = [r.base.quality_scores.overall for r in ling_results]

    rho_mdl_verif = _spearman(mdl_vals, verif_vals)
    rho_fre_overall = _spearman(fre_vals, overall_vals)

    print()
    print("SPEARMAN CORRELATIONS")
    print("-" * 60)
    print(f"  MDL vs verifiability score:       ρ = {rho_mdl_verif:+.4f}")
    print(f"  Flesch RE vs overall score:        ρ = {rho_fre_overall:+.4f}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    reqs = get_all_requirements()
    logger.info("Loaded %d CVA6 requirements.", len(reqs))

    logger.info("Running extended pipeline (linguistic extra will load if installed)…")
    results = assess_dataset_extended(reqs)

    has_linguistic = any(r.linguistic is not None for r in results)
    if has_linguistic:
        logger.info("Linguistic metrics computed for all requirements.")
    else:
        logger.warning(
            "Linguistic metrics unavailable. "
            "Run: pip install -e '.[linguistic]' && python -m spacy download en_core_web_sm"
        )

    output_path = _ROOT / "results" / "full_analysis_with_linguistic.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": "CVA6 RISC-V requirements specification (OpenHW Group)",
        "n_requirements": len(results),
        "linguistic_available": has_linguistic,
        "requirements": [_result_to_dict(r) for r in results],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.info("Results written to %s", output_path)

    _print_summary(results)


if __name__ == "__main__":
    main()
