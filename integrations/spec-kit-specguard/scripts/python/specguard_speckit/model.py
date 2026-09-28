"""Data model shared by parsers, checks and reports."""

from __future__ import annotations

from dataclasses import dataclass, field

SEVERITY_ORDER = {"info": 0, "warn": 1, "error": 2}
VERDICT_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}


@dataclass
class Requirement:
    """One FR / SC / NFR bullet from spec.md."""

    req_id: str
    """Identifier as written, e.g. ``FR-001``."""

    kind: str
    """``FR``, ``SC`` or ``NFR`` (the ID prefix)."""

    text: str
    """Plain text used for analysis: emphasis/code markup removed, clarification
    markers removed (they are reported separately)."""

    raw: str
    """Text as written, continuation lines joined."""

    line: int
    """1-based line of the bullet in spec.md."""

    section: str = ""
    """Nearest heading above the bullet."""

    markers: list[str] = field(default_factory=list)
    """Open ``[NEEDS CLARIFICATION: ...]`` payloads inside this requirement."""


@dataclass
class Scenario:
    text: str
    line: int
    is_gwt: bool
    """True when the item contains Given, When and Then."""


@dataclass
class UserStory:
    number: int | None
    title: str
    priority: str | None
    line: int
    scenarios: list[Scenario] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"US{self.number}" if self.number is not None else self.title


@dataclass
class Marker:
    """A ``[NEEDS CLARIFICATION ...]`` occurrence outside fenced code."""

    line: int
    question: str | None
    """Payload after the colon; ``None`` for a bare mention."""


@dataclass
class Heading:
    level: int
    text: str
    line: int


@dataclass
class SpecDocument:
    path: str | None
    title: str | None
    headings: list[Heading] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    stories: list[UserStory] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    template_leftovers: list[tuple] = field(default_factory=list)
    """``(placeholder, line)`` pairs of unfilled spec-template placeholders."""

    def ids(self, kind: str | None = None) -> list[str]:
        return [r.req_id for r in self.requirements if kind is None or r.kind == kind]


@dataclass
class Task:
    task_id: str
    done: bool
    text: str
    line: int
    phase: str = ""
    parallel: bool = False
    story_tags: list[str] = field(default_factory=list)
    """``US#`` tags from the leading ``[US#]`` brackets."""
    refs: list[str] = field(default_factory=list)
    """Requirement IDs (FR/SC/NFR) mentioned anywhere in the task text."""


@dataclass
class TasksDocument:
    path: str | None
    tasks: list[Task] = field(default_factory=list)


@dataclass
class Finding:
    check_id: str
    severity: str
    """``error`` | ``warn`` | ``info``."""
    message: str
    line: int | None = None
    ref: str | None = None
    """Requirement / story / task the finding is about, if any."""

    def sort_key(self) -> tuple:
        return (-SEVERITY_ORDER[self.severity], self.line or 0, self.check_id, self.ref or "")


def verdict_from(findings: list[Finding], gates: list[str]) -> str:
    """Worst of requirement gates and structural findings.

    error finding -> FAIL, warn finding -> WARN, info never affects the verdict.
    """
    worst = 0
    for gate in gates:
        worst = max(worst, VERDICT_ORDER[gate])
    for f in findings:
        if f.severity == "error":
            worst = max(worst, 2)
        elif f.severity == "warn":
            worst = max(worst, 1)
    return {0: "PASS", 1: "WARN", 2: "FAIL"}[worst]
