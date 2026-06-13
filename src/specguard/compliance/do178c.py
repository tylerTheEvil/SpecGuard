"""Representative codification of DO-178C objectives.

This is a *demonstration subset* of DO-178C objectives — not the full
set of ~71. Selected to cover:
    - Table A-3 (HLR verification) — 3 representative obj
    - Table A-4 (LLR verification) — 2 representative obj
    - Table A-7 (Verification of verification) — 2 representative obj

Rationale for subset selection:
    - Each table represented to demonstrate methodology breadth
    - Objectives chosen where graph schema directly supports verification
    - Cross-DAL applicability (some apply DAL A only, some all)

Disclaimer: full DO-178C codification (all 10 tables, ~71 obj) is
identified as separate research direction in the dissertation roadmap.
The Cypher patterns below are illustrative interpretations and would
require validation by Designated Engineering Representatives (DERs)
before use in actual certification workflows.
"""

from .constraint_engine import ComplianceConstraint

# ============================================================================
# Table A-3 — Verification of Outputs of Software Requirements Process
# (High-Level Requirements verification)
# ============================================================================

DO_178C_A3_1 = ComplianceConstraint(
    objective_id="DO-178C-A3-1",
    standard="DO-178C",
    table="A-3",
    title="High-level requirements comply with system requirements",
    description=(
        "High-level requirements are developed that comply with "
        "the allocated system requirements."
    ),
    applicable_dal=["A", "B", "C", "D"],
    cypher_query="""
        MATCH (hlr:Requirement {level: 'HLR'})
        WHERE NOT EXISTS {
          MATCH (hlr)-[:DERIVES_FROM|TRACES_TO]->(:Requirement {level: 'system'})
        }
        RETURN hlr.id AS violating_requirement,
               hlr.text AS req_text,
               'no_system_traceability' AS reason
    """,
    violation_template=(
        "HLR '{violating_requirement}' lacks traceability to system requirement. "
        "Required by DO-178C Table A-3 obj 1."
    ),
    rationale=(
        "Codified as: every HLR must have at least one DERIVES_FROM or "
        "TRACES_TO edge to a system-level requirement. Missing edge → violation."
    ),
)

DO_178C_A3_2 = ComplianceConstraint(
    objective_id="DO-178C-A3-2",
    standard="DO-178C",
    table="A-3",
    title="High-level requirements are accurate and consistent",
    description=(
        "High-level requirements are accurate, unambiguous, and "
        "sufficiently detailed; conflicts between HLR are resolved."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (hlr:Requirement {level: 'HLR'})-[:HAS_SMELL]->(s:Smell)
        WHERE s.severity = 'high'
        RETURN hlr.id AS violating_requirement,
               hlr.text AS req_text,
               s.smell_type AS reason,
               s.trigger AS smell_trigger
    """,
    violation_template=(
        "HLR '{violating_requirement}' has high-severity {reason} smell "
        "(trigger: '{smell_trigger}'). DO-178C A-3 obj 2 requires accurate "
        "and unambiguous requirements."
    ),
    rationale=(
        "Codified as: HLR with high-severity smells (vagueness, ambiguity, "
        "placeholder) violate accuracy/consistency requirement. SpecGuard "
        "smell detector provides the deterministic basis."
    ),
)

DO_178C_A3_3 = ComplianceConstraint(
    objective_id="DO-178C-A3-3",
    standard="DO-178C",
    table="A-3",
    title="High-level requirements are compatible with target computer",
    description=(
        "HLR are verifiable against the target computer hardware "
        "characteristics (timing, memory, I/O constraints)."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (hlr:Requirement {level: 'HLR'})
        WHERE hlr.category IN ['Performance', 'Timing', 'Memory']
          AND NOT EXISTS {
            MATCH (hlr)-[:CONSTRAINED_BY]->(:HardwareCharacteristic)
          }
        RETURN hlr.id AS violating_requirement,
               hlr.text AS req_text,
               hlr.category AS reason
    """,
    violation_template=(
        "Performance/timing/memory HLR '{violating_requirement}' lacks "
        "linkage to target hardware characteristics. DO-178C A-3 obj 3."
    ),
    rationale=(
        "Codified as: HLR in performance-critical categories must reference "
        "specific hardware constraints. Otherwise verifiability against "
        "target computer is undefined."
    ),
)


# ============================================================================
# Table A-4 — Verification of Outputs of Software Design Process
# (Low-Level Requirements verification)
# ============================================================================

DO_178C_A4_1 = ComplianceConstraint(
    objective_id="DO-178C-A4-1",
    standard="DO-178C",
    table="A-4",
    title="Low-level requirements comply with high-level requirements",
    description=(
        "LLR developed during software design comply with HLR; "
        "every LLR is traceable to at least one HLR."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (llr:Requirement {level: 'LLR'})
        WHERE NOT EXISTS {
          MATCH (llr)-[:DERIVES_FROM]->(:Requirement {level: 'HLR'})
        }
        RETURN llr.id AS violating_requirement,
               llr.text AS req_text,
               'no_hlr_parent' AS reason
    """,
    violation_template=(
        "LLR '{violating_requirement}' has no parent HLR — orphan requirement. "
        "DO-178C A-4 obj 1 requires LLR-to-HLR traceability."
    ),
    rationale="Codified as: bidirectional traceability check via DERIVES_FROM edge.",
)

DO_178C_A4_6 = ComplianceConstraint(
    objective_id="DO-178C-A4-6",
    standard="DO-178C",
    table="A-4",
    title="Software architecture is consistent with high-level requirements",
    description=(
        "Software architecture (modules, interfaces) covers all HLR; "
        "no HLR is left without architectural realization."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (hlr:Requirement {level: 'HLR'})
        WHERE NOT EXISTS {
          MATCH (hlr)<-[:IMPLEMENTS]-(:SoftwareModule)
        }
          AND NOT EXISTS {
          MATCH (hlr)<-[:IMPLEMENTS]-(:HDLModule)
        }
        RETURN hlr.id AS violating_requirement,
               hlr.text AS req_text,
               'no_implementing_module' AS reason
    """,
    violation_template=(
        "HLR '{violating_requirement}' has no implementing module "
        "(software or HDL). DO-178C A-4 obj 6: architecture must cover all HLR."
    ),
    rationale="Coverage check: every HLR must have at least one IMPLEMENTS edge incoming.",
)


# ============================================================================
# Table A-7 — Verification of Verification Process Results
# ============================================================================

DO_178C_A7_1 = ComplianceConstraint(
    objective_id="DO-178C-A7-1",
    standard="DO-178C",
    table="A-7",
    title="Test procedures are correct",
    description=(
        "Test procedures verify high-level and low-level requirements; "
        "every requirement has at least one verifying test case."
    ),
    applicable_dal=["A", "B", "C"],
    cypher_query="""
        MATCH (r:Requirement)
        WHERE r.level IN ['HLR', 'LLR']
          AND r.dal IN ['A', 'B', 'C']
          AND NOT EXISTS {
            MATCH (r)<-[:VERIFIES]-(:TestCase)
          }
        RETURN r.id AS violating_requirement,
               r.level AS req_level,
               r.dal AS dal_level,
               'no_verifying_test' AS reason
    """,
    violation_template=(
        "{req_level} '{violating_requirement}' (DAL-{dal_level}) has no "
        "verifying test case. DO-178C A-7 obj 1: every requirement must be "
        "tested."
    ),
    rationale="Test coverage check: incoming VERIFIES edge from TestCase node required.",
)

DO_178C_A7_3 = ComplianceConstraint(
    objective_id="DO-178C-A7-3",
    standard="DO-178C",
    table="A-7",
    title="Test coverage of high-level requirements is achieved",
    description=(
        "Test coverage analysis confirms that all HLR are exercised; "
        "for DAL-A specifically, MC/DC coverage is required."
    ),
    applicable_dal=["A", "B"],
    cypher_query="""
        MATCH (hlr:Requirement {level: 'HLR'})
        WHERE hlr.dal = 'A'
          AND NOT EXISTS {
            MATCH (hlr)<-[v:VERIFIES]-(:TestCase)
            WHERE v.coverage_type = 'MC/DC'
          }
        RETURN hlr.id AS violating_requirement,
               hlr.text AS req_text,
               'missing_mcdc_coverage' AS reason
    """,
    violation_template=(
        "DAL-A HLR '{violating_requirement}' lacks MC/DC test coverage. "
        "DO-178C A-7 obj 3 (DAL-A specific)."
    ),
    rationale="DAL-A specific: VERIFIES edge must have coverage_type='MC/DC'.",
)


# ============================================================================
# Aggregated subset — all DO-178C objectives codified for demo
# ============================================================================

DO_178C_OBJECTIVES = [
    DO_178C_A3_1,
    DO_178C_A3_2,
    DO_178C_A3_3,
    DO_178C_A4_1,
    DO_178C_A4_6,
    DO_178C_A7_1,
    DO_178C_A7_3,
]

assert len(DO_178C_OBJECTIVES) == 7, "Expected 7 representative objectives"
