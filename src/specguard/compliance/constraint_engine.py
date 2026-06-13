"""Constraint engine for compliance verification.

A regulatory objective from DO-178C / DO-254 / similar standards is
represented as:
    - id, title, description (human-readable metadata)
    - applicable_dal (which Design Assurance Levels this applies to)
    - cypher_query (executable pattern that returns violations)
    - violation_template (template for human-readable finding)

The engine runs each constraint's Cypher query against a knowledge graph
and produces a structured compliance report with:
    - aggregate compliance rate
    - per-objective pass/fail status
    - detailed violation list with traceability
    - audit trail (timestamps, agent identity)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ComplianceConstraint:
    """A regulatory objective codified as an executable graph pattern.

    This is the core abstraction implementing scientific novelty #3:
    'Codification of regulatory objectives as executable graph constraints'.
    """

    objective_id: str
    """Stable identifier, e.g. 'DO-178C-A3-1'."""

    standard: str
    """Standard name, e.g. 'DO-178C', 'DO-254'."""

    table: str
    """Table or section reference, e.g. 'A-3', '6.3.1'."""

    title: str
    """Short title from the standard."""

    description: str
    """Verbatim or close paraphrase of the objective text."""

    applicable_dal: list[str]
    """Design Assurance Levels for which this objective is required."""

    cypher_query: str
    """Executable Cypher pattern returning violating elements.

    Convention: query returns rows where each row represents a violation.
    Required column: 'violating_requirement' (or similar).
    Optional columns: 'reason', 'severity', additional context.
    """

    violation_template: str
    """Template for human-readable finding, with {placeholders}."""

    rationale: str = ""
    """Why this codification is correct interpretation of the objective."""


@dataclass
class ComplianceViolation:
    """A single violation detected by a constraint."""

    objective_id: str
    standard: str
    table: str
    title: str
    violating_element: str
    """ID of the requirement / artifact that violates the objective."""

    explanation: str
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceReport:
    """Structured compliance assessment over a set of objectives."""

    standard: str
    timestamp: str
    total_objectives_checked: int
    passing_objective_ids: list[str]
    violations: list[ComplianceViolation]

    @property
    def compliance_rate(self) -> float:
        """Fraction of objectives with zero violations."""
        if self.total_objectives_checked == 0:
            return 1.0
        return len(self.passing_objective_ids) / self.total_objectives_checked

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    def violations_by_objective(self) -> dict[str, list[ComplianceViolation]]:
        """Group violations by objective_id."""
        grouped: dict[str, list[ComplianceViolation]] = {}
        for v in self.violations:
            grouped.setdefault(v.objective_id, []).append(v)
        return grouped

    def summary(self) -> str:
        """Human-readable summary suitable for engineer review."""
        lines = [
            f"Compliance Report — {self.standard}",
            f"Generated: {self.timestamp}",
            "",
            f"Objectives checked:  {self.total_objectives_checked}",
            f"Passing:             {len(self.passing_objective_ids)}",
            f"Compliance rate:     {self.compliance_rate:.1%}",
            f"Total violations:    {self.violation_count}",
            "",
        ]
        if self.violations:
            lines.append("Violations:")
            grouped = self.violations_by_objective()
            for obj_id, viols in grouped.items():
                lines.append(f"  [{obj_id}] {viols[0].title}")
                for v in viols:
                    lines.append(f"    - {v.violating_element}: {v.explanation}")
        else:
            lines.append("No violations detected. ✓")
        return "\n".join(lines)


# Type alias for the graph runner interface — abstract so we can use
# either Neo4j driver or a local NetworkX-based mock.
GraphRunner = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


def run_compliance_check(
    graph_runner: GraphRunner,
    constraints: list[ComplianceConstraint],
    standard_name: str = "DO-178C/254",
    dal_filter: str | None = None,
) -> ComplianceReport:
    """Execute all applicable constraints against the graph.

    Args:
        graph_runner: callable that accepts (cypher_query, params) and
            returns a list of dict rows.
        constraints: list of ComplianceConstraint to evaluate.
        standard_name: label used in the report.
        dal_filter: if provided, only constraints applicable to this DAL
            are evaluated (e.g. 'A' for the most stringent).

    Returns:
        Structured ComplianceReport with violations and pass list.
    """
    applicable = constraints
    if dal_filter is not None:
        applicable = [
            c for c in constraints if dal_filter in c.applicable_dal
        ]

    passing_ids: list[str] = []
    all_violations: list[ComplianceViolation] = []

    for constraint in applicable:
        rows = graph_runner(constraint.cypher_query, {})
        if not rows:
            passing_ids.append(constraint.objective_id)
            continue

        for row in rows:
            try:
                explanation = constraint.violation_template.format(**row)
            except KeyError:
                # Template references a column that wasn't returned —
                # fall back to title for safety
                explanation = f"{constraint.title} (data: {row})"

            violation_target = (
                row.get("violating_requirement")
                or row.get("violating_element")
                or row.get("req_id")
                or "<unknown>"
            )

            all_violations.append(
                ComplianceViolation(
                    objective_id=constraint.objective_id,
                    standard=constraint.standard,
                    table=constraint.table,
                    title=constraint.title,
                    violating_element=str(violation_target),
                    explanation=explanation,
                    raw_data=row,
                )
            )

    return ComplianceReport(
        standard=standard_name,
        timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        total_objectives_checked=len(applicable),
        passing_objective_ids=passing_ids,
        violations=all_violations,
    )
