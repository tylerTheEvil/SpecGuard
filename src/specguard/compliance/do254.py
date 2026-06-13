"""Representative codification of DO-254 objectives.

DO-254 governs Design Assurance for Airborne Electronic Hardware (FPGA,
ASIC, complex PLDs). This subset focuses on Section 6 (Validation and
Verification Processes) — the area most directly comparable to DO-178C
software verification, demonstrating cross-domain compliance binding.

Subset selection:
    - Section 6.2: Hardware design verification — 2 obj
    - Section 6.3: Validation of derived hardware requirements — 2 obj
    - Section 6.4: Verification compliance with the specifications — 1 obj

Disclaimer: same as DO-178C — illustrative codification, requires DER
validation before certification use. Full DO-254 codification (~50 obj
across all sections) is separate research scope.
"""

from .constraint_engine import ComplianceConstraint

# ============================================================================
# Section 6.2 — Hardware Design Verification Process
# ============================================================================

DO_254_6_2_1 = ComplianceConstraint(
    objective_id="DO-254-6.2.1",
    standard="DO-254",
    table="6.2.1",
    title="Hardware requirements verification — completeness",
    description=(
        "Each hardware requirement (HWR) shall be verifiable; "
        "verification methods identified for each requirement."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (hwr:Requirement {level: 'HWR'})
        WHERE hwr.dal IN ['A', 'B', 'C']
          AND NOT EXISTS {
            MATCH (hwr)-[:VERIFIED_BY_METHOD]->(:VerificationMethod)
          }
        RETURN hwr.id AS violating_requirement,
               hwr.text AS req_text,
               hwr.dal AS dal_level,
               'no_verification_method' AS reason
    """,
    violation_template=(
        "HWR '{violating_requirement}' (DAL-{dal_level}) has no assigned "
        "verification method. DO-254 §6.2.1 requires verification method "
        "identified for each requirement."
    ),
    rationale=(
        "Codified as: every HWR must have outgoing VERIFIED_BY_METHOD edge "
        "to a VerificationMethod node (test, analysis, review, demonstration)."
    ),
)

DO_254_6_2_2 = ComplianceConstraint(
    objective_id="DO-254-6.2.2",
    standard="DO-254",
    table="6.2.2",
    title="Hardware requirement traceability to system requirements",
    description=(
        "Each HWR shall be traceable to higher-level system requirements "
        "or derived from them with documented rationale."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (hwr:Requirement {level: 'HWR'})
        WHERE NOT EXISTS {
          MATCH (hwr)-[:DERIVES_FROM|TRACES_TO]->(:Requirement {level: 'system'})
        }
          AND NOT (hwr.is_derived = true AND EXISTS {
            MATCH (hwr)-[:DERIVED_FROM_RATIONALE]->(:Rationale)
          })
        RETURN hwr.id AS violating_requirement,
               hwr.text AS req_text,
               'no_traceability_or_rationale' AS reason
    """,
    violation_template=(
        "HWR '{violating_requirement}' has neither system traceability nor "
        "derivation rationale. DO-254 §6.2.2 requires one or the other."
    ),
    rationale=(
        "Codified as: HWR is valid if either (a) traces to system req, OR "
        "(b) is_derived=true AND has rationale node. Otherwise — orphan."
    ),
)


# ============================================================================
# Section 6.3 — Validation of Derived Requirements
# ============================================================================

DO_254_6_3_1 = ComplianceConstraint(
    objective_id="DO-254-6.3.1",
    standard="DO-254",
    table="6.3.1",
    title="Derived requirements documented with rationale",
    description=(
        "Derived requirements (created during design, not flowing from "
        "system requirements) shall be documented with rationale and "
        "validated against system safety analysis."
    ),
    applicable_dal=["A", "B"],
    cypher_query="""
        MATCH (hwr:Requirement {level: 'HWR'})
        WHERE hwr.is_derived = true
          AND NOT EXISTS {
            MATCH (hwr)-[:DERIVED_FROM_RATIONALE]->(:Rationale)
          }
        RETURN hwr.id AS violating_requirement,
               hwr.text AS req_text,
               'derived_without_rationale' AS reason
    """,
    violation_template=(
        "Derived HWR '{violating_requirement}' lacks documented rationale. "
        "DO-254 §6.3.1 requires rationale for derived requirements."
    ),
    rationale="Critical for FPGA: derived requirements without rationale → audit fail.",
)

DO_254_6_3_2 = ComplianceConstraint(
    objective_id="DO-254-6.3.2",
    standard="DO-254",
    table="6.3.2",
    title="Derived requirements impact on system safety assessed",
    description=(
        "Each derived hardware requirement shall be evaluated for its "
        "impact on system safety; ARP4761-style safety assessment required."
    ),
    applicable_dal=["A", "B"],
    cypher_query="""
        MATCH (hwr:Requirement {level: 'HWR'})
        WHERE hwr.is_derived = true
          AND hwr.dal IN ['A', 'B']
          AND NOT EXISTS {
            MATCH (hwr)-[:SAFETY_ASSESSED_BY]->(:SafetyAnalysis)
          }
        RETURN hwr.id AS violating_requirement,
               hwr.text AS req_text,
               hwr.dal AS dal_level,
               'no_safety_assessment' AS reason
    """,
    violation_template=(
        "Derived DAL-{dal_level} HWR '{violating_requirement}' lacks safety "
        "impact assessment. DO-254 §6.3.2 requires ARP4761-style analysis."
    ),
    rationale=(
        "Cross-references ARP4761 safety analysis — derived requirements "
        "must be assessed for system-level safety impact."
    ),
)


# ============================================================================
# Section 6.4 — Verification Compliance
# ============================================================================

DO_254_6_4_1 = ComplianceConstraint(
    objective_id="DO-254-6.4.1",
    standard="DO-254",
    table="6.4.1",
    title="Verification activities compliant with hardware design",
    description=(
        "Verification results shall demonstrate that the hardware design "
        "implementation satisfies the hardware requirements."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (hwr:Requirement {level: 'HWR'})
        WHERE hwr.dal IN ['A', 'B']
          AND NOT EXISTS {
            MATCH (hwr)<-[:VERIFIES]-(:TestCase {status: 'passed'})
          }
          AND NOT EXISTS {
            MATCH (hwr)<-[:VERIFIES]-(:Assertion {status: 'proven'})
          }
        RETURN hwr.id AS violating_requirement,
               hwr.dal AS dal_level,
               'no_passing_verification' AS reason
    """,
    violation_template=(
        "DAL-{dal_level} HWR '{violating_requirement}' has no passing "
        "verification artifact (test or formal assertion). DO-254 §6.4.1."
    ),
    rationale=(
        "Verification result must show success: either passing TestCase "
        "or proven Assertion with VERIFIES edge."
    ),
)


# ============================================================================
# Aggregated subset
# ============================================================================

DO_254_OBJECTIVES = [
    DO_254_6_2_1,
    DO_254_6_2_2,
    DO_254_6_3_1,
    DO_254_6_3_2,
    DO_254_6_4_1,
]

assert len(DO_254_OBJECTIVES) == 5, "Expected 5 representative DO-254 objectives"
