"""Structural checks codified from Spec Kit's own specification rules.

Source: ``templates/commands/specify.md`` ("Specification Quality Checklist",
"Success Criteria Guidelines") and ``templates/spec-template.md`` (mandatory
sections, placeholders), pinned spec-kit commit c00dc05. Spec Kit asks the
generating LLM to self-check these items; here the mechanically checkable
subset is enforced deterministically. Items that need judgment are listed in
:data:`NOT_CHECKED` and reported as such — never silently implied.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .assess import RequirementResult
from .model import Finding, SpecDocument
from .profile import BINARY, UNMEASURED

MANDATORY_SECTIONS = (
    ("User Scenarios & Testing", re.compile(r"\buser (?:scenarios|stories)\b", re.I)),
    ("Requirements", re.compile(r"\brequirements\b", re.I)),
    ("Success Criteria", re.compile(r"\bsuccess criteria\b", re.I)),
)
EDGE_CASES_RE = re.compile(r"\bedge cases?\b", re.I)
NORMATIVE_RE = re.compile(r"\b(?:must|shall|should|may|will)\b|\brequired to\b", re.I)

CHECKS = {
    "SK-001": ("error", "Open [NEEDS CLARIFICATION: ...] marker"),
    "SK-002": ("error", "Unfilled spec-template placeholder"),
    "SK-003": ("error", "Mandatory section missing"),
    "SK-004": ("error", "Duplicate requirement ID"),
    "SK-005": ("error", "No functional requirement found"),
    "SK-006": ("warn", "User story without priority"),
    "SK-007": ("warn", "User story without a Given/When/Then acceptance scenario"),
    "SK-008": ("warn", "Requirement without a normative keyword"),
    "SK-009": ("warn", "Success criterion without a measurable outcome"),
    "SK-010": ("info", "Success criterion is a binary predicate without a metric"),
    "SK-011": ("info", "No Edge Cases section"),
    "SK-012": ("info", "Gap in requirement ID sequence"),
    "SK-013": ("info", "Bare [NEEDS CLARIFICATION] mention without a question"),
}

NOT_CHECKED = (
    "Focused on user value and business needs",
    "Written for non-technical stakeholders",
    "No implementation details (languages, frameworks, APIs)",
    "Scope is clearly bounded",
    "Requirements are unambiguous beyond the smell lexicons",
    "User scenarios cover primary flows",
)


def _finding(check_id: str, message: str, line: int | None = None, ref: str | None = None):
    return Finding(check_id=check_id, severity=CHECKS[check_id][0], message=message, line=line,
                   ref=ref)


def check_structure(doc: SpecDocument, results: list[RequirementResult]) -> list[Finding]:
    out: list[Finding] = []

    for m in doc.markers:
        if m.question:
            out.append(_finding("SK-001", f"Open clarification: {m.question}", m.line))
        else:
            out.append(_finding("SK-013", "Bare [NEEDS CLARIFICATION] mention (no question)",
                                m.line))

    for placeholder, line in doc.template_leftovers:
        out.append(_finding("SK-002", f"Template placeholder left unfilled: {placeholder}", line))

    headings = [h.text for h in doc.headings if h.level >= 2]
    for name, pattern in MANDATORY_SECTIONS:
        if not any(pattern.search(h) for h in headings):
            out.append(_finding("SK-003", f"Mandatory section missing: {name}"))

    lines_by_id: dict[str, list[int]] = defaultdict(list)
    for r in doc.requirements:
        lines_by_id[r.req_id].append(r.line)
    for rid, lines in sorted(lines_by_id.items()):
        if len(lines) > 1:
            where = ", ".join(f"L{n}" for n in lines)
            out.append(_finding("SK-004", f"{rid} is defined {len(lines)} times ({where})",
                                lines[1], rid))

    if not doc.ids("FR"):
        out.append(_finding("SK-005", "No FR-### requirement bullets were recognized"))

    for story in doc.stories:
        if story.priority is None:
            out.append(_finding("SK-006", f"{story.label} has no (Priority: P#)", story.line,
                                story.label))
        if not any(s.is_gwt for s in story.scenarios):
            out.append(_finding(
                "SK-007", f"{story.label} has no Given/When/Then acceptance scenario",
                story.line, story.label))

    for r in doc.requirements:
        if r.kind != "SC" and not NORMATIVE_RE.search(r.text):
            out.append(_finding("SK-008", f"{r.req_id} has no MUST/SHALL/SHOULD/MAY", r.line,
                                r.req_id))

    for res in results:
        if res.sc_class == UNMEASURED:
            out.append(_finding(
                "SK-009",
                f"{res.requirement.req_id} states no metric (time, percentage, count, rate) "
                "and no absolute pass/fail condition",
                res.requirement.line, res.requirement.req_id))
        elif res.sc_class == BINARY:
            out.append(_finding(
                "SK-010",
                f"{res.requirement.req_id} is verifiable as pass/fail but has no metric "
                "(Spec Kit guideline asks for time, percentage, count or rate)",
                res.requirement.line, res.requirement.req_id))

    if doc.requirements and not any(EDGE_CASES_RE.search(h) for h in headings):
        out.append(_finding("SK-011", "No 'Edge Cases' section"))

    by_kind: dict[str, list[int]] = defaultdict(list)
    for r in doc.requirements:
        digits = re.sub(r"\D", "", r.req_id)
        if digits and r.req_id[-1].isdigit():
            by_kind[r.kind].append(int(digits))
    for kind, nums in sorted(by_kind.items()):
        present = sorted(set(nums))
        missing = [n for n in range(present[0], present[-1] + 1) if n not in set(present)]
        if missing:
            shown = ", ".join(f"{kind}-{n:03d}" for n in missing[:10])
            more = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
            out.append(_finding("SK-012", f"Missing IDs in sequence: {shown}{more}"))

    return sorted(out, key=Finding.sort_key)
