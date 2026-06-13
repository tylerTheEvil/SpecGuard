"""SpecGuard Pipeline.

Orchestrates the full quality assessment pipeline:

    Requirements → Smell Detection → Quality Scoring → Gate Decision

This is the canonical entry point used by notebooks and experiments.
The pipeline is deterministic — same input always produces same output.
This is a deliberate design choice that distinguishes SpecGuard from
ad-hoc LLM prompting: results are reproducible and auditable, which is
required for DO-178C / DO-254 tool qualification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .quality_scorer import QualityScores, score_requirement
from .smell_detector import SmellReport, analyze_requirement


@dataclass
class AssessmentResult:
    """Complete assessment result for a single requirement."""

    requirement_id: str
    requirement_text: str
    smell_report: SmellReport
    quality_scores: QualityScores
    metadata: dict = field(default_factory=dict)

    @property
    def gate_decision(self) -> str:
        return self.quality_scores.gate_decision

    def summary(self) -> str:
        """Human-readable summary line."""
        return (
            f"{self.requirement_id}: "
            f"overall={self.quality_scores.overall:.2f} "
            f"(C={self.quality_scores.completeness:.2f}, "
            f"S={self.quality_scores.consistency:.2f}, "
            f"V={self.quality_scores.verifiability:.2f}) "
            f"smells={self.smell_report.smell_count} "
            f"→ {self.gate_decision}"
        )


def assess_requirement(req_id: str, text: str, metadata: dict | None = None) -> AssessmentResult:
    """Run the complete pipeline on a single requirement.

    Args:
        req_id: Requirement identifier (e.g., "L1W-10")
        text: Natural language requirement text
        metadata: Optional metadata (category, safety-critical flag, etc.)

    Returns:
        AssessmentResult with smell report, quality scores, and gate decision.
    """
    smell_report = analyze_requirement(req_id, text)
    quality_scores = score_requirement(text, smell_report)
    return AssessmentResult(
        requirement_id=req_id,
        requirement_text=text,
        smell_report=smell_report,
        quality_scores=quality_scores,
        metadata=metadata or {},
    )


def assess_dataset(requirements: list) -> list[AssessmentResult]:
    """Run the complete pipeline on a list of Requirement objects."""
    results = []
    for req in requirements:
        metadata = {
            "category": req.category,
            "safety_critical_context": req.safety_critical_context,
            "parent_section": req.parent_section,
        }
        result = assess_requirement(req.req_id, req.text, metadata=metadata)
        results.append(result)
    return results


def aggregate_metrics(results: list[AssessmentResult]) -> dict:
    """Compute dataset-level aggregate metrics."""
    if not results:
        return {}

    n = len(results)
    pass_count = sum(1 for r in results if r.gate_decision == "PASS")
    warn_count = sum(1 for r in results if r.gate_decision == "WARN")
    fail_count = sum(1 for r in results if r.gate_decision == "FAIL")

    avg_completeness = sum(r.quality_scores.completeness for r in results) / n
    avg_consistency = sum(r.quality_scores.consistency for r in results) / n
    avg_verifiability = sum(r.quality_scores.verifiability for r in results) / n
    avg_overall = sum(r.quality_scores.overall for r in results) / n

    total_smells = sum(r.smell_report.smell_count for r in results)
    smells_per_req = total_smells / n

    # Smells by type across the dataset
    smell_type_counts: dict[str, int] = {}
    for r in results:
        for hit in r.smell_report.hits:
            key = hit.smell_type.value
            smell_type_counts[key] = smell_type_counts.get(key, 0) + 1

    return {
        "total_requirements": n,
        "gate_pass": pass_count,
        "gate_warn": warn_count,
        "gate_fail": fail_count,
        "pass_rate": round(pass_count / n, 3),
        "fail_rate": round(fail_count / n, 3),
        "avg_completeness": round(avg_completeness, 3),
        "avg_consistency": round(avg_consistency, 3),
        "avg_verifiability": round(avg_verifiability, 3),
        "avg_overall": round(avg_overall, 3),
        "total_smells_detected": total_smells,
        "smells_per_requirement": round(smells_per_req, 2),
        "smell_type_distribution": smell_type_counts,
    }
