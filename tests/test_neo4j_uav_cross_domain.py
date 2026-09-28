"""Integration tests: CROSS-* objectives on the UAV cross-domain graph (Neo4j).

Phase 2 of the evidence-hardening plan. These tests load the **derived** UAV
flight-control cross-domain dataset (:mod:`specguard.data.uav_cross_domain`)
into a real Neo4j instance and prove that the three cross-domain objectives
(:data:`specguard.compliance.CROSS_DOMAIN_OBJECTIVES`) *discriminate*: each
finds its seeded defect and distinguishes incomplete timing allocations from
numeric overruns. Missing budgets are UNKNOWN, not zero-valued contributions.

All tests are marked ``@pytest.mark.neo4j`` and **skip cleanly** when Neo4j is
unreachable, so plain ``pytest`` keeps passing.

Fixture isolation note
----------------------
This module owns a module-scoped fixture that clear-and-loads the UAV graph via
``scripts.load_uav_cross_domain.load_uav_graph``. It does **not** share state
with ``tests/test_neo4j_integration.py`` (which loads the CVA6 mock graph in its
own module-scoped fixture). pytest runs each module's tests to completion before
the next, so the two clear-and-load fixtures do not interleave.

Honesty: the UAV dataset is derived/illustrative, not certification evidence —
see the data module docstring.
"""

from __future__ import annotations

import pytest

from specguard.compliance import CROSS_DOMAIN_OBJECTIVES, run_compliance_check
from specguard.data.uav_cross_domain import SEEDED_VIOLATIONS

pytestmark = pytest.mark.neo4j

_PROBE_TIMEOUT = 3.0


def _neo4j_available() -> bool:
    """Return True if the neo4j driver is installed and the DB is reachable."""
    try:
        from neo4j import GraphDatabase

        from specguard.compliance.neo4j_runner import Neo4jConfig
    except ImportError:
        return False

    config = Neo4jConfig.from_env()
    from specguard.compliance.neo4j_runner import require_isolated_test_database
    try:
        require_isolated_test_database(config)
    except RuntimeError:
        return False

    try:
        driver = GraphDatabase.driver(
            config.uri,
            auth=(config.user, config.password),
            connection_timeout=_PROBE_TIMEOUT,
        )
        try:
            driver.verify_connectivity()
            return True
        finally:
            driver.close()
    except Exception:
        return False


@pytest.fixture(scope="module")
def uav_runner():
    """Clear-and-load the UAV cross-domain graph once; yield a connected runner."""
    if not _neo4j_available():
        pytest.skip("Neo4j not reachable — skipping UAV integration tests")

    from scripts.load_uav_cross_domain import load_uav_graph
    from specguard.compliance.neo4j_runner import Neo4jGraphRunner

    load_uav_graph()
    runner = Neo4jGraphRunner()
    runner.verify_connectivity()
    yield runner
    runner.close()


_BY_ID = {o.objective_id: o for o in CROSS_DOMAIN_OBJECTIVES}
_SEEDED = {s.objective_id: s for s in SEEDED_VIOLATIONS}


def test_cross_hw_sw_interface_discriminates(uav_runner):
    """CROSS-HW-SW-1 flags the FPU interface, not the consistent ones."""
    rows = uav_runner(_BY_ID["CROSS-HW-SW-1"].cypher_query, {})
    flagged_ifaces = {r["shared_interface"] for r in rows}
    assert "FPU_CSR_BLOCK" in flagged_ifaces
    # The three CONSISTENT_WITH interfaces must not appear.
    assert flagged_ifaces.isdisjoint(
        {"GYRO_IRQ_LINE", "ACTUATOR_MMAP_REGS", "IMU_DMA_CHANNEL"}
    )
    assert len(rows) == 1


def test_cross_timing_budget_discriminates(uav_runner):
    """CROSS-TIMING-1 separates a numeric overrun from missing allocations."""
    rows = uav_runner(_BY_ID["CROSS-TIMING-1"].cypher_query, {})
    by_id = {r["violating_requirement"]: r for r in rows}
    assert len(rows) == len(by_id) == 2
    assert {rid: r["_status"] for rid, r in by_id.items()} == {
        "UAV-SYS-40": "FAIL", "UAV-SYS-10": "UNKNOWN",
    }
    overrun = by_id["UAV-SYS-40"]
    assert (overrun["allocated"], overrun["budget"], overrun["missing_budgets"]) == (
        2_500_000, 2_000_000, 0,
    )
    # The FPU pair derives from SYS-10 without its own allocation. Its known
    # 2.5 ms shares fit 4 ms, but that does not prove the complete budget fits.
    incomplete = by_id["UAV-SYS-10"]
    assert (incomplete["allocated"], incomplete["budget"], incomplete["missing_budgets"]) == (
        2_500_000, 4_000_000, 2,
    )


def test_cross_safety_propagation_discriminates(uav_runner):
    """CROSS-SAFETY-1 flags the single-domain hazard, not the dual-domain one."""
    rows = uav_runner(_BY_ID["CROSS-SAFETY-1"].cypher_query, {})
    flagged = {r["violating_requirement"] for r in rows}
    assert "UAV-HAZ-2" in flagged  # hazardous, HW-only mitigation
    assert "UAV-HAZ-1" not in flagged  # catastrophic, dual-domain mitigation
    assert "UAV-HAZ-3" not in flagged  # major, below threshold
    assert len(rows) == 1


def test_each_objective_fires_on_exactly_its_seeded_violation(uav_runner):
    """Each query finds one seeded defect; UNKNOWN timing is not a violation."""
    for obj in CROSS_DOMAIN_OBJECTIVES:
        rows = uav_runner(obj.cypher_query, {})
        defects = [r for r in rows if r.get("_status", "FAIL") == "FAIL"]
        assert len(defects) == 1, (obj.objective_id, rows)
        seeded = _SEEDED[obj.objective_id]
        field = (
            "shared_interface" if obj.objective_id == "CROSS-HW-SW-1" else "violating_requirement"
        )
        assert defects[0][field] == seeded.violating_element
        unknowns = [r for r in rows if r.get("_status") == "UNKNOWN"]
        assert [r["violating_requirement"] for r in unknowns] == (
            ["UAV-SYS-10"] if obj.objective_id == "CROSS-TIMING-1" else []
        )


def test_run_compliance_check_end_to_end(uav_runner):
    """Unknown broader scope preserves the one demonstrated numeric violation."""
    report = run_compliance_check(
        uav_runner, CROSS_DOMAIN_OBJECTIVES, standard_name="cross-domain (UAV)"
    )
    assert report.total_objectives_checked == 3
    assert report.violation_count == 1  # numeric witness survives unknown broader scope
    assert report.passing_objective_ids == []
    assert sum(r.status == "UNKNOWN" for r in report.results) == 3
    assert all(r.details.get('candidate_rows') for r in report.results if r.status == 'UNKNOWN')
