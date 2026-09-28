"""Assessment profiles: how the vendored SpecGuard core is applied to spec.md.

``default``
    The SpecGuard core exactly as calibrated on CVA6 (aerospace/hardware
    register). Kept for comparison and for teams that want the strict lexicon.

``speckit`` (extension default)
    The same detectors and gate thresholds, plus register rules for Spec Kit's
    product-spec idiom. Every rule is itemized with its corpus evidence in
    docs/checks.md; none changes a detector, they filter individual hits or
    change how Success Criteria are scored:

    P1  counts of discrete entities are unit-less ("up to 10 stories",
        "1,000 concurrent users") -> MISSING_UNIT hit dropped
    P2  'any' is the universal / negative-polarity quantifier ("reject any
        expired code") -> VAGUENESS hit dropped
    P4  'different' denotes distinctness ("a different repository")
        -> VAGUENESS hit dropped
    NC  an open ``[NEEDS CLARIFICATION: ...]`` inside a requirement is a
        PLACEHOLDER hit (Spec Kit's institutionalized TBD)
    P3  Success Criteria are outcome statements, modal-free by Spec Kit
        design: the completeness modal bonus is granted, and verifiability
        is driven by an explicit measurability class (QUANTIFIED / BINARY /
        UNMEASURED) instead of modal strength.

Register-independent detector bugs are NOT handled here — they are fixed in
the SpecGuard core (pilot G1-G5, in-the-wild corpus G6-G9) and vendored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._vendor.specguard_core.quality_scorer import (
    SEVERITY_WEIGHTS,
    SMELL_AFFECTS_COMPLETENESS,
    SMELL_AFFECTS_VERIFIABILITY,
    QualityScores,
    compute_consistency,
)
from ._vendor.specguard_core.smell_detector import SmellHit, SmellReport, SmellType

PROFILES = ("speckit", "default")

QUANTIFIED = "QUANTIFIED"
BINARY = "BINARY"
UNMEASURED = "UNMEASURED"

# Verifiability base per measurability class (P3). Chosen so that, with the
# core weights and no smells, QUANTIFIED -> ~0.97 PASS, BINARY -> ~0.90 PASS,
# UNMEASURED -> 0.70 WARN; one medium smell keeps BINARY at PASS (0.77) and
# pushes UNMEASURED further into WARN.
SC_VERIFIABILITY_BASE = {QUANTIFIED: 1.0, BINARY: 0.85, UNMEASURED: 0.4}

# Mirrors the core's inline constants in quality_scorer.score_requirement /
# compute_completeness (lock-step is enforced by tests/test_profile.py).
OVERALL_WEIGHTS = (0.30, 0.25, 0.45)
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,}\b")

# A count of discrete entities: number, up to three modifiers (not function
# words), plural noun — "10 stories", "1,000 concurrent redirect requests".
_MODIFIER = r"(?:(?!(?:on|in|at|for|to|from|with|by|and|or|of|the|a|an|per|when|if)\b)[a-z-]+\s+)"
COUNT_TAIL = r"\s+" + _MODIFIER + r"{0,3}[a-z]+(?:s|ren)\b"
ENTITY_COUNT_RE = re.compile(r"[\d,.]+" + COUNT_TAIL, re.IGNORECASE)
# "top 5 endpoints" is a rank cut-off (a selection), not an outcome magnitude.
RANK_PREFIX = r"(?<!\btop )(?<!\bfirst )(?<!\blast )(?<!\bbottom )"

TIME_UNITS = (
    r"(?:ms|milliseconds?|s|secs?|seconds?|mins?|minutes?|h|hrs?|hours?|"
    r"days?|weeks?|months?|years?)"
)
SIZE_UNITS = r"(?:bytes?|kb|mb|gb|tb|kib|mib|gib|tib)"
RATE_UNITS = r"(?:rps|qps|tps|fps|hz|khz|mhz|ghz|req/s|requests?/s)"
QUANTIFIED_RES = (
    re.compile(r"\d+(?:\.\d+)?\s*%"),
    re.compile(rf"\b\d[\d,.]*\s*(?:{TIME_UNITS}|{SIZE_UNITS}|{RATE_UNITS})\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?x\b", re.IGNORECASE),
    re.compile(
        r"\b(?:under|within|up to|at least|at most|no more than|no fewer than|fewer than|"
        r"less than|more than|greater than|exactly|below|above|maximum of|minimum of)\s+\d",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d+\s*(?:/|of|out of)\s*\d+\b", re.IGNORECASE),
    re.compile(RANK_PREFIX + r"\b\d[\d,]*" + COUNT_TAIL, re.IGNORECASE),
)
# Deterministic predicates: an absolute condition a test run either meets or not.
BINARY_RE = re.compile(
    r"\b(?:every|all|each|no|none|never|always|zero|identical|byte-identical|"
    r"byte-for-byte|exactly|same|unchanged)\b"
    r"|\bexits?\s+(?:with\s+)?(?:code\s+|status\s+)?\d"
    r"|\bnon-zero\b|\bpass(?:es)?\b|\bfails?\b|\breject(?:s|ed)?\b|\bmatch(?:es)?\b"
    r"|\bsucceeds?\b|\bgreen\b",
    re.IGNORECASE,
)


@dataclass
class Suppression:
    hit: SmellHit
    rule: str


def measurability_class(text: str) -> str:
    """QUANTIFIED (metric present) / BINARY (absolute predicate) / UNMEASURED."""
    if any(p.search(text) for p in QUANTIFIED_RES):
        return QUANTIFIED
    if BINARY_RE.search(text):
        return BINARY
    return UNMEASURED


def filter_hits(
    hits: list[SmellHit], text: str, profile: str
) -> tuple[list[SmellHit], list[Suppression]]:
    """Apply the profile's hit-level register rules (P1, P2, P4)."""
    if profile != "speckit":
        return list(hits), []
    kept: list[SmellHit] = []
    dropped: list[Suppression] = []
    for hit in hits:
        rule = _register_rule(hit, text)
        if rule:
            dropped.append(Suppression(hit=hit, rule=rule))
        else:
            kept.append(hit)
    return kept, dropped


def _register_rule(hit: SmellHit, text: str) -> str | None:
    trigger = hit.trigger.lower()
    if hit.smell_type == SmellType.MISSING_UNIT and ENTITY_COUNT_RE.match(text, hit.position):
        return "P1"
    if hit.smell_type == SmellType.VAGUENESS and trigger == "any":
        return "P2"
    if hit.smell_type == SmellType.VAGUENESS and trigger == "different":
        return "P4"
    return None


def clarification_hits(markers: list[str]) -> list[SmellHit]:
    """NC: one high-severity PLACEHOLDER hit per open clarification marker."""
    return [
        SmellHit(
            smell_type=SmellType.PLACEHOLDER,
            trigger="NEEDS CLARIFICATION",
            position=0,
            severity="high",
            explanation=(
                f"Open clarification: '{q}'. Resolve it (e.g. with /speckit.clarify) "
                "before planning."
            ),
        )
        for q in markers
    ]


def combine(completeness: float, consistency: float, verifiability: float) -> float:
    wc, ws, wv = OVERALL_WEIGHTS
    return round(wc * completeness + ws * consistency + wv * verifiability, 3)


def score_outcome(text: str, report: SmellReport, sc_class: str) -> QualityScores:
    """P3: score a Success Criterion in the outcome register.

    Structure mirrors the core ``score_requirement``; only two terms differ:
    the modal bonus in completeness is granted (modal-free SCs are correct
    Spec Kit style) and the verifiability base comes from the measurability
    class instead of measurable-pattern + modal strength.
    """
    v = SC_VERIFIABILITY_BASE[sc_class]
    v -= sum(
        SEVERITY_WEIGHTS[h.severity]
        for h in report.hits
        if h.smell_type in SMELL_AFFECTS_VERIFIABILITY
    )
    verifiability = round(max(0.0, min(1.0, v)), 3)

    c = 0.9 + (0.1 if ACRONYM_RE.search(text) else 0.0)
    c -= sum(
        SEVERITY_WEIGHTS[h.severity] * 1.5
        for h in report.hits
        if h.smell_type == SmellType.PLACEHOLDER
    )
    c -= sum(
        SEVERITY_WEIGHTS[h.severity]
        for h in report.hits
        if h.smell_type in SMELL_AFFECTS_COMPLETENESS
    )
    completeness = round(max(0.0, min(1.0, c)), 3)

    consistency = compute_consistency(text, report)
    return QualityScores(
        requirement_id=report.requirement_id,
        completeness=completeness,
        consistency=consistency,
        verifiability=verifiability,
        overall=combine(completeness, consistency, verifiability),
    )
