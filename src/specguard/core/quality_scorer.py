"""Requirements Quality Scoring.

Computes quantitative quality scores for requirements based on:

- Smell density (smell count per token)
- Severity-weighted smell impact
- Verifiability indicators (presence of measurable criteria)
- Length / structural metrics

Scoring rationale follows:
- Zakeri-Nasrabadi et al. (2024). "Natural language requirements testability
  measurement based on requirement smells". Neural Computing and Applications.
- ISO/IEC/IEEE 29148:2018 quality characteristics.

The output is three normalized scores in [0, 1]:
- completeness_score: presence of mandatory structural elements
- consistency_score: absence of self-contradictory patterns (limited at single-req level)
- verifiability_score: presence of measurable criteria, absence of subjective terms

These map directly to the dissertation's three quality criteria, which in turn
align with DO-178C Table A-3 objectives 1-7 and DO-254 requirements capture
objectives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .smell_detector import SmellReport, SmellType

# Severity weights for smell impact on quality scores
SEVERITY_WEIGHTS = {
    "low": 0.1,
    "medium": 0.3,
    "high": 0.6,
}

# Smell-to-criterion mapping — which smells affect which quality criterion
# (based on the linguistic analysis in Zakeri-Nasrabadi et al. 2024)
SMELL_AFFECTS_VERIFIABILITY = {
    SmellType.AMBIGUITY,
    SmellType.VAGUENESS,
    SmellType.SUBJECTIVITY,
    SmellType.COMPARATIVE,
    SmellType.MISSING_UNIT,
}

SMELL_AFFECTS_COMPLETENESS = {
    SmellType.PLACEHOLDER,
    SmellType.IMPLICIT_REFERENCE,
    SmellType.OPTIONALITY,
}

# Modal verbs indicating commitment level
MANDATORY_MODALS = {"shall", "must", "will"}
RECOMMENDED_MODALS = {"should"}
OPTIONAL_MODALS = {"may", "can", "could", "might"}

# Indicators of measurable / verifiable criteria
MEASURABLE_PATTERNS = [
    re.compile(r"\b\d+\s*(?:kbyte|kbytes|mbyte|mbytes|byte|bytes|bit|bits)\b", re.I),
    re.compile(r"\b\d+\s*(?:hz|khz|mhz|ghz|hertz)\b", re.I),
    re.compile(r"\b\d+\s*(?:ns|us|ms|s|sec|seconds?|cycles?)\b", re.I),
    re.compile(r"\b\d+\s*(?:way|ways|kb|mb|gb)\b", re.I),
    re.compile(r"\b\d+\s*(?:%|percent)\b", re.I),
    re.compile(r"\bversion\s+\d+(?:\.\d+)*\b", re.I),
    re.compile(r"\b(?:less than|more than|at least|at most|equal to|greater than)\b", re.I),
]


@dataclass
class QualityScores:
    """Quality scores for a single requirement, in [0, 1]."""

    requirement_id: str
    completeness: float
    consistency: float
    verifiability: float
    overall: float

    @property
    def gate_decision(self) -> str:
        """Gate-decision for SDD pipeline: PASS / WARN / FAIL.

        - PASS: ready for downstream formalization
        - WARN: usable but with documented quality concerns
        - FAIL: must be revised before progression
        """
        if self.overall >= 0.75:
            return "PASS"
        if self.overall >= 0.50:
            return "WARN"
        return "FAIL"


def _count_tokens(text: str) -> int:
    """Approximate token count using whitespace split."""
    return max(1, len(text.split()))


def _has_measurable_criterion(text: str) -> bool:
    """Check whether text contains at least one quantitative criterion."""
    return any(p.search(text) for p in MEASURABLE_PATTERNS)


def _modal_strength(text: str) -> float:
    """Compute commitment strength based on modal verbs.

    Returns value in [0, 1] where 1.0 = strong mandatory, 0.0 = no modal at all.
    """
    text_lower = " " + text.lower() + " "
    if any(f" {m} " in text_lower for m in MANDATORY_MODALS):
        return 1.0
    if any(f" {m} " in text_lower for m in RECOMMENDED_MODALS):
        return 0.6
    if any(f" {m} " in text_lower for m in OPTIONAL_MODALS):
        return 0.3
    return 0.0


def compute_verifiability(text: str, report: SmellReport) -> float:
    """Verifiability score in [0, 1].

    High verifiability requires:
    - Presence of measurable criteria
    - Absence of subjective/ambiguous terminology
    - Strong modal commitment
    """
    base = 0.5

    # Measurable criteria boost
    if _has_measurable_criterion(text):
        base += 0.3

    # Modal commitment boost
    base += 0.2 * _modal_strength(text)

    # Smell penalty
    penalty = 0.0
    for hit in report.hits:
        if hit.smell_type in SMELL_AFFECTS_VERIFIABILITY:
            penalty += SEVERITY_WEIGHTS[hit.severity]

    score = max(0.0, min(1.0, base - penalty))
    return round(score, 3)


def compute_completeness(text: str, report: SmellReport) -> float:
    """Completeness score in [0, 1].

    Heuristic at single-requirement level. Real completeness checking
    requires inter-requirement analysis (planned for graph layer).
    """
    base = 0.7

    # Modal verb required for clear commitment
    if _modal_strength(text) > 0:
        base += 0.2

    # Subject reference: requirement should mention the subject explicitly
    # (CVA6, L1WTD, L1I, etc — capitalized identifier or known acronym)
    if re.search(r"\b[A-Z][A-Z0-9]{2,}\b", text):
        base += 0.1

    # Heavy penalty for placeholders
    placeholder_penalty = sum(
        SEVERITY_WEIGHTS[hit.severity] * 1.5  # extra weight for placeholders
        for hit in report.hits
        if hit.smell_type == SmellType.PLACEHOLDER
    )

    # Penalty for completeness-affecting smells
    smell_penalty = sum(
        SEVERITY_WEIGHTS[hit.severity]
        for hit in report.hits
        if hit.smell_type in SMELL_AFFECTS_COMPLETENESS
    )

    score = max(0.0, min(1.0, base - placeholder_penalty - smell_penalty))
    return round(score, 3)


def compute_consistency(text: str, report: SmellReport) -> float:
    """Consistency score in [0, 1].

    Single-requirement level: looks for internal contradictions like
    'shall be both A and not A'. Cross-requirement consistency is left
    for the graph layer.
    """
    base = 1.0

    # Detect internal contradictions: presence of both 'shall' and 'shall not'
    has_positive_modal = bool(re.search(r"\bshall\b(?!\s*not)", text, re.I))
    has_negative_modal = bool(re.search(r"\bshall\s+not\b", text, re.I))

    if has_positive_modal and has_negative_modal:
        # This is rare but, when it happens within a single requirement,
        # it usually signals confusion. We leave a soft penalty.
        base -= 0.2

    # Detect mixed modal strength within same requirement (shall + may)
    has_strong = any(re.search(rf"\b{m}\b", text, re.I) for m in MANDATORY_MODALS)
    has_weak = any(re.search(rf"\b{m}\b", text, re.I) for m in OPTIONAL_MODALS)
    if has_strong and has_weak:
        base -= 0.15

    return round(max(0.0, min(1.0, base)), 3)


def score_requirement(text: str, report: SmellReport) -> QualityScores:
    """Compute all quality scores for a requirement."""
    completeness = compute_completeness(text, report)
    consistency = compute_consistency(text, report)
    verifiability = compute_verifiability(text, report)

    # Weighted overall score — verifiability is most important for safety-critical
    overall = round(
        0.30 * completeness + 0.25 * consistency + 0.45 * verifiability,
        3,
    )

    return QualityScores(
        requirement_id=report.requirement_id,
        completeness=completeness,
        consistency=consistency,
        verifiability=verifiability,
        overall=overall,
    )
