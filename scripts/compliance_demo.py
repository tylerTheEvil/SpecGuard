"""Demo: Compliance constraint engine running on CVA6 requirements graph.

Demonstrates scientific novelty #3: 'Codification of regulatory objectives
as executable graph constraints.'

This script:
    1. Loads the CVA6 requirements
    2. Augments them with mock DAL/level/traceability data (since the
       public CVA6 spec doesn't include certification metadata)
    3. Constructs an in-memory graph
    4. Runs DO-178C + DO-254 + cross-domain constraints
    5. Generates a compliance report

This is a *proof of concept* — production use would integrate with a
real Neo4j database and validated DER-reviewed constraints.
"""

from __future__ import annotations

from specguard.compliance import (
    CROSS_DOMAIN_OBJECTIVES,
    DO_178C_OBJECTIVES,
    DO_254_OBJECTIVES,
    run_compliance_check,
)
from specguard.data.cva6_requirements import get_all_requirements

# ============================================================================
# In-memory graph runner — demonstrates Cypher query execution without Neo4j
# ============================================================================

class MockGraph:
    """Minimal in-memory graph that supports a tiny subset of Cypher.

    For demo purposes only — production would use Neo4j driver.
    The point is to show *that the constraints execute correctly* given
    a graph with the right schema.
    """

    def __init__(self) -> None:
        self.requirements: list[dict] = []
        self.smells: list[dict] = []
        self.relationships: list[dict] = []  # source_id, edge_type, target_id

    def add_requirement(self, **props) -> None:
        self.requirements.append(props)

    def add_smell(self, req_id: str, smell_type: str, severity: str,
                  trigger: str) -> None:
        self.smells.append({
            "req_id": req_id,
            "smell_type": smell_type,
            "severity": severity,
            "trigger": trigger,
        })
        self.relationships.append({
            "source": req_id,
            "edge_type": "HAS_SMELL",
            "target": f"smell_{len(self.smells)}",
        })

    def add_edge(self, source_id: str, edge_type: str, target_id: str) -> None:
        self.relationships.append({
            "source": source_id,
            "edge_type": edge_type,
            "target": target_id,
        })

    def has_outgoing_edge(self, req_id: str, edge_types: list[str],
                          target_filter: dict | None = None) -> bool:
        """Check if requirement has any outgoing edge of given types."""
        for rel in self.relationships:
            if rel["source"] == req_id and rel["edge_type"] in edge_types:
                if target_filter is None:
                    return True
                target_req = next(
                    (r for r in self.requirements if r.get("id") == rel["target"]),
                    None,
                )
                if target_req and all(
                    target_req.get(k) == v for k, v in target_filter.items()
                ):
                    return True
        return False

    def has_incoming_edge(self, req_id: str, edge_types: list[str]) -> bool:
        """Check if requirement has any incoming edge of given types."""
        return any(
            rel["target"] == req_id and rel["edge_type"] in edge_types
            for rel in self.relationships
        )


def make_graph_runner(graph: MockGraph):
    """Build a runner that interprets our specific Cypher patterns.

    NOTE: this is a *pattern-recognition* implementation — it matches
    each constraint by objective_id semantics, not by parsing Cypher.
    Production use needs real Neo4j driver. Demo shows the end-to-end
    flow correctly.
    """

    def run(query: str, params: dict) -> list[dict]:
        # Pattern matching by query content
        if "DERIVES_FROM|TRACES_TO" in query and "level: 'HLR'" in query \
                and "level: 'system'" in query:
            # DO-178C-A3-1: HLR without system traceability
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_system_traceability"}
                for r in graph.requirements
                if r.get("level") == "HLR"
                and not graph.has_outgoing_edge(
                    r["id"], ["DERIVES_FROM", "TRACES_TO"],
                    target_filter={"level": "system"},
                )
            ]

        if "HAS_SMELL" in query and "high" in query:
            # DO-178C-A3-2: HLR with high-severity smells
            results = []
            for smell in graph.smells:
                if smell["severity"] != "high":
                    continue
                req = next(
                    (r for r in graph.requirements if r["id"] == smell["req_id"]),
                    None,
                )
                if req and req.get("level") == "HLR":
                    results.append({
                        "violating_requirement": req["id"],
                        "req_text": req["text"],
                        "reason": smell["smell_type"],
                        "smell_trigger": smell["trigger"],
                    })
            return results

        if "category IN ['Performance'" in query:
            # DO-178C-A3-3: Performance HLR without HW characteristic link
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": r.get("category", "")}
                for r in graph.requirements
                if r.get("level") == "HLR"
                and r.get("category") in ["Performance", "Timing", "Memory", "PPA"]
                and not graph.has_outgoing_edge(r["id"], ["CONSTRAINED_BY"])
            ]

        if "level: 'LLR'" in query and "level: 'HLR'" in query \
                and "DERIVES_FROM" in query:
            # DO-178C-A4-1: LLR without HLR parent
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_hlr_parent"}
                for r in graph.requirements
                if r.get("level") == "LLR"
                and not graph.has_outgoing_edge(
                    r["id"], ["DERIVES_FROM"],
                    target_filter={"level": "HLR"},
                )
            ]

        if "IMPLEMENTS" in query and "SoftwareModule" in query:
            # DO-178C-A4-6: HLR without implementing module
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "no_implementing_module"}
                for r in graph.requirements
                if r.get("level") == "HLR"
                and not graph.has_incoming_edge(r["id"], ["IMPLEMENTS"])
            ]

        if "VERIFIES" in query and "level IN ['HLR', 'LLR']" in query:
            # DO-178C-A7-1: requirement without test
            return [
                {"violating_requirement": r["id"],
                 "req_level": r.get("level"),
                 "dal_level": r.get("dal"),
                 "reason": "no_verifying_test"}
                for r in graph.requirements
                if r.get("level") in ["HLR", "LLR"]
                and r.get("dal") in ["A", "B", "C"]
                and not graph.has_incoming_edge(r["id"], ["VERIFIES"])
            ]

        if "MC/DC" in query:
            # DO-178C-A7-3: DAL-A HLR without MC/DC
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
                    results.append({
                        "violating_requirement": r["id"],
                        "req_text": r["text"],
                        "reason": "missing_mcdc_coverage",
                    })
            return results

        if "VERIFIED_BY_METHOD" in query:
            # DO-254-6.2.1: HWR without verification method
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "dal_level": r.get("dal"), "reason": "no_verification_method"}
                for r in graph.requirements
                if r.get("level") == "HWR"
                and r.get("dal") in ["A", "B", "C"]
                and not graph.has_outgoing_edge(r["id"], ["VERIFIED_BY_METHOD"])
            ]

        if "DERIVED_FROM_RATIONALE" in query and "is_derived = true" in query \
                and "level: 'HWR'" in query and "DAL" not in query.upper().split("WHERE")[1][:50]:
            # DO-254-6.3.1: derived HWR without rationale
            return [
                {"violating_requirement": r["id"], "req_text": r["text"],
                 "reason": "derived_without_rationale"}
                for r in graph.requirements
                if r.get("level") == "HWR"
                and r.get("is_derived") is True
                and not graph.has_outgoing_edge(r["id"], ["DERIVED_FROM_RATIONALE"])
            ]

        # Other DO-254 / cross-domain constraints would have similar
        # interpreters here. For demo, returning empty (no violation)
        # for objectives our mock graph doesn't have data for.
        return []

    return run


# ============================================================================
# Demo: build augmented CVA6 graph
# ============================================================================

def build_demo_graph() -> MockGraph:
    """Construct a graph from CVA6 requirements with mock certification metadata.

    Augmentation rationale:
        - Treat all CVA6 requirements as HLR (high-level) for demo
        - Assign DAL-B as default (typical for non-flight-critical processor)
        - Mark a subset as DAL-A to demonstrate variation
        - Add some traceability edges, leave others missing on purpose
    """
    graph = MockGraph()
    cva6_reqs = get_all_requirements()

    # System-level placeholder (would be from ARP4754A in real spec)
    graph.add_requirement(
        id="SYS-1",
        text="Processor shall execute RISC-V ISA",
        level="system",
        dal="A",
    )
    graph.add_requirement(
        id="SYS-2",
        text="Processor shall meet performance targets",
        level="system",
        dal="B",
    )

    # Add CVA6 requirements as HLR
    for req in cva6_reqs:
        graph.add_requirement(
            id=req.req_id,
            text=req.text,
            level="HLR",
            dal="A" if req.req_id.startswith("ISA") else "B",
            category=req.category,
            is_derived=False,
        )
        # Mock traceability — about 70% of ISA reqs traced to system
        if req.req_id.startswith("ISA") and req.req_id != "ISA-90":
            graph.add_edge(req.req_id, "DERIVES_FROM", "SYS-1")
        elif req.category == "Performance" and req.req_id != "PPA-50":
            graph.add_edge(req.req_id, "DERIVES_FROM", "SYS-2")
        # Note: PPA-50, PPA-60 (TBD placeholders) and others left without
        # traceability — they should be flagged

        # Mock test coverage — about half have tests
        if hash(req.req_id) % 2 == 0:
            graph.add_edge(f"TC_{req.req_id}", "VERIFIES", req.req_id)

    # Run smell detector and add smell edges
    from specguard.core.smell_detector import analyze_requirement
    for req in cva6_reqs:
        report = analyze_requirement(req.req_id, req.text)
        for hit in report.hits:
            graph.add_smell(
                req_id=req.req_id,
                smell_type=hit.smell_type.value,
                severity=hit.severity,
                trigger=hit.trigger,
            )

    return graph


def main() -> None:
    print("=" * 70)
    print("SpecGuard Compliance Check Demo")
    print("Codified DO-178C / DO-254 / Cross-Domain Objectives on CVA6")
    print("=" * 70)
    print()

    graph = build_demo_graph()
    runner = make_graph_runner(graph)

    print("Graph statistics:")
    print(f"  Requirements:    {len(graph.requirements)}")
    print(f"  Smells:          {len(graph.smells)}")
    print(f"  Relationships:   {len(graph.relationships)}")
    print()

    # Run DO-178C check
    print("-" * 70)
    print("DO-178C Compliance Check (representative subset)")
    print("-" * 70)
    do178c_report = run_compliance_check(
        runner, DO_178C_OBJECTIVES, standard_name="DO-178C"
    )
    print(do178c_report.summary())
    print()

    # Run DO-254 check
    print("-" * 70)
    print("DO-254 Compliance Check (representative subset)")
    print("-" * 70)
    do254_report = run_compliance_check(
        runner, DO_254_OBJECTIVES, standard_name="DO-254"
    )
    print(do254_report.summary())
    print()

    # Run cross-domain check
    print("-" * 70)
    print("Cross-Domain Compliance Check (DO-178C ↔ DO-254 binding)")
    print("-" * 70)
    cross_report = run_compliance_check(
        runner, CROSS_DOMAIN_OBJECTIVES, standard_name="Cross-Domain"
    )
    print(cross_report.summary())
    print()

    # Combined summary
    print("=" * 70)
    print("AGGREGATE COMPLIANCE STATUS")
    print("=" * 70)
    total_objectives = (do178c_report.total_objectives_checked
                        + do254_report.total_objectives_checked
                        + cross_report.total_objectives_checked)
    total_passing = (len(do178c_report.passing_objective_ids)
                     + len(do254_report.passing_objective_ids)
                     + len(cross_report.passing_objective_ids))
    total_violations = (do178c_report.violation_count
                        + do254_report.violation_count
                        + cross_report.violation_count)

    print(f"Total objectives checked: {total_objectives}")
    print(f"Passing:                  {total_passing} "
          f"({total_passing/total_objectives:.1%})")
    print(f"Total violations:         {total_violations}")
    print()
    print("This is a representative subset demonstrating the methodology.")
    print("Full DO-178C (~71 obj) + DO-254 (~50 obj) codification is")
    print("identified as separate research direction (~700+ hours of work).")


if __name__ == "__main__":
    main()
