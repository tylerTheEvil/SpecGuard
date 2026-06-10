"""Load the SpecGuard knowledge graph + MOCK compliance metadata into Neo4j.

Phase 1a of the evidence-hardening plan. This script makes the 15 codified
regulatory objectives (7 DO-178C + 5 DO-254 + 3 cross-domain) actually
executable against a real Neo4j instance, rather than the in-memory
pattern-matching runner used by ``scripts/compliance_demo.py``.

What it does
------------
1. **Clears** the target database (the graph is fully reproducible from the
   repository, so a destructive reload is acceptable).
2. **Builds** the base CVA6 requirements graph deterministically via
   :mod:`specguard.graph.builder` (64 requirements + components / standards /
   configurations / smells) and writes it to Neo4j. Each ``Requirement`` node
   is given an ``id`` property equal to its ``req_id`` so the constraint
   queries (which match on ``r.id``) resolve.
3. **Adds MOCK compliance metadata** required by the 15 queries:
   DAL assignments, requirement ``level`` (system / HLR / LLR / HWR),
   traceability edges, ``TestCase`` / ``VerificationMethod`` /
   ``SoftwareModule`` nodes, ``Interface`` / ``SafetyHazard`` /
   ``Rationale`` / ``SafetyAnalysis`` / ``Assertion`` nodes, timing budgets,
   and the cross-domain SW<->HW binding edges.

HONESTY (per CLAUDE.md)
-----------------------
The compliance metadata added here is **entirely MOCK**. The public CVA6
specification contains no certification data (no DAL assignments, no
HLR/LLR/HWR decomposition, no traceability or verification evidence). This
synthetic metadata exists solely to **demonstrate that the codified Cypher
patterns execute and discriminate** on a graph that has the schema they
assume. It deliberately seeds *both* compliant cases and violations so that
each objective demonstrates discrimination, not just firing. It is NOT
certification evidence and must not be presented as such.

Run::

    .venv/bin/python scripts/load_neo4j.py

Connection defaults target the local DBMS and are overridable via the
SPECGUARD_NEO4J_* environment variables (see neo4j_runner.Neo4jConfig).
"""

from __future__ import annotations

from specguard.compliance.neo4j_runner import Neo4jConfig, Neo4jGraphRunner
from specguard.core import assess_dataset
from specguard.data.cva6_requirements import get_all_requirements
from specguard.graph.builder import build_graph

# ---------------------------------------------------------------------------
# Mock metadata definitions
# ---------------------------------------------------------------------------

# System-level requirements (would come from ARP4754A allocation in reality).
# SYS-3 carries a timing budget so the cross-domain timing objective has data.
SYSTEM_REQUIREMENTS = [
    {"id": "SYS-1", "text": "Processor shall execute the RISC-V ISA.",
     "level": "system", "dal": "A"},
    {"id": "SYS-2", "text": "Processor shall meet performance targets.",
     "level": "system", "dal": "B"},
    {"id": "SYS-3", "text": "Load-to-use memory access shall complete within budget.",
     "level": "system", "dal": "A", "timing_budget_ns": 100},
    {"id": "SYS-4", "text": "Store path shall complete within budget.",
     "level": "system", "dal": "A", "timing_budget_ns": 50},
]

# Hardware requirements (HWR) — the FPGA/DO-254 side. These are MOCK additions
# layered on top of the CVA6 (which the dissertation treats as the HW anchor).
# Fields: id, text, dal, is_derived, timing_budget_ns (optional),
#         derives_from (system id), has_method, has_rationale,
#         has_safety_assessment, has_passing_verification.
HARDWARE_REQUIREMENTS = [
    # Compliant HWR: traced, verified, derived-with-rationale where needed.
    {"id": "HWR-10", "text": "Cache controller shall service load within 80 ns.",
     "dal": "A", "is_derived": False, "timing_budget_ns": 60,
     "derives_from": "SYS-3", "has_method": True, "has_safety_assessment": True,
     "has_passing_verification": True},
    {"id": "HWR-20", "text": "Store buffer shall drain within 40 ns.",
     "dal": "A", "is_derived": False, "timing_budget_ns": 40,
     "derives_from": "SYS-4", "has_method": True, "has_safety_assessment": True,
     "has_passing_verification": True},
    # Compliant derived HWR: has rationale + safety assessment.
    {"id": "HWR-30", "text": "ECC scrubber shall run every 1 ms (derived).",
     "dal": "A", "is_derived": True, "derives_from": None,
     "has_method": True, "has_rationale": True, "has_safety_assessment": True,
     "has_passing_verification": True},
    # VIOLATION DO-254-6.2.1: no verification method assigned.
    {"id": "HWR-40", "text": "Interrupt latency shall be bounded.",
     "dal": "A", "is_derived": False, "derives_from": "SYS-1",
     "has_method": False, "has_safety_assessment": True,
     "has_passing_verification": True},
    # VIOLATION DO-254-6.2.2 + 6.3.1: derived but no rationale, no trace.
    {"id": "HWR-50", "text": "Branch predictor table sized to 256 entries (derived).",
     "dal": "B", "is_derived": True, "derives_from": None,
     "has_method": True, "has_rationale": False, "has_safety_assessment": True,
     "has_passing_verification": True},
    # VIOLATION DO-254-6.3.2: derived DAL-A without safety assessment.
    {"id": "HWR-60", "text": "DMA burst length fixed at 16 (derived).",
     "dal": "A", "is_derived": True, "derives_from": None,
     "has_method": True, "has_rationale": True, "has_safety_assessment": False,
     "has_passing_verification": True},
    # VIOLATION DO-254-6.4.1: no passing verification artifact.
    {"id": "HWR-70", "text": "Clock gating shall reduce dynamic power.",
     "dal": "A", "is_derived": False, "derives_from": "SYS-2",
     "has_method": True, "has_safety_assessment": True,
     "has_passing_verification": False},
]

# Low-level requirements (LLR) — software design layer.
# HLR parent edge present => compliant for DO-178C-A4-1; absent => orphan.
LOW_LEVEL_REQUIREMENTS = [
    {"id": "LLR-10", "text": "Decode stage shall raise illegal-instruction trap.",
     "dal": "A", "derives_from_hlr": "ISA-10", "has_test": True},
    # VIOLATION DO-178C-A4-1: orphan LLR (no HLR parent).
    {"id": "LLR-20", "text": "Pipeline flush handler shall clear scoreboard.",
     "dal": "A", "derives_from_hlr": None, "has_test": True},
]

# Shared HW/SW interfaces for the cross-domain interface objective.
# A SW HLR and a HW HWR both MENTION the interface; CONSISTENT_WITH present
# => compliant, absent => violation.
INTERFACES = [
    {"name": "CSR_MMAP", "sw_req": "HPM-10", "hw_req": "HWR-10",
     "consistent": True},
    # VIOLATION CROSS-HW-SW-1: shared interface without CONSISTENT_WITH.
    {"name": "IRQ_LINE", "sw_req": "IRQ-10", "hw_req": "HWR-40",
     "consistent": False},
]

# Cross-domain timing decomposition. SW (HLR) + HW (HWR) children of a system
# requirement; sum compared against the system budget.
TIMING_DECOMP = [
    # Compliant: 30 (SW) + 60 (HW) = 90 <= 100 budget on SYS-3.
    {"sys": "SYS-3", "sw_req": "L1W-10", "sw_budget": 30,
     "hw_req": "HWR-10", "hw_budget": 60},
    # VIOLATION CROSS-TIMING-1: 30 (SW) + 40 (HW) = 70 > 50 budget on SYS-4.
    {"sys": "SYS-4", "sw_req": "L1W-20", "sw_budget": 30,
     "hw_req": "HWR-20", "hw_budget": 40},
]

# Safety hazards from a mock ARP4761 FHA. Dual-domain mitigation required for
# catastrophic/hazardous; present on both sides => compliant.
SAFETY_HAZARDS = [
    {"id": "HAZ-1", "description": "Undetected memory corruption propagates.",
     "severity": "catastrophic", "mitigation_domain": "both",
     "sw_mitigator": "HPM-10", "hw_mitigator": "HWR-30"},
    # VIOLATION CROSS-SAFETY-1: catastrophic, dual-domain required, HW side only.
    {"id": "HAZ-2", "description": "Stale cache line read after store.",
     "severity": "hazardous", "mitigation_domain": "both",
     "sw_mitigator": None, "hw_mitigator": "HWR-20"},
]


# ---------------------------------------------------------------------------
# Loading logic
# ---------------------------------------------------------------------------


def _clear_database(runner: Neo4jGraphRunner) -> None:
    """Delete every node and relationship in the target database."""
    runner("MATCH (n) DETACH DELETE n", {})


def _load_base_graph(runner: Neo4jGraphRunner) -> dict:
    """Build the CVA6 graph in memory and write it to Neo4j.

    Returns the builder's stats dict. Requirement nodes get both ``req_id``
    and ``id`` (the constraint queries match on ``.id``).
    """
    requirements = get_all_requirements()
    smell_results = assess_dataset(requirements)
    graph = build_graph(requirements, smell_results)

    # Nodes
    for node in graph.nodes:
        props = dict(node.properties)
        # Requirement nodes: expose `id` alias for the constraint queries.
        if node.label == "Requirement":
            props.setdefault("id", node.properties.get("req_id", node.node_id))
        runner(
            f"MERGE (n:{node.label} {{node_id: $node_id}}) SET n += $props",
            {"node_id": node.node_id, "props": props},
        )

    # Relationships
    for rel in graph.relationships:
        runner(
            f"""
            MATCH (a:{rel.from_label} {{node_id: $from_id}})
            MATCH (b:{rel.to_label} {{node_id: $to_id}})
            MERGE (a)-[:{rel.rel_type}]->(b)
            """,
            {"from_id": rel.from_id, "to_id": rel.to_id},
        )

    return graph.stats()


def _add_compliance_metadata(runner: Neo4jGraphRunner) -> None:
    """Add the MOCK certification metadata the 15 objectives assume.

    Mirrors the augmentation logic of ``scripts/compliance_demo.py`` for the
    DO-178C software side, then extends it with a hardware (HWR) layer,
    interfaces, hazards and timing decomposition so the DO-254 and
    cross-domain objectives execute against real data with seeded violations.
    """
    requirements = get_all_requirements()

    # --- Software side: tag CVA6 requirements as HLR with mock DAL/trace -----
    # Replicates compliance_demo.build_demo_graph():
    #   - all CVA6 reqs become HLR
    #   - ISA* => DAL-A, else DAL-B
    #   - ISA* (except ISA-90) DERIVES_FROM SYS-1
    #   - Performance category (except PPA-50) DERIVES_FROM SYS-2
    #   - ~half (hash%2==0) get a verifying TestCase
    for req in requirements:
        dal = "A" if req.req_id.startswith("ISA") else "B"
        runner(
            """
            MATCH (r:Requirement {node_id: $id})
            SET r.level = 'HLR', r.dal = $dal, r.is_derived = false
            """,
            {"id": req.req_id, "dal": dal},
        )

        if req.req_id.startswith("ISA") and req.req_id != "ISA-90":
            _merge_trace(runner, req.req_id, "SYS-1")
        elif req.category == "Performance" and req.req_id != "PPA-50":
            _merge_trace(runner, req.req_id, "SYS-2")

        if hash(req.req_id) % 2 == 0:
            _merge_test(runner, req.req_id, f"TC_{req.req_id}", coverage_type=None)

    # --- System requirements -------------------------------------------------
    for sys in SYSTEM_REQUIREMENTS:
        props = dict(sys)
        props["node_id"] = sys["id"]
        props["is_derived"] = False
        runner("MERGE (n:Requirement {node_id: $node_id}) SET n += $props", {
            "node_id": sys["id"], "props": props,
        })

    # --- Hardware requirements (HWR) -----------------------------------------
    for hw in HARDWARE_REQUIREMENTS:
        props = {
            "node_id": hw["id"], "id": hw["id"], "text": hw["text"],
            "level": "HWR", "dal": hw["dal"], "is_derived": hw["is_derived"],
        }
        if hw.get("timing_budget_ns") is not None:
            props["timing_budget_ns"] = hw["timing_budget_ns"]
        runner("MERGE (n:Requirement {node_id: $node_id}) SET n += $props",
               {"node_id": hw["id"], "props": props})

        if hw.get("derives_from"):
            _merge_trace(runner, hw["id"], hw["derives_from"])
        if hw.get("has_method"):
            runner(
                """
                MATCH (h:Requirement {node_id: $id})
                MERGE (m:VerificationMethod {node_id: $mid})
                  SET m.name = 'analysis'
                MERGE (h)-[:VERIFIED_BY_METHOD]->(m)
                """,
                {"id": hw["id"], "mid": f"VM_{hw['id']}"},
            )
        if hw.get("has_rationale"):
            runner(
                """
                MATCH (h:Requirement {node_id: $id})
                MERGE (rat:Rationale {node_id: $rid})
                  SET rat.text = 'Derived rationale (mock).'
                MERGE (h)-[:DERIVED_FROM_RATIONALE]->(rat)
                """,
                {"id": hw["id"], "rid": f"RAT_{hw['id']}"},
            )
        if hw.get("has_safety_assessment"):
            runner(
                """
                MATCH (h:Requirement {node_id: $id})
                MERGE (sa:SafetyAnalysis {node_id: $sid})
                  SET sa.method = 'ARP4761 (mock)'
                MERGE (h)-[:SAFETY_ASSESSED_BY]->(sa)
                """,
                {"id": hw["id"], "sid": f"SA_{hw['id']}"},
            )
        if hw.get("has_passing_verification"):
            runner(
                """
                MATCH (h:Requirement {node_id: $id})
                MERGE (tc:TestCase {node_id: $tid}) SET tc.status = 'passed'
                MERGE (tc)-[:VERIFIES]->(h)
                """,
                {"id": hw["id"], "tid": f"HWTC_{hw['id']}"},
            )

    # --- Low-level requirements (LLR) ----------------------------------------
    for llr in LOW_LEVEL_REQUIREMENTS:
        runner(
            """
            MERGE (n:Requirement {node_id: $id})
              SET n += {id: $id, text: $text, level: 'LLR',
                        dal: $dal, is_derived: false}
            """,
            {"id": llr["id"], "text": llr["text"], "dal": llr["dal"]},
        )
        if llr.get("derives_from_hlr"):
            runner(
                """
                MATCH (l:Requirement {node_id: $lid})
                MATCH (h:Requirement {node_id: $hid})
                MERGE (l)-[:DERIVES_FROM]->(h)
                """,
                {"lid": llr["id"], "hid": llr["derives_from_hlr"]},
            )
        if llr.get("has_test"):
            _merge_test(runner, llr["id"], f"TC_{llr['id']}", coverage_type=None)

    # --- Implementing modules (DO-178C-A4-6) ---------------------------------
    # Give a handful of HLR an IMPLEMENTS edge so the objective passes for
    # some and fires for the rest (demonstrates discrimination).
    for hlr_id in ("ISA-10", "ISA-20", "GEN-10", "PVL-10"):
        runner(
            """
            MATCH (h:Requirement {node_id: $id})
            MERGE (m:SoftwareModule {node_id: $mid}) SET m.name = $mid
            MERGE (m)-[:IMPLEMENTS]->(h)
            """,
            {"id": hlr_id, "mid": f"MOD_{hlr_id}"},
        )

    # --- MC/DC coverage (DO-178C-A7-3): give one DAL-A HLR MC/DC -------------
    runner(
        """
        MATCH (h:Requirement {node_id: 'ISA-10'})
        MERGE (tc:TestCase {node_id: 'MCDC_ISA-10'}) SET tc.status = 'passed'
        MERGE (tc)-[v:VERIFIES]->(h) SET v.coverage_type = 'MC/DC'
        """,
        {},
    )

    # --- HardwareCharacteristic links (DO-178C-A3-3) -------------------------
    # Link the performance counters HLR (HPM-10) so it passes; leave the rest
    # of Performance/Timing/Memory category unlinked => violations.
    runner(
        """
        MATCH (h:Requirement {node_id: 'HPM-10'})
        MERGE (hc:HardwareCharacteristic {node_id: 'HC_timing'})
          SET hc.name = 'cycle_counter_timing'
        MERGE (h)-[:CONSTRAINED_BY]->(hc)
        """,
        {},
    )

    # --- Interfaces (CROSS-HW-SW-1) ------------------------------------------
    for iface in INTERFACES:
        runner(
            """
            MERGE (i:Interface {node_id: $name}) SET i.name = $name
            WITH i
            MATCH (sw:Requirement {node_id: $sw})
            MATCH (hw:Requirement {node_id: $hw})
            MERGE (sw)-[:MENTIONS]->(i)
            MERGE (hw)-[:MENTIONS]->(i)
            """,
            {"name": iface["name"], "sw": iface["sw_req"], "hw": iface["hw_req"]},
        )
        if iface["consistent"]:
            runner(
                """
                MATCH (sw:Requirement {node_id: $sw})
                MATCH (hw:Requirement {node_id: $hw})
                MERGE (sw)-[:CONSISTENT_WITH]->(hw)
                """,
                {"sw": iface["sw_req"], "hw": iface["hw_req"]},
            )

    # --- Timing decomposition (CROSS-TIMING-1) -------------------------------
    for td in TIMING_DECOMP:
        runner(
            """
            MATCH (s:Requirement {node_id: $sys})
            MATCH (sw:Requirement {node_id: $sw})
            MATCH (hw:Requirement {node_id: $hw})
            SET sw.timing_budget_ns = $swb, hw.timing_budget_ns = $hwb
            MERGE (sw)-[:DERIVES_FROM]->(s)
            MERGE (hw)-[:DERIVES_FROM]->(s)
            """,
            {"sys": td["sys"], "sw": td["sw_req"], "hw": td["hw_req"],
             "swb": td["sw_budget"], "hwb": td["hw_budget"]},
        )

    # --- Safety hazards (CROSS-SAFETY-1) -------------------------------------
    for haz in SAFETY_HAZARDS:
        runner(
            """
            MERGE (h:SafetyHazard {node_id: $id})
              SET h.id = $id, h.description = $desc,
                  h.severity = $sev, h.mitigation_domain = $dom
            """,
            {"id": haz["id"], "desc": haz["description"],
             "sev": haz["severity"], "dom": haz["mitigation_domain"]},
        )
        if haz.get("sw_mitigator"):
            runner(
                """
                MATCH (r:Requirement {node_id: $rid})
                MATCH (h:SafetyHazard {node_id: $hid})
                MERGE (r)-[:MITIGATES]->(h)
                """,
                {"rid": haz["sw_mitigator"], "hid": haz["id"]},
            )
        if haz.get("hw_mitigator"):
            runner(
                """
                MATCH (r:Requirement {node_id: $rid})
                MATCH (h:SafetyHazard {node_id: $hid})
                MERGE (r)-[:MITIGATES]->(h)
                """,
                {"rid": haz["hw_mitigator"], "hid": haz["id"]},
            )


def _merge_trace(runner: Neo4jGraphRunner, from_id: str, to_id: str) -> None:
    """Create a DERIVES_FROM edge from one requirement to another."""
    runner(
        """
        MATCH (a:Requirement {node_id: $from_id})
        MATCH (b:Requirement {node_id: $to_id})
        MERGE (a)-[:DERIVES_FROM]->(b)
        """,
        {"from_id": from_id, "to_id": to_id},
    )


def _merge_test(
    runner: Neo4jGraphRunner, req_id: str, tc_id: str, coverage_type: str | None
) -> None:
    """Create a TestCase node verifying a requirement."""
    if coverage_type is None:
        runner(
            """
            MATCH (r:Requirement {node_id: $rid})
            MERGE (tc:TestCase {node_id: $tid}) SET tc.status = 'passed'
            MERGE (tc)-[:VERIFIES]->(r)
            """,
            {"rid": req_id, "tid": tc_id},
        )
    else:
        runner(
            """
            MATCH (r:Requirement {node_id: $rid})
            MERGE (tc:TestCase {node_id: $tid}) SET tc.status = 'passed'
            MERGE (tc)-[v:VERIFIES]->(r) SET v.coverage_type = $cov
            """,
            {"rid": req_id, "tid": tc_id, "cov": coverage_type},
        )


def load_all(config: Neo4jConfig | None = None) -> dict:
    """Clear, load the base graph, and add mock compliance metadata.

    Returns a small summary dict with node/relationship counts.
    """
    runner = Neo4jGraphRunner(config)
    try:
        runner.verify_connectivity()
        _clear_database(runner)
        stats = _load_base_graph(runner)
        _add_compliance_metadata(runner)
        totals = runner(
            "MATCH (n) RETURN count(n) AS nodes", {}
        )[0]
        rels = runner(
            "MATCH ()-[r]->() RETURN count(r) AS rels", {}
        )[0]
        return {
            "base_stats": stats,
            "final_node_count": totals["nodes"],
            "final_rel_count": rels["rels"],
        }
    finally:
        runner.close()


def main() -> None:
    print("=" * 70)
    print("SpecGuard Neo4j Loader — base graph + MOCK compliance metadata")
    print("=" * 70)
    summary = load_all()
    print(f"Base graph nodes:        {summary['base_stats']['total_nodes']}")
    print(f"Base graph relationships:{summary['base_stats']['total_relationships']}")
    print(f"Final node count:        {summary['final_node_count']}")
    print(f"Final relationship count:{summary['final_rel_count']}")
    print()
    print("Compliance metadata is MOCK — demonstrates executability, not")
    print("certification fitness (CVA6 spec contains no certification data).")


if __name__ == "__main__":
    main()
