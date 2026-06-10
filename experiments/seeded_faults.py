"""Seeded Faults Experiment — IMPLEMENTATION SANITY CHECK (not method validation).

WARNING — read before citing the recall number from this experiment.

This experiment injects faults using the detector's OWN lexicon vocabulary
(``inject_ambiguity`` inserts "appropriate"/"fast"/"user-friendly", etc. — words
that literally live in ``smell_detector.AMBIGUITY_TERMS``). Consequently the
reported ~100% recall is true *by construction*: any lexicon-based detector
attains perfect recall against faults drawn from its own lexicon. This validates
that the detection *implementation* fires end-to-end (the pipeline wiring,
mutation harness, and reporting work), NOT that the detection *method*
generalises.

Method-level (de-circularized) validation lives in
``experiments/seeded_faults_independent.py``, which injects faults using an
INDEPENDENT lexicon — terms from published literature (INCOSE GtWR, Femmer 2017,
Berry & Kamsties, ISO 29148) programmatically verified disjoint from the
detector's lexicons. Recall there is below 100% and is the credible, publishable
measure of lexicon coverage.

Keep this script as a fast regression sanity check; do NOT report its recall as
evidence of method quality in Paper #3.

Methodology reference:
- Zakeri-Nasrabadi et al. (2024). "Natural language requirements testability
  measurement based on requirement smells"
- Veizaga et al. (2023). "Automated Smell Detection and Recommendation"
  used similar mutation-style validation
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from specguard import assess_requirement
from specguard.core.smell_detector import SmellType
from specguard.data.cva6_requirements import get_all_requirements


@dataclass
class SeededFault:
    """A single fault injected into a clean requirement."""

    original_id: str
    original_text: str
    mutated_text: str
    fault_type: SmellType
    fault_description: str


# Set seed for reproducibility
random.seed(42)


def inject_ambiguity(text: str) -> tuple[str, str]:
    """Replace specific term with subjective adjective."""
    replacements = [
        ("upper-bounded", "appropriate"),
        ("compile-time", "fast"),
        ("64-bit", "efficient"),
        ("32-bit", "reasonable"),
        ("single-precision", "user-friendly"),
        ("double-precision", "robust"),
        ("worst case", "modern"),
        ("predictability", "smoothness"),
    ]
    for original, replacement in replacements:
        if original in text:
            mutated = text.replace(original, replacement, 1)
            return mutated, f"Replaced '{original}' with subjective '{replacement}'"
    # Fallback — just append vague qualifier
    return text + " The implementation should be efficient.", "Added subjective sentence"


def inject_vagueness(text: str) -> tuple[str, str]:
    """Replace specific quantifiers with imprecise ones.

    Uses word-boundary regex to avoid substring matches like 'all' inside 'shall'.
    """
    import re

    if re.search(r"\bsix\b", text):
        mutated = re.sub(r"\bsix\b", "several", text, count=1)
        return mutated, "Replaced 'six' with 'several'"
    if re.search(r"\b(64-bit|32-bit)\b", text):
        mutated = re.sub(r"\b(64-bit|32-bit)\b", "many", text, count=1)
        return mutated, "Replaced bit-width with 'many'"
    if re.search(r"\bone\b", text):
        mutated = re.sub(r"\bone\b", "some", text, count=1)
        return mutated, "Replaced 'one' with 'some'"
    if "shall " in text:
        return (
            text.replace("shall ", "shall typically ", 1),
            "Inserted vague 'typically' after shall",
        )
    return text + " There may be some additional considerations.", "Added vague sentence"


def inject_optionality(text: str) -> tuple[str, str]:
    """Add weak escape-hatch phrasing."""
    if " shall " in text:
        mutated = text.replace(" shall ", " shall, where applicable, ", 1)
        return mutated, "Added 'where applicable' escape hatch"
    return text + " This requirement applies if needed.", "Added 'if needed' escape clause"


def inject_placeholder(text: str) -> tuple[str, str]:
    """Replace specific value with TBD placeholder."""
    # Find first numeric value and replace
    import re

    match = re.search(r"\b\d+(?:\.\d+)?\b", text)
    if match:
        mutated = text[: match.start()] + "TBD" + text[match.end() :]
        return mutated, f"Replaced numeric value '{match.group()}' with 'TBD'"
    return text + " (TBD: exact value to be determined.)", "Added TBD placeholder"


def inject_comparative(text: str) -> tuple[str, str]:
    """Add bare comparative without baseline."""
    if " shall " in text:
        mutated = text.replace(" shall ", " shall be faster and ", 1)
        return mutated, "Added bare comparative 'faster'"
    return text + " The implementation should be more efficient.", "Added bare comparative"


# Map fault types to injectors
INJECTORS = {
    SmellType.AMBIGUITY: inject_ambiguity,
    SmellType.VAGUENESS: inject_vagueness,
    SmellType.OPTIONALITY: inject_optionality,
    SmellType.PLACEHOLDER: inject_placeholder,
    SmellType.COMPARATIVE: inject_comparative,
}


def create_faulty_dataset(
    requirements: list,
    n_faults_per_type: int = 10,
    seed: int = 42,
) -> list[SeededFault]:
    """Create a controlled dataset of seeded faults."""
    random.seed(seed)

    # Filter to requirements long enough to mutate meaningfully
    candidates = [r for r in requirements if len(r.text.split()) >= 8]

    seeded = []
    for fault_type, injector in INJECTORS.items():
        # Sample distinct requirements for each fault type
        sample = random.sample(candidates, min(n_faults_per_type, len(candidates)))
        for req in sample:
            mutated_text, description = injector(req.text)
            if mutated_text != req.text:  # only keep actual mutations
                seeded.append(
                    SeededFault(
                        original_id=req.req_id,
                        original_text=req.text,
                        mutated_text=mutated_text,
                        fault_type=fault_type,
                        fault_description=description,
                    )
                )

    return seeded


def evaluate_detection(faults: list[SeededFault]) -> dict:
    """Evaluate SpecGuard's detection of seeded faults.

    For each seeded fault, check if SpecGuard detects the expected smell type.
    Computes precision and recall per fault type.
    """
    per_type_stats: dict = {}

    for fault in faults:
        ftype = fault.fault_type.value
        if ftype not in per_type_stats:
            per_type_stats[ftype] = {
                "total": 0,
                "detected": 0,
                "examples_caught": [],
                "examples_missed": [],
            }

        per_type_stats[ftype]["total"] += 1

        # Run SpecGuard on the mutated text
        result = assess_requirement(fault.original_id + "-mutated", fault.mutated_text)

        # Did SpecGuard detect the expected smell type?
        detected_types = result.smell_report.smell_types_found
        if fault.fault_type in detected_types:
            per_type_stats[ftype]["detected"] += 1
            if len(per_type_stats[ftype]["examples_caught"]) < 2:
                per_type_stats[ftype]["examples_caught"].append(
                    {
                        "id": fault.original_id,
                        "mutation": fault.fault_description,
                        "mutated_text": fault.mutated_text[:120],
                    }
                )
        else:
            if len(per_type_stats[ftype]["examples_missed"]) < 2:
                per_type_stats[ftype]["examples_missed"].append(
                    {
                        "id": fault.original_id,
                        "mutation": fault.fault_description,
                        "mutated_text": fault.mutated_text[:120],
                    }
                )

    # Compute recall per type
    for _ftype, stats in per_type_stats.items():
        stats["recall"] = round(stats["detected"] / stats["total"], 3) if stats["total"] else 0.0

    # Aggregate
    total_faults = sum(s["total"] for s in per_type_stats.values())
    total_detected = sum(s["detected"] for s in per_type_stats.values())
    overall_recall = round(total_detected / total_faults, 3) if total_faults else 0.0

    return {
        "total_faults_injected": total_faults,
        "total_faults_detected": total_detected,
        "overall_recall": overall_recall,
        "per_fault_type": per_type_stats,
    }


def evaluate_false_positive_rate(requirements: list) -> dict:
    """Run SpecGuard on clean (un-mutated) requirements to estimate
    false-positive rate baseline."""

    n_clean = len(requirements)
    n_with_smells = 0
    smell_types_in_clean: dict = {}

    for req in requirements:
        result = assess_requirement(req.req_id, req.text)
        if result.smell_report.smell_count > 0:
            n_with_smells += 1
            for hit in result.smell_report.hits:
                key = hit.smell_type.value
                smell_types_in_clean[key] = smell_types_in_clean.get(key, 0) + 1

    return {
        "clean_requirements_total": n_clean,
        "clean_requirements_flagged": n_with_smells,
        "clean_flag_rate": round(n_with_smells / n_clean, 3),
        "smells_in_clean_set": smell_types_in_clean,
    }


def main() -> None:
    """Run the full validation experiment."""
    print("=" * 70)
    print("SPECGUARD VALIDATION EXPERIMENT")
    print("=" * 70)
    print()

    requirements = get_all_requirements()
    print(f"Loaded {len(requirements)} requirements from CVA6 specification.")
    print()

    # Step 1: false positive rate on clean dataset
    print("Step 1: Analyzing clean requirements (false-positive baseline)...")
    fp_results = evaluate_false_positive_rate(requirements)
    print(
        f"  → {fp_results['clean_requirements_flagged']}/{fp_results['clean_requirements_total']} "
        f"clean requirements flagged ({fp_results['clean_flag_rate']*100:.1f}%)"
    )
    print(f"  → Smells found in clean set: {fp_results['smells_in_clean_set']}")
    print()

    # Step 2: seed faults
    print("Step 2: Creating seeded fault dataset...")
    faults = create_faulty_dataset(requirements, n_faults_per_type=10)
    print(f"  → Created {len(faults)} faults across {len(INJECTORS)} fault types.")
    print()

    # Step 3: evaluate detection
    print("Step 3: Evaluating SpecGuard detection on seeded faults...")
    eval_results = evaluate_detection(faults)
    print(f"  → Overall recall: {eval_results['overall_recall']*100:.1f}%")
    print()
    print("Per-fault-type recall:")
    for ftype, stats in eval_results["per_fault_type"].items():
        print(
            f"  - {ftype:20s}: {stats['detected']}/{stats['total']} "
            f"({stats['recall']*100:.0f}% recall)"
        )
    print()

    # Save full results
    output_path = Path(__file__).parent.parent / "results" / "experiment_results.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "false_positive_baseline": fp_results,
                "seeded_fault_evaluation": eval_results,
                "n_faults": len(faults),
            },
            f,
            indent=2,
        )
    print(f"Detailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
