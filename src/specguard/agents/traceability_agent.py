"""Traceability Agent — wraps Layer 3 (compliance constraint engine).

Runs the codified DO-178C / DO-254 / cross-domain objectives
(``specguard.compliance``) against a knowledge graph via the existing
``GraphRunner`` callable interface ``(cypher_query, params) -> list[dict]``.

Runner injection
----------------
The ``GraphRunner`` is **injectable** (constructor argument ``runner``), exactly
as ``run_compliance_check`` expects. This is the seam where a real
``Neo4jGraphRunner`` (Phase 1a, in the ``[graph]`` extra) would be substituted
for the in-memory demo runner without changing the agent. When no runner is
supplied, the agent builds an unclassified in-memory graph from the dispatched requirements, so the
skeleton runs end-to-end with no database (plain ``pytest`` stays green).

The objective sets default to the 15 representative objectives (7 DO-178C +
5 DO-254 + 3 cross-domain) but are also injectable for testing.

LLM role: augmentative annotation of the compliance summary only; the
pass/fail results come entirely from the deterministic constraint engine.
"""

from __future__ import annotations

from collections.abc import Callable

from specguard.compliance import (
    CROSS_DOMAIN_OBJECTIVES,
    DO_178C_OBJECTIVES,
    DO_254_OBJECTIVES,
    ComplianceConstraint,
    run_compliance_check,
)
from specguard.compliance.constraint_engine import GraphRunner

from .base import Agent, AgentReport, AgentRequest

#: Default representative objective set (matches the compliance demo).
DEFAULT_OBJECTIVES: list[ComplianceConstraint] = (
    list(DO_178C_OBJECTIVES) + list(DO_254_OBJECTIVES) + list(CROSS_DOMAIN_OBJECTIVES)
)


class TraceabilityAgent(Agent):
    """Wraps the Layer 3 compliance engine with an injectable GraphRunner."""

    role = "Traceability Agent (Layer 3 compliance + cross-domain binding)"

    def __init__(
        self,
        name: str,
        *,
        runner: GraphRunner | None = None,
        runner_factory: Callable[[list], GraphRunner] | None = None,
        constraints: list[ComplianceConstraint] | None = None,
        provider=None,
        provider_name: str | None = None,
    ) -> None:
        """Construct the agent.

        Args:
            runner: a ready ``GraphRunner``; used as-is if given.
            runner_factory: builds a runner from the dispatched requirements
                (used when ``runner`` is ``None``). Defaults to the in-memory
                unclassified requirements factory; no synthetic evidence is generated.
            constraints: objective set to evaluate (defaults to the 15
                representative objectives).
        """
        super().__init__(name, provider=provider, provider_name=provider_name)
        self._runner = runner
        self._runner_factory = runner_factory or _build_inmemory_runner
        self.constraints = constraints if constraints is not None else DEFAULT_OBJECTIVES

    def run(self, request: AgentRequest) -> AgentReport:
        if 'verification_bundle' in request.context:
            from specguard.verification.analyzer import analyze_bundle
            from specguard.verification.model import Bundle
            payload = analyze_bundle(Bundle.from_dict(request.context['verification_bundle']))
            return AgentReport(agent_name=self.name, role=self.role, payload=payload)
        runner = self._runner or self._runner_factory(request.requirements)
        report = run_compliance_check(
            runner, self.constraints, standard_name="DO-178C/254 + Cross-Domain"
        )

        payload = {
            "objectives_checked": report.total_objectives_checked,
            "passing": len(report.passing_objective_ids),
            "passing_objective_ids": report.passing_objective_ids,
            "violation_count": report.violation_count,
            "compliance_rate": report.compliance_rate,
            "summary": report.to_dict()["summary"],
            "results": [r.to_dict() for r in report.results],
            "synthetic": getattr(runner, "synthetic", None),
            "violations_by_objective": {
                obj_id: len(viols)
                for obj_id, viols in report.violations_by_objective().items()
            },
        }

        annotation: str | None = None
        used_provider: str | None = None
        if self.provider is not None:
            prompt = (
                "Deterministic compliance check (already final):\n"
                f"- objectives checked: {report.total_objectives_checked}\n"
                f"- passing: {len(report.passing_objective_ids)}\n"
                f"- violations: {report.violation_count}\n"
                f"- scoped results: {report.to_dict()['summary']}\n\n"
                "Explain the compliance posture in one short paragraph for a "
                "certification engineer."
            )
            annotation = self.provider.complete(
                prompt,
                system="You are an augmentative compliance analyst; you never "
                "change the deterministic pass/fail verdicts.",
            )
            used_provider = self.provider_name

        return AgentReport(
            agent_name=self.name,
            role=self.role,
            payload=payload,
            llm_annotation=annotation,
            used_provider=used_provider,
        )


def _build_inmemory_runner(requirements: list) -> GraphRunner:
    """User text has no reviewed certification metadata or graph scope."""
    from specguard.compliance.memory_runner import MockGraph, make_graph_runner

    graph = MockGraph()
    for req in requirements:
        graph.add_requirement(id=req.req_id, text=req.text, category=req.category)
    return make_graph_runner(graph)
