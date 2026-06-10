"""In-memory compliance runner for the no-database fallback path.

The unified CLI's ``specguard comply --memory`` must work without a Neo4j
instance and without depending on ``scripts/`` being importable (an installed
console entry point does not have the repo root on ``sys.path``). This module
therefore re-homes the demo's MockGraph + pattern-recognition runner inside the
package, so the in-memory path is importable as
``specguard.compliance.memory_runner``.

Honesty / scope (unchanged from scripts/compliance_demo.py)
-----------------------------------------------------------
This is a *pattern-recognition* runner: it dispatches each constraint by
``objective_id`` semantics rather than parsing Cypher, and the certification
metadata it builds (DAL / level / traceability) is **mock** — the public CVA6
spec carries none. It demonstrates that the codified objectives execute
end-to-end and discriminate; it is **not** certification evidence. The
authoritative Cypher execution path is :class:`Neo4jGraphRunner`.
"""

from __future__ import annotations

from collections.abc import Callable

from specguard.data.cva6_requirements import get_all_requirements


class MockGraph:
    """Minimal in-memory graph supporting the constraint runner's needs."""

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

    def has_outgoing_edge(
        self, req_id: str, edge_types: list[str], target_filter: dict | None = None
    ) -> bool:
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

    def has_incoming_edge(self, req_id: str, edge_types: list[str]) -> bool:
        return any(
            rel["target"] == req_id and rel["edge_type"] in edge_types
            for rel in self.relationships
        )


def make_graph_runner(graph: MockGraph) -> Callable[[str, dict], list[dict]]:
    """Build a runner matching constraint Cypher patterns by objective semantics."""

    def run(query: str, params: dict) -> list[dict]:
        if (
            "DERIVES_FROM|TRACES_TO" in query
            and "level: 'HLR'" in query
            and "level: 'system'" in query
        ):
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_system_traceability"}
                for r in graph.requirements
                if r.get("level") == "HLR"
                and not graph.has_outgoing_edge(
                    r["id"], ["DERIVES_FROM", "TRACES_TO"], target_filter={"level": "system"}
                )
            ]

        if "HAS_SMELL" in query and "high" in query:
            results = []
            for smell in graph.smells:
                if smell["severity"] != "high":
                    continue
                req = next((r for r in graph.requirements if r["id"] == smell["req_id"]), None)
                if req and req.get("level") == "HLR":
                    results.append(
                        {"violating_requirement": req["id"], "req_text": req["text"],
                         "reason": smell["smell_type"], "smell_trigger": smell["trigger"]}
                    )
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
                {"violating_requirement": r["id"], "req_text": r["text"], "reason": "no_hlr_parent"}
                for r in graph.requirements
                if r.get("level") == "LLR"
                and not graph.has_outgoing_edge(
                    r["id"], ["DERIVES_FROM"], target_filter={"level": "HLR"}
                )
            ]

        if "IMPLEMENTS" in query and "SoftwareModule" in query:
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_implementing_module"}
                for r in graph.requirements
                if r.get("level") == "HLR" and not graph.has_incoming_edge(r["id"], ["IMPLEMENTS"])
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
                    rel["target"] == r["id"]
                    and rel["edge_type"] == "VERIFIES"
                    and rel.get("coverage_type") == "MC/DC"
                    for rel in graph.relationships
                )
                if not has_mcdc:
                    results.append(
                        {"violating_requirement": r["id"], "req_text": r["text"],
                         "reason": "missing_mcdc_coverage"}
                    )
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

        if (
            "DERIVED_FROM_RATIONALE" in query
            and "is_derived = true" in query
            and "level: 'HWR'" in query
            and "DAL" not in query.upper().split("WHERE")[1][:50]
        ):
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "derived_without_rationale"}
                for r in graph.requirements
                if r.get("level") == "HWR"
                and r.get("is_derived") is True
                and not graph.has_outgoing_edge(r["id"], ["DERIVED_FROM_RATIONALE"])
            ]

        # Objectives without mock data return no violation (demo behaviour).
        return []

    return run


def build_demo_graph() -> MockGraph:
    """Construct the CVA6 graph with mock certification metadata.

    Identical augmentation to ``scripts/compliance_demo.build_demo_graph``:
    all CVA6 reqs become HLR, ISA* are DAL-A, ~70% of ISA / Performance reqs
    are traced, ~half get a verifying test, and smells are attached.
    """
    from specguard.core.smell_detector import analyze_requirement

    graph = MockGraph()
    cva6_reqs = get_all_requirements()

    graph.add_requirement(id="SYS-1", text="Processor shall execute RISC-V ISA",
                          level="system", dal="A")
    graph.add_requirement(id="SYS-2", text="Processor shall meet performance targets",
                          level="system", dal="B")

    for req in cva6_reqs:
        graph.add_requirement(
            id=req.req_id, text=req.text, level="HLR",
            dal="A" if req.req_id.startswith("ISA") else "B",
            category=req.category, is_derived=False,
        )
        if req.req_id.startswith("ISA") and req.req_id != "ISA-90":
            graph.add_edge(req.req_id, "DERIVES_FROM", "SYS-1")
        elif req.category == "Performance" and req.req_id != "PPA-50":
            graph.add_edge(req.req_id, "DERIVES_FROM", "SYS-2")
        if hash(req.req_id) % 2 == 0:
            graph.add_edge(f"TC_{req.req_id}", "VERIFIES", req.req_id)

    for req in cva6_reqs:
        for hit in analyze_requirement(req.req_id, req.text).hits:
            graph.add_smell(
                req_id=req.req_id, smell_type=hit.smell_type.value,
                severity=hit.severity, trigger=hit.trigger,
            )

    return graph
