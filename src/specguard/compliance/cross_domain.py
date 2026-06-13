"""Cross-domain compliance objectives — DO-178C ↔ DO-254 binding.

This is the *unique research niche* of the dissertation: regulatory
objectives that bind software (DO-178C) and hardware/FPGA (DO-254)
sides of a safety-critical system together.

Existing literature focuses on either:
    - Software side: Zrelli 2026, Ribeiro 2025, Masoudifard 2024
    - Hardware side: AssertionForge 2025, Saarthi 2025
    - But not the binding between them.

This binding is required by ARP4754A (system-level guidance) and
implicit in certification evidence packages — auditors check that
hardware-software interfaces are coherently specified across both sides.

These objectives demonstrate the cross-domain niche even if not
directly numbered in either standard — they encode binding requirements
that emerge at the system level.
"""

from .constraint_engine import ComplianceConstraint

CROSS_HW_SW_INTERFACE = ComplianceConstraint(
    objective_id="CROSS-HW-SW-1",
    standard="ARP4754A+DO-178C+DO-254",
    table="cross-domain",
    title="Hardware-software interface requirements coherent",
    description=(
        "Every hardware-software interface (e.g. memory-mapped register, "
        "interrupt, DMA channel) shall be specified consistently in both "
        "software (DO-178C) and hardware (DO-254) requirements; mismatched "
        "specifications indicate integration risk."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (sw:Requirement {level: 'HLR'})-[:MENTIONS]->(iface:Interface),
              (hw:Requirement {level: 'HWR'})-[:MENTIONS]->(iface)
        WHERE NOT EXISTS {
          MATCH (sw)-[:CONSISTENT_WITH]->(hw)
        }
        RETURN sw.id + ' <-> ' + hw.id AS violating_requirement,
               iface.name AS shared_interface,
               'unconfirmed_consistency' AS reason
    """,
    violation_template=(
        "SW HLR and HW HWR both reference interface '{shared_interface}' "
        "but consistency is not asserted (no CONSISTENT_WITH edge). "
        "Cross-domain coherence required by ARP4754A §5."
    ),
    rationale=(
        "Detects pairs of SW/HW requirements mentioning the same interface "
        "without explicit consistency assertion — a class of integration "
        "defects that often slips through single-domain verification."
    ),
)

CROSS_TIMING_BUDGET = ComplianceConstraint(
    objective_id="CROSS-TIMING-1",
    standard="ARP4754A+DO-178C+DO-254",
    table="cross-domain",
    title="Timing budget allocations consistent across SW and HW",
    description=(
        "When system-level timing requirements are decomposed into "
        "software (latency) and hardware (clock speed, pipeline depth) "
        "components, the allocations must sum within the system budget."
    ),
    applicable_dal=["A", "B"],
    cypher_query="""
        MATCH (sysreq:Requirement {level: 'system'})
        WHERE sysreq.timing_budget_ns IS NOT NULL
          AND EXISTS {
            MATCH (sysreq)<-[:DERIVES_FROM]-(:Requirement {level: 'HLR'})
          }
          AND EXISTS {
            MATCH (sysreq)<-[:DERIVES_FROM]-(:Requirement {level: 'HWR'})
          }
        WITH sysreq,
             [(sysreq)<-[:DERIVES_FROM]-(sw:Requirement {level: 'HLR'})
              | sw.timing_budget_ns] AS sw_budgets,
             [(sysreq)<-[:DERIVES_FROM]-(hw:Requirement {level: 'HWR'})
              | hw.timing_budget_ns] AS hw_budgets
        WITH sysreq, sw_budgets + hw_budgets AS allocated_budgets,
             sysreq.timing_budget_ns AS budget
        WHERE reduce(s = 0, b IN allocated_budgets | s + coalesce(b, 0)) > budget
        RETURN sysreq.id AS violating_requirement,
               sysreq.timing_budget_ns AS budget,
               reduce(s = 0, b IN allocated_budgets | s + coalesce(b, 0))
                 AS allocated,
               'budget_overrun' AS reason
    """,
    violation_template=(
        "System requirement '{violating_requirement}' has timing budget "
        "{budget} ns, but allocations to SW+HW sum to {allocated} ns. "
        "Budget overrun in cross-domain allocation."
    ),
    rationale=(
        "Cross-domain numerical consistency check: aggregates timing "
        "budgets across SW (HLR) and HW (HWR) children of a system req, "
        "flags overruns. This is the kind of error that single-domain "
        "tools cannot detect."
    ),
)

CROSS_SAFETY_PROPAGATION = ComplianceConstraint(
    objective_id="CROSS-SAFETY-1",
    standard="ARP4761+DO-178C+DO-254",
    table="cross-domain",
    title="Safety hazards propagated to both SW and HW requirements",
    description=(
        "System-level safety hazards (from ARP4761 functional hazard "
        "assessment) shall propagate to mitigations in both software "
        "and hardware requirements where applicable."
    ),
    applicable_dal=["A", "B"],
    cypher_query="""
        MATCH (haz:SafetyHazard)
        WHERE haz.severity IN ['catastrophic', 'hazardous']
          AND haz.mitigation_domain IN ['both', 'sw_and_hw']
          AND NOT (
            EXISTS {
              MATCH (haz)<-[:MITIGATES]-(:Requirement {level: 'HLR'})
            }
            AND EXISTS {
              MATCH (haz)<-[:MITIGATES]-(:Requirement {level: 'HWR'})
            }
          )
        RETURN haz.id AS violating_requirement,
               haz.description AS hazard_text,
               haz.severity AS severity,
               'incomplete_mitigation_coverage' AS reason
    """,
    violation_template=(
        "Safety hazard '{violating_requirement}' (severity: {severity}) "
        "requires both SW and HW mitigation but lacks one or both. "
        "ARP4761 + DO-178C/DO-254 cross-domain mitigation."
    ),
    rationale=(
        "Catastrophic/hazardous safety hazards that require dual-domain "
        "mitigation (e.g. defense-in-depth) must have requirements on "
        "BOTH sides. Single-domain mitigation insufficient for highest "
        "severity classifications."
    ),
)


CROSS_DOMAIN_OBJECTIVES = [
    CROSS_HW_SW_INTERFACE,
    CROSS_TIMING_BUDGET,
    CROSS_SAFETY_PROPAGATION,
]

assert len(CROSS_DOMAIN_OBJECTIVES) == 3, "Expected 3 cross-domain objectives"
