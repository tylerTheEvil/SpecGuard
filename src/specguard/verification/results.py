"""Verdict and freshness are separate: stale evidence never erases a violation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


@dataclass
class CheckResult:
    rule_id: str
    objects: list[str]
    status: CheckStatus
    reason: str
    applicability: str = "Applicability not established"
    scope: str = "undeclared"
    evidence: list[str] = field(default_factory=list)
    missing_prerequisites: list[str] = field(default_factory=list)
    dependency_versions: dict[str, str] = field(default_factory=dict)
    freshness: str = "CURRENT"
    details: dict[str, Any] = field(default_factory=dict)
    limits: list[str] = field(
        default_factory=lambda: [
            "Project check only; no claim of system safety or whole-standard compliance."
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize(results: list[CheckResult]) -> dict[str, Any]:
    expected = sum(max(1, r.details.get("unexamined_checks", 1)) for r in results)
    scope_known = not any(r.details.get("scope_unknown") for r in results)
    counts = {s.value: sum(r.status == s for r in results) for s in CheckStatus}
    # Historical PASS is visible, but does not count as a current completed check.
    completed = sum(
        r.status in (CheckStatus.PASS, CheckStatus.FAIL) and r.freshness == "CURRENT"
        for r in results
    )
    passing = sum(r.status == CheckStatus.PASS and r.freshness == "CURRENT" for r in results)
    stale = sum(r.freshness == "STALE" for r in results)
    unknown_freshness = sum(r.freshness == "UNKNOWN" for r in results)
    status = next(
        (s for s in (CheckStatus.FAIL, CheckStatus.ERROR, CheckStatus.UNKNOWN) if counts[s]),
        CheckStatus.PASS,
    )
    if status == CheckStatus.PASS and (stale or unknown_freshness or not results):
        status = CheckStatus.UNKNOWN
    elif results and counts["NOT_APPLICABLE"] == len(results):
        status = CheckStatus.NOT_APPLICABLE
    return {
        "status": status,
        "counts": counts,
        "stale": stale,
        "freshness_unknown": unknown_freshness,
        "expected_checks": expected,
        "expected_scope_complete": scope_known,
        "completed_applicable_checks": completed,
        "pass_fraction_completed": passing / completed if completed else None,
        "completion_coverage": completed / expected if expected and scope_known else None,
        "incomplete": bool(
            counts["UNKNOWN"]
            or counts["ERROR"]
            or stale
            or unknown_freshness
            or not results
            or any(r.missing_prerequisites for r in results)
        ),
    }
