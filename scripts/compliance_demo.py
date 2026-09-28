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

# ============================================================================
# In-memory graph runner — demonstrates Cypher query execution without Neo4j
# ============================================================================
from specguard.compliance.memory_runner import build_demo_graph, make_graph_runner


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

    print("SYNTHETIC demo metadata; unreviewed scope remains UNKNOWN.")
    print("No whole-standard compliance percentage is computed.")


if __name__ == "__main__":
    main()
