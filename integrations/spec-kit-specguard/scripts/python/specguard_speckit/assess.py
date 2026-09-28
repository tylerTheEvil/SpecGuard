"""Per-requirement Layer-1 assessment: vendored core + profile."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._vendor.specguard_core.quality_scorer import QualityScores, score_requirement
from ._vendor.specguard_core.smell_detector import SmellHit, SmellReport, analyze_requirement
from .model import Requirement
from .profile import (
    Suppression,
    clarification_hits,
    filter_hits,
    measurability_class,
    score_outcome,
)

OUTCOME_KINDS = ("SC",)


@dataclass
class RequirementResult:
    requirement: Requirement
    hits: list[SmellHit]
    scores: QualityScores
    sc_class: str | None = None
    suppressed: list[Suppression] = field(default_factory=list)

    @property
    def gate(self) -> str:
        return self.scores.gate_decision


def assess_requirement(req: Requirement, profile: str = "speckit") -> RequirementResult:
    """Detect smells, apply the profile, score, and gate one requirement.

    Deterministic: the same requirement text and profile always produce the
    same result. No model is consulted.
    """
    core = analyze_requirement(req.req_id, req.text)
    kept, suppressed = filter_hits(core.hits, req.text, profile)
    if profile == "speckit":
        kept = clarification_hits(req.markers) + kept
    report = SmellReport(requirement_id=req.req_id, requirement_text=req.text, hits=kept)

    sc_class = None
    if profile == "speckit" and req.kind in OUTCOME_KINDS:
        sc_class = measurability_class(req.text)
        scores = score_outcome(req.text, report, sc_class)
    else:
        scores = score_requirement(req.text, report)
    return RequirementResult(
        requirement=req, hits=kept, scores=scores, sc_class=sc_class, suppressed=suppressed
    )


def assess_all(
    requirements: list[Requirement], profile: str = "speckit", kinds: tuple[str, ...] | None = None
) -> list[RequirementResult]:
    return [
        assess_requirement(r, profile)
        for r in requirements
        if kinds is None or r.kind in kinds
    ]
