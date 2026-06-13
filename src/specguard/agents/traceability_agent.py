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
supplied, the agent builds the same in-memory mock-metadata runner used by
``scripts/compliance_demo.py`` from the dispatched requirements, so the
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
                mock-metadata factory mirroring ``scripts/compliance_demo.py``.
            constraints: objective set to evaluate (defaults to the 15
                representative objectives).
        """
        super().__init__(name, provider=provider, provider_name=provider_name)
        self._runner = runner
        self._runner_factory = runner_factory or _build_inmemory_runner
        self.constraints = constraints if constraints is not None else DEFAULT_OBJECTIVES

    def run(self, request: AgentRequest) -> AgentReport:
        runner = self._runner or self._runner_factory(request.requirements)
        report = run_compliance_check(
            runner, self.constraints, standard_name="DO-178C/254 + Cross-Domain"
        )

        payload = {
            "objectives_checked": report.total_objectives_checked,
            "passing": len(report.passing_objective_ids),
            "passing_objective_ids": report.passing_objective_ids,
            "violation_count": report.violation_count,
            "compliance_rate": round(report.compliance_rate, 3),
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
                f"- compliance rate: {report.compliance_rate:.1%}\n\n"
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


# ---------------------------------------------------------------------------
# Default in-memory runner — mirrors scripts/compliance_demo.py's MockGraph.
#
# Kept inside the agents package (stdlib-only) so the skeleton is
# self-contained and importable without the scripts/ sys.path shim. This is a
# *pattern-recognition* runner for the representative objectives, not a Cypher
# parser; production substitutes Neo4jGraphRunner via the `runner` argument.
# ---------------------------------------------------------------------------


class _MockGraph:
    """Minimal in-memory graph supporting the demo's Cypher-pattern dispatch."""

    def __init__(self) -> None:
        self.requirements: list[dict] = []
        self.smells: list[dict] = []
        self.relationships: list[dict] = []

    def add_requirement(self, **props) -> None:
        self.requirements.append(props)

    def add_smell(self, req_id: str, smell_type: str, severity: str, trigger: str) -> None:
        self.smells.append(
            {"req_id": req_id, "smell_type": smell_type, "severity": severity, "trigger": trigger}
        )
        self.relationships.append(
            {"source": req_id, "edge_type": "HAS_SMELL", "target": f"smell_{len(self.smells)}"}
        )

    def add_edge(self, source_id: str, edge_type: str, target_id: str) -> None:
        self.relationships.append(
            {"source": source_id, "edge_type": edge_type, "target": target_id}
        )

    def has_outgoing_edge(self, req_id, edge_types, target_filter=None) -> bool:
        for rel in self.relationships:
            if rel["source"] == req_id and rel["edge_type"] in edge_types:
                if target_filter is None:
                    return True
                target_req = next(
                    (r for r in self.requirements if r.get("id") == rel["target"]), None
                )
                if target_req and all(target_req.get(k) == v for k, v in target_filter.items()):
                    return True
        return False

    def has_incoming_edge(self, req_id, edge_types) -> bool:
        return any(
            rel["target"] == req_id and rel["edge_type"] in edge_types
            for rel in self.relationships
        )


def _build_demo_graph(requirements: list) -> _MockGraph:
    """Augment the dispatched requirements with mock certification metadata."""
    import hashlib

    from specguard.core.smell_detector import analyze_requirement

    def _stable_parity(s: str) -> int:
        # Deterministic across processes (Python's built-in hash() is salted
        # per-process via PYTHONHASHSEED). Mirrors the demo's "~half have a
        # test" mock-coverage rule but reproducibly, so the results JSON is
        # stable run-to-run — required for an auditable research artifact.
        return int.from_bytes(hashlib.md5(s.encode()).digest()[:8], "big") % 2

    graph = _MockGraph()
    graph.add_requirement(id="SYS-1", text="Processor shall execute RISC-V ISA",
                          level="system", dal="A")
    graph.add_requirement(id="SYS-2", text="Processor shall meet performance targets",
                          level="system", dal="B")

    for req in requirements:
        graph.add_requirement(
            id=req.req_id,
            text=req.text,
            level="HLR",
            dal="A" if req.req_id.startswith("ISA") else "B",
            category=req.category,
            is_derived=False,
        )
        if req.req_id.startswith("ISA") and req.req_id != "ISA-90":
            graph.add_edge(req.req_id, "DERIVES_FROM", "SYS-1")
        elif req.category == "Performance" and req.req_id != "PPA-50":
            graph.add_edge(req.req_id, "DERIVES_FROM", "SYS-2")
        if _stable_parity(req.req_id) == 0:
            graph.add_edge(f"TC_{req.req_id}", "VERIFIES", req.req_id)

    for req in requirements:
        report = analyze_requirement(req.req_id, req.text)
        for hit in report.hits:
            graph.add_smell(req.req_id, hit.smell_type.value, hit.severity, hit.trigger)
    return graph


def _build_inmemory_runner(requirements: list) -> GraphRunner:
    """Build a ``GraphRunner`` over an in-memory mock graph of ``requirements``.

    The interpreter recognises the representative objectives by Cypher-pattern
    substrings, identical to ``scripts/compliance_demo.py``. Objectives whose
    data the mock graph does not model return no rows (treated as passing).
    """
    graph = _build_demo_graph(requirements)

    def run(query: str, params: dict) -> list[dict]:
        if "DERIVES_FROM|TRACES_TO" in query and "level: 'HLR'" in query \
                and "level: 'system'" in query:
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_system_traceability"}
                for r in graph.requirements
                if r.get("level") == "HLR"
                and not graph.has_outgoing_edge(
                    r["id"], ["DERIVES_FROM", "TRACES_TO"], target_filter={"level": "system"})
            ]
        if "HAS_SMELL" in query and "high" in query:
            results = []
            for smell in graph.smells:
                if smell["severity"] != "high":
                    continue
                req = next((r for r in graph.requirements if r["id"] == smell["req_id"]), None)
                if req and req.get("level") == "HLR":
                    results.append({
                        "violating_requirement": req["id"], "req_text": req["text"],
                        "reason": smell["smell_type"], "smell_trigger": smell["trigger"]})
            return results
        if "category IN ['Performance'" in query:
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": r.get("category", "")}
                for r in graph.requirements
                if r.get("level") == "HLR"
                and r.get("category") in ["Performance", "Timing", "Memory", "PPA"]
                and not graph.has_outgoing_edge(r["id"], ["CONSTRAINED_BY"])
            ]
        if "level: 'LLR'" in query and "level: 'HLR'" in query and "DERIVES_FROM" in query:
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_hlr_parent"}
                for r in graph.requirements
                if r.get("level") == "LLR"
                and not graph.has_outgoing_edge(
                    r["id"], ["DERIVES_FROM"], target_filter={"level": "HLR"})
            ]
        if "IMPLEMENTS" in query and "SoftwareModule" in query:
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_implementing_module"}
                for r in graph.requirements
                if r.get("level") == "HLR"
                and not graph.has_incoming_edge(r["id"], ["IMPLEMENTS"])
            ]
        if "VERIFIES" in query and "level IN ['HLR', 'LLR']" in query:
            return [
                {"violating_requirement": r["id"], "req_level": r.get("level"),
                 "dal_level": r.get("dal"), "reason": "no_verifying_test"}
                for r in graph.requirements
                if r.get("level") in ["HLR", "LLR"]
                and r.get("dal") in ["A", "B", "C"]
                and not graph.has_incoming_edge(r["id"], ["VERIFIES"])
            ]
        if "MC/DC" in query:
            results = []
            for r in graph.requirements:
                if r.get("level") != "HLR" or r.get("dal") != "A":
                    continue
                has_mcdc = any(
                    rel["target"] == r["id"] and rel["edge_type"] == "VERIFIES"
                    and rel.get("coverage_type") == "MC/DC"
                    for rel in graph.relationships
                )
                if not has_mcdc:
                    results.append({"violating_requirement": r["id"], "req_text": r["text"],
                                    "reason": "missing_mcdc_coverage"})
            return results
        if "VERIFIED_BY_METHOD" in query:
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "dal_level": r.get("dal"), "reason": "no_verification_method"}
                for r in graph.requirements
                if r.get("level") == "HWR"
                and r.get("dal") in ["A", "B", "C"]
                and not graph.has_outgoing_edge(r["id"], ["VERIFIED_BY_METHOD"])
            ]
        if "DERIVED_FROM_RATIONALE" in query and "is_derived = true" in query \
                and "level: 'HWR'" in query \
                and "DAL" not in query.upper().split("WHERE")[1][:50]:
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "derived_without_rationale"}
                for r in graph.requirements
                if r.get("level") == "HWR"
                and r.get("is_derived") is True
                and not graph.has_outgoing_edge(r["id"], ["DERIVED_FROM_RATIONALE"])
            ]
        return []

    return run
