"""De-circularized seeded-fault validation (independent lexicon).

This is the *method-level* validation experiment. Unlike
``experiments/seeded_faults.py`` (whose 100% recall is true by construction
because it injects the detector's own trigger words), this experiment injects
faults using ONLY the INDEPENDENT lexicon in ``independent_lexicon.py`` — terms
taken from published requirements-quality literature (INCOSE GtWR, Femmer 2017,
Berry & Kamsties, ISO 29148) that are programmatically verified disjoint from
the detector's lexicons.

Consequences, by design:
* Recall below 100% is EXPECTED and acceptable. The gap quantifies the coverage
  limit of a closed deterministic lexicon and is publishable evidence (Paper #3
  "lexicon coverage" limitation). The detector is NOT tuned to close it.
* We also compute precision over (mutated ∪ clean) and a false-positive rate on
  the clean 64-requirement set, with a documented exclusion rule for genuine
  pre-existing defects (see ``KNOWN_PREEXISTING_DEFECTS``).

A second optional tier evaluates LLM-written *blind* mutations
(``experiments/data/blind_mutations.json``, produced by a separate agent blind
to the detector lexicons) if that file exists.

Deterministic: ``random.seed`` is fixed. Stdlib-only.

Methodology references:
- Femmer et al. (2017), "Rapid Quality Assurance with Requirements Smells", JSS.
- Zakeri-Nasrabadi et al. (2024), Neural Computing and Applications — mutation-
  style validation of smell detection.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from independent_lexicon import (
    OVERLAP_REPORT,
    PLACEHOLDER_CLOSED_VOCAB_NOTE,
    independent_terms,
    lexicon_sizes,
)

from specguard import assess_requirement
from specguard.core.smell_detector import SmellType
from specguard.data.cva6_requirements import get_all_requirements

SEED = 42
N_PER_TYPE = 10

RESULTS_PATH = Path(__file__).parent.parent / "results" / "seeded_faults_independent.json"
BLIND_PATH = Path(__file__).parent / "data" / "blind_mutations.json"

# Fault type -> the SmellType(s) that count as a correct detection for it.
# Note: an injected single subjective adjective (ambiguity) may surface as
# AMBIGUITY; a multi-word judgement phrase may surface as SUBJECTIVITY; an
# escape clause (optionality) may surface as OPTIONALITY or WEAKNESS. We accept
# the semantically-equivalent smell family so recall is not penalised by the
# detector's internal category boundaries.
EXPECTED_SMELLS: dict[str, set[SmellType]] = {
    "ambiguity": {SmellType.AMBIGUITY, SmellType.SUBJECTIVITY},
    "vagueness": {SmellType.VAGUENESS},
    "optionality": {SmellType.OPTIONALITY, SmellType.WEAKNESS},
    "comparative": {SmellType.COMPARATIVE},
    "placeholder": {SmellType.PLACEHOLDER},
}

# Known pre-existing defects in the CVA6 corpus. These requirements are flagged
# by the detector on their ORIGINAL (un-mutated) text, and the flags are GENUINE
# true positives — not false alarms. They are therefore excluded from the
# false-positive numerator when computing FPR on the clean set (counting them as
# FPs would understate the detector's clean-set precision). Documented in
# CLAUDE.md "Empirical results": PPA-50 / PPA-60 are TBD placeholders, L1W-60
# uses vague "some".
KNOWN_PREEXISTING_DEFECTS = {"PPA-50", "PPA-60", "L1W-60"}


@dataclass
class Mutation:
    """A single fault injected with an independent-lexicon term."""

    original_id: str
    original_text: str
    mutated_text: str
    fault_type: str
    injected_term: str
    description: str


def _inject(fault_type: str, text: str, term: str) -> tuple[str, str]:
    """Insert an independent term so the mutated text carries exactly one new
    smell of the target type. Returns (mutated_text, description).

    The injection strategy per type is chosen to be minimal and grammatical so
    that a detection is attributable to the injected term, not to collateral
    text. Returns the unchanged text if no suitable insertion point exists.
    """
    if fault_type == "ambiguity":
        # Append a subjective-quality clause using the independent adjective.
        return (
            text.rstrip(".") + f". The implementation shall be {term}.",
            f"Appended subjective adjective '{term}'",
        )
    if fault_type == "vagueness":
        # Append a vague-quantifier clause.
        return (
            text.rstrip(".") + f". {term.capitalize()} of the cases shall be handled.",
            f"Appended vague quantifier '{term}'",
        )
    if fault_type == "optionality":
        # Insert an escape clause after the first 'shall', else append.
        if " shall " in text:
            return (
                text.replace(" shall ", f" shall, {term}, ", 1),
                f"Inserted escape clause '{term}' after 'shall'",
            )
        return (
            text.rstrip(".") + f". This requirement applies {term}.",
            f"Appended escape clause '{term}'",
        )
    if fault_type == "comparative":
        # Append a bare comparative without baseline.
        return (
            text.rstrip(".") + f". The result shall be {term}.",
            f"Appended bare comparative '{term}'",
        )
    if fault_type == "placeholder":
        # Replace first numeric value with the spelled-out placeholder, else append.
        m = re.search(r"\b\d+(?:\.\d+)?\b", text)
        if m:
            return (
                text[: m.start()] + term + text[m.end() :],
                f"Replaced numeric '{m.group()}' with placeholder '{term}'",
            )
        return (
            text.rstrip(".") + f". Exact value {term}.",
            f"Appended placeholder '{term}'",
        )
    raise ValueError(f"unknown fault_type {fault_type!r}")


def build_mutations(requirements: list, n_per_type: int = N_PER_TYPE) -> list[Mutation]:
    """Deterministically build independent-lexicon mutations."""
    rng = random.Random(SEED)
    candidates = [r for r in requirements if len(r.text.split()) >= 8]
    mutations: list[Mutation] = []

    for fault_type, expected in EXPECTED_SMELLS.items():
        terms = independent_terms(fault_type)
        if not terms:
            continue
        # Sample requirements (with replacement across types; distinct within a
        # type) and cycle through independent terms deterministically.
        reqs = rng.sample(candidates, min(n_per_type, len(candidates)))
        term_pool = list(terms)
        rng.shuffle(term_pool)
        for i, req in enumerate(reqs):
            term = term_pool[i % len(term_pool)]
            mutated, desc = _inject(fault_type, req.text, term)
            if mutated == req.text:
                continue
            mutations.append(
                Mutation(
                    original_id=req.req_id,
                    original_text=req.text,
                    mutated_text=mutated,
                    fault_type=fault_type,
                    injected_term=term,
                    description=desc,
                )
            )
    return mutations


def _detected_types(req_id: str, text: str) -> set[SmellType]:
    return assess_requirement(req_id, text).smell_report.smell_types_found


def evaluate_recall(mutations: list[Mutation]) -> dict:
    """Per-type and overall recall over the injected mutations.

    Recall is attributed only to NEW smells: a mutation is a hit only if the
    expected smell family appears in the mutated text AND was not already present
    in the original (so collateral pre-existing smells don't inflate recall).
    """
    per_type: dict[str, dict] = {}
    details: list[dict] = []

    for mut in mutations:
        ft = mut.fault_type
        stats = per_type.setdefault(ft, {"total": 0, "hit": 0})
        stats["total"] += 1

        expected = EXPECTED_SMELLS[ft]
        orig_types = _detected_types(mut.original_id, mut.original_text)
        mut_types = _detected_types(mut.original_id + "-mut", mut.mutated_text)
        new_expected = (mut_types & expected) - orig_types
        hit = bool(new_expected)
        if hit:
            stats["hit"] += 1

        details.append(
            {
                "original_id": mut.original_id,
                "fault_type": ft,
                "injected_term": mut.injected_term,
                "description": mut.description,
                "mutated_text": mut.mutated_text,
                "expected_smell": sorted(s.value for s in expected),
                "detected_smells": sorted(s.value for s in mut_types),
                "new_expected_smells": sorted(s.value for s in new_expected),
                "hit": hit,
            }
        )

    for ft, stats in per_type.items():
        stats["recall"] = round(stats["hit"] / stats["total"], 3) if stats["total"] else 0.0

    total = sum(s["total"] for s in per_type.values())
    hits = sum(s["hit"] for s in per_type.values())
    return {
        "overall_recall": round(hits / total, 3) if total else 0.0,
        "total_mutations": total,
        "total_hits": hits,
        "per_fault_type": per_type,
        "mutation_detail": details,
    }


def evaluate_precision_and_fpr(requirements: list, mutations: list[Mutation]) -> dict:
    """Precision over (mutated ∪ clean) plus FPR on the clean set.

    Precision is per fault type: of all clean+mutated items where the detector
    raised the expected smell family, how many were actually mutated to carry it
    (true positives). A clean requirement that *already* carries that smell
    family is a true positive only if it is a known pre-existing defect;
    otherwise it counts against precision as a false positive — except we still
    exclude the documented pre-existing defects so we don't penalise genuine
    findings.

    FPR (clean set): fraction of the 64 clean requirements flagged with ANY
    smell, EXCLUDING the known pre-existing defects (PPA-50/PPA-60/L1W-60) from
    the numerator because their flags are genuine true positives.
    """
    # --- FPR on clean set ---
    clean_flagged: list[str] = []
    for req in requirements:
        if assess_requirement(req.req_id, req.text).smell_report.smell_count > 0:
            clean_flagged.append(req.req_id)
    clean_flagged_excl = [r for r in clean_flagged if r not in KNOWN_PREEXISTING_DEFECTS]
    n_clean = len(requirements)
    fpr = {
        "clean_total": n_clean,
        "clean_flagged_raw": sorted(clean_flagged),
        "excluded_known_defects": sorted(
            r for r in clean_flagged if r in KNOWN_PREEXISTING_DEFECTS
        ),
        "false_positive_requirements": sorted(clean_flagged_excl),
        "false_positive_rate": round(len(clean_flagged_excl) / n_clean, 3) if n_clean else 0.0,
        "exclusion_rule": (
            "Known pre-existing defects PPA-50, PPA-60 (TBD placeholders) and "
            "L1W-60 (vague 'some') are genuine true positives and are removed "
            "from the FP numerator."
        ),
    }

    # --- Precision per fault type over (clean ∪ mutated) ---
    precision: dict[str, dict] = {}
    for ft, expected in EXPECTED_SMELLS.items():
        muts = [m for m in mutations if m.fault_type == ft]
        tp = 0  # mutated item where expected smell newly appears
        fp = 0  # item flagged with expected smell that is NOT a genuine carrier
        # Mutated items:
        for m in muts:
            orig = _detected_types(m.original_id, m.original_text)
            new = (_detected_types(m.original_id + "-mut", m.mutated_text) & expected) - orig
            if new:
                tp += 1
        # Clean items flagged with this expected family (potential FPs):
        for req in requirements:
            flagged = _detected_types(req.req_id, req.text) & expected
            if flagged and req.req_id not in KNOWN_PREEXISTING_DEFECTS:
                fp += 1
        denom = tp + fp
        precision[ft] = {
            "true_positives": tp,
            "false_positives": fp,
            "precision": round(tp / denom, 3) if denom else None,
        }

    # Aggregate precision over all types.
    tp_all = sum(p["true_positives"] for p in precision.values())
    fp_all = sum(p["false_positives"] for p in precision.values())
    denom_all = tp_all + fp_all
    return {
        "false_positive_rate": fpr,
        "per_type_precision": precision,
        "overall_precision": round(tp_all / denom_all, 3) if denom_all else None,
    }


def evaluate_blind_mutations() -> dict | None:
    """Evaluate LLM-written blind mutations if the file exists, else None.

    Schema (list of objects): original_id, original_text, mutated_text,
    target_smell (one of ambiguity/vagueness/optionality/placeholder/
    comparative), description. Recall is reported per-type and overall, using
    the same NEW-smell attribution as the independent tier.
    """
    if not BLIND_PATH.exists():
        return None
    try:
        raw = json.loads(BLIND_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:  # pragma: no cover
        return {"error": f"could not read {BLIND_PATH.name}: {exc}"}

    # Accept either a bare list (spec schema) or a {"mutations": [...]} wrapper
    # (the concurrent agent's file adds a "_provenance" sibling key).
    if isinstance(raw, dict):
        raw = raw.get("mutations", [])
    if not isinstance(raw, list):
        return {"error": f"{BLIND_PATH.name}: expected list or {{'mutations': [...]}}"}

    per_type: dict[str, dict] = {}
    details: list[dict] = []
    for item in raw:
        ft = item.get("target_smell")
        if ft not in EXPECTED_SMELLS:
            continue
        expected = EXPECTED_SMELLS[ft]
        stats = per_type.setdefault(ft, {"total": 0, "hit": 0})
        stats["total"] += 1
        oid = item.get("original_id", "blind")
        orig = _detected_types(oid, item.get("original_text", ""))
        mut = _detected_types(oid + "-blind", item["mutated_text"])
        new = (mut & expected) - orig
        hit = bool(new)
        if hit:
            stats["hit"] += 1
        details.append(
            {
                "original_id": oid,
                "target_smell": ft,
                "mutated_text": item["mutated_text"],
                "expected_smell": sorted(s.value for s in expected),
                "detected_smells": sorted(s.value for s in mut),
                "hit": hit,
            }
        )
    for stats in per_type.values():
        stats["recall"] = round(stats["hit"] / stats["total"], 3) if stats["total"] else 0.0
    total = sum(s["total"] for s in per_type.values())
    hits = sum(s["hit"] for s in per_type.values())
    return {
        "source_file": str(BLIND_PATH),
        "overall_recall": round(hits / total, 3) if total else 0.0,
        "total_mutations": total,
        "total_hits": hits,
        "per_fault_type": per_type,
        "mutation_detail": details,
    }


def main() -> None:
    print("=" * 72)
    print("SPECGUARD — DE-CIRCULARIZED VALIDATION (independent lexicon)")
    print("=" * 72)
    requirements = get_all_requirements()
    print(f"Loaded {len(requirements)} CVA6 requirements.")
    print(f"Independent lexicon sizes (disjoint): {lexicon_sizes()}")
    print(f"Overlaps excluded from injection: {len(OVERLAP_REPORT)}")
    print()

    mutations = build_mutations(requirements)
    print(f"Built {len(mutations)} independent-lexicon mutations.")

    recall = evaluate_recall(mutations)
    print(f"Overall recall (independent): {recall['overall_recall'] * 100:.1f}%")
    for ft, s in recall["per_fault_type"].items():
        print(f"  - {ft:12s}: {s['hit']}/{s['total']} ({s['recall'] * 100:.0f}%)")
    print()

    pr = evaluate_precision_and_fpr(requirements, mutations)
    print(f"Overall precision (clean ∪ mutated): {pr['overall_precision']}")
    fpr = pr["false_positive_rate"]
    print(
        f"FPR on clean set: {fpr['false_positive_rate'] * 100:.1f}% "
        f"({len(fpr['false_positive_requirements'])}/{fpr['clean_total']}, "
        f"excluding {fpr['excluded_known_defects']})"
    )
    print()

    blind = evaluate_blind_mutations()
    if blind is None:
        print(f"Blind-mutation tier: SKIPPED (no {BLIND_PATH} found).")
    elif "error" in blind:
        print(f"Blind-mutation tier: ERROR — {blind['error']}")
    else:
        print(
            f"Blind-mutation tier: overall recall "
            f"{blind['overall_recall'] * 100:.1f}% over {blind['total_mutations']} mutations."
        )
        for ft, s in blind["per_fault_type"].items():
            print(f"  - {ft:12s}: {s['hit']}/{s['total']} ({s['recall'] * 100:.0f}%)")
    print()

    payload = {
        "experiment": "seeded_faults_independent",
        "description": (
            "Method-level validation using an INDEPENDENT lexicon disjoint from "
            "the detector's own lexicons. Recall < 100% is expected and is "
            "evidence of closed-lexicon coverage limits, not a bug."
        ),
        "seed": SEED,
        "independent_lexicon_sizes": lexicon_sizes(),
        "overlaps_excluded": OVERLAP_REPORT,
        "placeholder_closed_vocab_note": PLACEHOLDER_CLOSED_VOCAB_NOTE,
        "independent_tier": {
            "recall": {k: v for k, v in recall.items() if k != "mutation_detail"},
            "precision_and_fpr": pr,
            "mutation_detail": recall["mutation_detail"],
        },
        "blind_mutations": blind,
    }
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Results written to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
