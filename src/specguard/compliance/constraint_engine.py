"""Scoped graph-pattern checks with explicit uncertainty and evidence freshness.

Legacy regulatory identifiers label illustrative project patterns, not a proof
of an entire standard's objectives. Scope, expected objects and prerequisites
are supplied separately from violation queries. Empty legacy rows are UNKNOWN;
execution failures are ERROR. All reports preserve per-object diagnostics and
only compute a PASS fraction among completed applicable checks.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from specguard.verification.results import CheckResult, CheckStatus, summarize


@dataclass
class ComplianceConstraint:
    """A regulatory objective codified as an executable graph pattern.

    Legacy regulatory mappings are illustrative and require independent review;
    successful execution of a graph pattern establishes only that pattern.
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
class RuleScope:
    """Independently supplied inventory/preconditions, never inferred from violation rows.

    expected_objects must enumerate the complete applicable rule/object scope.
    source identifies the reviewed applicability decision. complete refers to all
    predicates used by this rule (including relationship inventories).
    """

    expected_objects: list[str]
    source: str
    complete: bool = False
    supported: bool = True
    missing_prerequisites: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    dependency_versions: dict[str, str] = field(default_factory=dict)
    freshness: str = "CURRENT"
    not_applicable_reason: str = ""


@dataclass
class ComplianceReport:
    """Project graph checks; regulatory identifiers are legacy illustrative mappings."""

    standard: str
    timestamp: str
    total_objectives_checked: int
    passing_objective_ids: list[str]
    violations: list[ComplianceViolation]
    results: list[CheckResult] = field(default_factory=list)

    @property
    def compliance_rate(self) -> float | None:
        """Deprecated alias: PASS fraction of current completed rule/object checks."""
        return summarize(self.results)["pass_fraction_completed"]

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    def violations_by_objective(self) -> dict[str, list[ComplianceViolation]]:
        grouped: dict[str, list[ComplianceViolation]] = {}
        for v in self.violations:
            grouped.setdefault(v.objective_id, []).append(v)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "summary": summarize(self.results),
            "compliance_rate": self.compliance_rate,
        }

    def summary(self) -> str:
        stats = summarize(self.results)
        fraction = stats["pass_fraction_completed"]
        rate = f"{fraction:.1%}" if fraction is not None else "not assessed"
        lines = [
            f"Project graph checks — {self.standard}",
            f"Rule/object statuses: {stats['counts']}",
            f"PASS fraction among completed applicable checks: {rate} "
            f"(denominator={stats['completed_applicable_checks']})",
            f"Expected checks: {stats['expected_checks']}; "
            f"completion coverage: {stats['completion_coverage']}; "
            f"STALE: {stats['stale']}; freshness unknown: {stats['freshness_unknown']}",
        ]
        lines += [
            f"[{r.status}/{r.freshness}] {r.rule_id} {r.objects}: {r.reason}" for r in self.results
        ]
        return "\n".join(lines)


GraphRunner = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


def run_compliance_check(
    graph_runner: GraphRunner,
    constraints: list[ComplianceConstraint],
    standard_name: str = "DO-178C/254",
    dal_filter: str | None = None,
    *,
    scopes: dict[str, RuleScope] | None = None,
) -> ComplianceReport:
    """Evaluate queries with a separately reviewed scope/precondition manifest.

    A legacy violations-only runner has no closed-world authority. Its rows
    remain candidate diagnostics, including apparent missing-edge violations.
    Execution failures are ERROR even when the scope is unknown.
    """
    results: list[CheckResult] = []
    violations: list[ComplianceViolation] = []
    passing = []
    for c in constraints:
        ctx = (scopes or {}).get(c.objective_id)
        if ctx is None and hasattr(graph_runner, "scope_for"):
            try:
                ctx = graph_runner.scope_for(c)  # type: ignore[attr-defined]
            except Exception as exc:
                results.append(
                    CheckResult(
                        c.objective_id,
                        [],
                        CheckStatus.ERROR,
                        f"Scope evaluation failed: {type(exc).__name__}: {exc}",
                    )
                )
                continue

        def emit(status, reason, objects=None, c=c, ctx=ctx, **kwargs):
            result = CheckResult(
                c.objective_id,
                objects or [],
                status,
                reason,
                applicability=ctx.source if ctx else "Unknown runner scope",
                scope=ctx.source if ctx else "undeclared",
                evidence=list(ctx.evidence) if ctx else [],
                dependency_versions=dict(ctx.dependency_versions) if ctx else {},
                freshness=ctx.freshness if ctx else "CURRENT",
                **kwargs,
            )
            results.append(result)

        if dal_filter is not None and dal_filter not in c.applicable_dal:
            emit(CheckStatus.NOT_APPLICABLE, f"Rule excludes declared DAL {dal_filter}")
            continue
        if (
            ctx
            and ctx.complete
            and ctx.source
            and not ctx.expected_objects
            and (ctx.not_applicable_reason and not ctx.missing_prerequisites and ctx.supported)
        ):
            emit(CheckStatus.NOT_APPLICABLE, ctx.not_applicable_reason)
            continue
        try:
            rows = graph_runner(c.cypher_query, {})
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise TypeError("Runner must return list[dict]")
        except Exception as exc:
            emit(
                CheckStatus.ERROR,
                f"{type(exc).__name__}: {exc}",
                ctx.expected_objects if ctx else [],
            )
            continue
        missing = list(ctx.missing_prerequisites) if ctx else ["reviewed scope and prerequisites"]
        if ctx and not ctx.complete:
            missing.append("complete rule inventory")
        if ctx and (not ctx.source or not ctx.expected_objects or not ctx.supported):
            missing.append("supported rule with reviewed, enumerated applicability")
        if hasattr(graph_runner, "supports_constraint") and not graph_runner.supports_constraint(c):
            missing.append("runner capability for this rule")
        if missing:
            emit(
                CheckStatus.UNKNOWN,
                "Insufficient basis for a closed-world graph check",
                ctx.expected_objects if ctx else [],
                missing_prerequisites=missing,
                details={
                    "candidate_rows": rows,
                    "scope_unknown": not bool(ctx and ctx.complete and ctx.source),
                },
            )
            if c.objective_id == "CROSS-TIMING-1":
                for row in rows:
                    # The query evaluates only explicit additive, nonnegative budgets.
                    if row.get("_status") == "FAIL":
                        witness_target = str(row.get("violating_requirement", "<unknown>"))
                        try:
                            reason = c.violation_template.format(**row)
                        except (KeyError, ValueError) as exc:
                            emit(
                                CheckStatus.ERROR,
                                f"Malformed timing witness: {exc}",
                                [witness_target],
                            )
                            continue
                        emit(
                            CheckStatus.FAIL,
                            reason,
                            [witness_target],
                            missing_prerequisites=missing,
                            details={"row": row},
                        )
                        violations.append(
                            ComplianceViolation(
                                c.objective_id,
                                c.standard,
                                c.table,
                                c.title,
                                witness_target,
                                reason,
                                row,
                            )
                        )
            continue
        assert ctx is not None
        by_object: dict[str, list[dict]] = {}
        for row in rows:
            target = (
                row.get("violating_requirement")
                or row.get("violating_element")
                or row.get("req_id")
            )
            if target not in ctx.expected_objects:
                emit(
                    CheckStatus.ERROR,
                    "Runner returned an object outside declared scope",
                    [str(target)],
                    details={"row": row},
                )
            else:
                by_object.setdefault(target, []).append(row)
        for obj in ctx.expected_objects:
            findings = by_object.get(obj, [])
            if not findings:
                emit(
                    CheckStatus.PASS, "No violation of this graph pattern in reviewed scope", [obj]
                )
            for row in findings:
                try:
                    reason = c.violation_template.format(**row)
                except KeyError:
                    reason = f"{c.title}: {row}"
                status = CheckStatus(row.get("_status", "FAIL"))
                emit(
                    status,
                    reason if status == CheckStatus.FAIL else row.get("reason", reason),
                    [obj],
                    details={"row": row},
                    missing_prerequisites=["component budgets"]
                    if row.get("missing_budgets")
                    else [],
                )
                if status != CheckStatus.FAIL:
                    continue
                violations.append(
                    ComplianceViolation(
                        c.objective_id, c.standard, c.table, c.title, obj, reason, row
                    )
                )
        rule_results = [r for r in results if r.rule_id == c.objective_id]
        if rule_results and all(
            r.status == CheckStatus.PASS and r.freshness == "CURRENT" for r in rule_results
        ):
            passing.append(c.objective_id)
    return ComplianceReport(
        standard_name, datetime.now(UTC).isoformat(), len(constraints), passing, violations, results
    )
