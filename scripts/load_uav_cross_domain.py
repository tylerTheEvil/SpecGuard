"""Load the UAV cross-domain dataset into Neo4j and run the CROSS-* objectives.

Phase 2 of the evidence-hardening plan. This script loads the **derived**
UAV flight-control cross-domain dataset (:mod:`specguard.data.uav_cross_domain`)
into the project Neo4j instance and executes the three cross-domain compliance
objectives (:data:`specguard.compliance.CROSS_DOMAIN_OBJECTIVES`) against it via
the existing :class:`~specguard.compliance.neo4j_runner.Neo4jGraphRunner` and
:func:`~specguard.compliance.run_compliance_check`.

It **supersedes** the hand-authored synthetic cross-domain seed in
``scripts/load_neo4j.py`` for the cross-domain niche: instead of invented
``HWR-*`` / ``HAZ-*`` / ``IRQ_LINE`` mock metadata, the graph is built from a
dataset whose software side is derived from public PX4/ArduPilot documentation
and whose hardware side is anchored in the real CVA6 core (the FPGA-hosted
processor). See the data module docstring for full provenance and the honesty
statement (derived/illustrative, not a real certified program).

Clear-and-load is fine — the project DBMS is dedicated and fully reproducible
from the repository. This does **not** touch or break ``scripts/load_neo4j.py``;
both loaders clear the database before loading, so whichever ran last defines
the graph. The integration test fixtures each (re)load what they need.

Run::

    .venv/bin/python scripts/load_uav_cross_domain.py

Writes ``results/cross_domain_run.json`` with per-objective pass/violation
results and a ``_provenance`` block.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure the project root is importable so ``scripts.load_neo4j`` resolves both
# under pytest (rootdir on path) and when this file is run directly as a script.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Reuse the destructive-clear helper from the Phase 1a loader so the two stay
# behaviourally identical (and we do not duplicate the Cypher).
from scripts.load_neo4j import _clear_database
from specguard.compliance import CROSS_DOMAIN_OBJECTIVES, run_compliance_check
from specguard.compliance.neo4j_runner import Neo4jConfig, Neo4jGraphRunner
from specguard.data.uav_cross_domain import (
    HAZARDS,
    INTERFACES,
    SEEDED_VIOLATIONS,
    SYSTEM_REQUIREMENTS,
    DomainRequirement,
    Hazard,
    Interface,
    SystemRequirement,
    dataset_stats,
    get_domain_requirements,
)

_RESULTS_PATH = Path(__file__).resolve().parents[1] / "results" / "cross_domain_run.json"


# ---------------------------------------------------------------------------
# Loading logic
# ---------------------------------------------------------------------------


def _load_system_requirements(
    runner: Neo4jGraphRunner, reqs: list[SystemRequirement]
) -> None:
    """Create ``:Requirement {level:'system'}`` nodes with timing budgets."""
    for r in reqs:
        runner(
            """
            MERGE (n:Requirement {node_id: $id})
            SET n.id = $id, n.text = $text, n.level = 'system',
                n.dal = $dal, n.is_derived = false,
                n.timing_budget_ns = $budget, n.provenance = $prov
            """,
            {
                "id": r.req_id,
                "text": r.text,
                "dal": r.dal,
                "budget": r.timing_budget_ns,
                "prov": r.provenance,
            },
        )


def _load_domain_requirements(
    runner: Neo4jGraphRunner, reqs: list[DomainRequirement]
) -> None:
    """Create HLR/HWR ``:Requirement`` nodes and their ``DERIVES_FROM`` edges."""
    for r in reqs:
        runner(
            """
            MERGE (n:Requirement {node_id: $id})
            SET n.id = $id, n.text = $text, n.level = $level,
                n.dal = $dal, n.is_derived = $is_derived,
                n.provenance = $prov, n.cva6_ref = $cva6_ref
            """,
            {
                "id": r.req_id,
                "text": r.text,
                "level": r.level,
                "dal": r.dal,
                "is_derived": r.is_derived,
                "prov": r.provenance,
                "cva6_ref": r.cva6_ref,
            },
        )
        if r.timing_budget_ns is not None:
            runner(
                "MATCH (n:Requirement {node_id: $id}) "
                "SET n.timing_budget_ns = $budget",
                {"id": r.req_id, "budget": r.timing_budget_ns},
            )
        runner(
            """
            MATCH (child:Requirement {node_id: $cid})
            MATCH (parent:Requirement {node_id: $pid})
            MERGE (child)-[:DERIVES_FROM]->(parent)
            """,
            {"cid": r.req_id, "pid": r.derives_from},
        )


def _load_interfaces(runner: Neo4jGraphRunner, ifaces: list[Interface]) -> None:
    """Create ``:Interface`` nodes, ``MENTIONS`` edges and CONSISTENT_WITH."""
    for i in ifaces:
        runner(
            """
            MERGE (iface:Interface {node_id: $name})
            SET iface.name = $name, iface.description = $desc,
                iface.provenance = $prov
            WITH iface
            MATCH (sw:Requirement {node_id: $sw})
            MATCH (hw:Requirement {node_id: $hw})
            MERGE (sw)-[:MENTIONS]->(iface)
            MERGE (hw)-[:MENTIONS]->(iface)
            """,
            {
                "name": i.name,
                "desc": i.description,
                "prov": i.provenance,
                "sw": i.sw_req,
                "hw": i.hw_req,
            },
        )
        if i.consistent:
            runner(
                """
                MATCH (sw:Requirement {node_id: $sw})
                MATCH (hw:Requirement {node_id: $hw})
                MERGE (sw)-[:CONSISTENT_WITH]->(hw)
                """,
                {"sw": i.sw_req, "hw": i.hw_req},
            )


def _load_hazards(runner: Neo4jGraphRunner, hazards: list[Hazard]) -> None:
    """Create ``:SafetyHazard`` nodes and ``MITIGATES`` edges from both sides."""
    for h in hazards:
        runner(
            """
            MERGE (haz:SafetyHazard {node_id: $id})
            SET haz.id = $id, haz.description = $desc,
                haz.severity = $sev, haz.mitigation_domain = $dom,
                haz.provenance = $prov
            """,
            {
                "id": h.haz_id,
                "desc": h.description,
                "sev": h.severity,
                "dom": h.mitigation_domain,
                "prov": h.provenance,
            },
        )
        for rid in (*h.sw_mitigators, *h.hw_mitigators):
            runner(
                """
                MATCH (r:Requirement {node_id: $rid})
                MATCH (haz:SafetyHazard {node_id: $hid})
                MERGE (r)-[:MITIGATES]->(haz)
                """,
                {"rid": rid, "hid": h.haz_id},
            )


def load_uav_graph(config: Neo4jConfig | None = None) -> dict:
    """Clear the database and load the full UAV cross-domain graph.

    Returns a summary dict with node/relationship counts.
    """
    runner = Neo4jGraphRunner(config)
    try:
        runner.verify_connectivity()
        _clear_database(runner)
        _load_system_requirements(runner, SYSTEM_REQUIREMENTS)
        _load_domain_requirements(runner, get_domain_requirements())
        _load_interfaces(runner, INTERFACES)
        _load_hazards(runner, HAZARDS)
        nodes = runner("MATCH (n) RETURN count(n) AS nodes", {})[0]["nodes"]
        rels = runner("MATCH ()-[r]->() RETURN count(r) AS rels", {})[0]["rels"]
        return {
            "dataset": dataset_stats(),
            "final_node_count": nodes,
            "final_rel_count": rels,
        }
    finally:
        runner.close()


# ---------------------------------------------------------------------------
# Run the CROSS-* objectives and persist the result artifact
# ---------------------------------------------------------------------------


def run_and_dump(config: Neo4jConfig | None = None) -> dict:
    """Load the graph, run the 3 CROSS-* objectives, write the results JSON."""
    summary = load_uav_graph(config)

    runner = Neo4jGraphRunner(config)
    try:
        runner.verify_connectivity()
        report = run_compliance_check(
            runner, CROSS_DOMAIN_OBJECTIVES, standard_name="cross-domain (UAV)"
        )
    finally:
        runner.close()

    by_objective: dict[str, dict] = {}
    for obj in CROSS_DOMAIN_OBJECTIVES:
        viols = report.violations_by_objective().get(obj.objective_id, [])
        by_objective[obj.objective_id] = {
            "title": obj.title,
            "standard": obj.standard,
            "passed": len(viols) == 0,
            "violation_count": len(viols),
            "violations": [
                {
                    "violating_element": v.violating_element,
                    "explanation": v.explanation,
                    "raw_data": v.raw_data,
                }
                for v in viols
            ],
        }

    artifact = {
        "standard": report.standard,
        "timestamp": report.timestamp,
        "graph_summary": summary,
        "objectives_checked": report.total_objectives_checked,
        "passing_objective_ids": report.passing_objective_ids,
        "total_violations": report.violation_count,
        "by_objective": by_objective,
        "seeded_violations": [asdict(sv) for sv in SEEDED_VIOLATIONS],
        "_provenance": {
            "dataset": "specguard.data.uav_cross_domain",
            "nature": (
                "DERIVED, ILLUSTRATIVE dataset authored for this study — NOT "
                "requirements from a real certified UAV program and NOT "
                "certification evidence. This supersedes the hand-authored "
                "synthetic cross-domain seed in scripts/load_neo4j.py."
            ),
            "sw_side_derived_from": [
                "PX4 architecture/controller concept "
                "(docs.px4.io/main/en/concept/architecture.html): IMU 1 kHz "
                "sample, 250 Hz publish; cascaded position/attitude/rate "
                "controllers",
                "PX4 control-loop cadence "
                "(discuss.px4.io/t/control-loop-update-frequency/14043): "
                "rate loop ~250 Hz, position loop ~100 Hz",
                "ArduPilot aggressive rate-loop tuning "
                "(ardupilot.org/copter/docs/high-loop-rate-tuning.html): "
                "main loop 400 Hz / 2.5 ms; fast-rate thread up to 4 kHz",
                "ArduPilot failsafe documentation "
                "(ardupilot.org/copter/docs/failsafe-landing-page.html): "
                "bounded deterministic link-loss/battery/EKF failsafes",
            ],
            "hw_side_anchored_in": (
                "CVA6 Requirements Specification v1.0.1 (OpenHW Group/Thales) "
                "via specguard.data.cva6_requirements; HWR reqs reference real "
                "CVA6 IDs IRQ-10, MEM-10, MEM-20, L1W-10, FET-10, ISA-60"
            ),
            "authored_for_this_study": (
                "'shall' requirement wording, HLR/HWR decomposition, "
                "timing-budget arithmetic, DAL assignments, mini-FHA hazards "
                "and severities, and all deliberate seeded violations"
            ),
        },
    }

    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(json.dumps(artifact, indent=2) + "\n")
    return artifact


def main() -> None:
    print("=" * 70)
    print("SpecGuard — UAV cross-domain dataset loader + CROSS-* run")
    print("=" * 70)
    artifact = run_and_dump()
    summary = artifact["graph_summary"]
    print(f"Dataset:            {summary['dataset']}")
    print(f"Final node count:   {summary['final_node_count']}")
    print(f"Final rel count:    {summary['final_rel_count']}")
    print()
    print("CROSS-* objective outcomes:")
    for oid, info in artifact["by_objective"].items():
        status = "PASS" if info["passed"] else f"FAIL ({info['violation_count']})"
        flagged = [v["violating_element"] for v in info["violations"]]
        print(f"  [{oid}] {status} {flagged}")
    print()
    print(f"Results written to: {_RESULTS_PATH}")
    print()
    print("Dataset is DERIVED/illustrative (PX4/ArduPilot docs + CVA6 anchor),")
    print("NOT certification evidence. See module docstring for provenance.")


if __name__ == "__main__":
    main()
