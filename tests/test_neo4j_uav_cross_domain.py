"""Integration tests: CROSS-* objectives on the UAV cross-domain graph (Neo4j).

Phase 2 of the evidence-hardening plan. These tests load the **derived** UAV
flight-control cross-domain dataset (:mod:`specguard.data.uav_cross_domain`)
into a real Neo4j instance and prove that the three cross-domain objectives
(:data:`specguard.compliance.CROSS_DOMAIN_OBJECTIVES`) *discriminate*: each
fires on exactly its seeded violation and passes on the compliant counterparts.

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
    """CROSS-TIMING-1 flags the failsafe overrun, not the in-budget systems."""
    rows = uav_runner(_BY_ID["CROSS-TIMING-1"].cypher_query, {})
    flagged = {r["violating_requirement"] for r in rows}
    assert "UAV-SYS-40" in flagged  # 1.5 + 1.0 = 2.5 ms > 2 ms budget
    assert flagged.isdisjoint(
        {"UAV-SYS-10", "UAV-SYS-20", "UAV-SYS-30", "UAV-SYS-50", "UAV-SYS-60"}
    )
    assert len(rows) == 1
    # Confirm the reported arithmetic matches the seeded overrun.
    row = rows[0]
    assert row["allocated"] > row["budget"]


def test_cross_safety_propagation_discriminates(uav_runner):
    """CROSS-SAFETY-1 flags the single-domain hazard, not the dual-domain one."""
    rows = uav_runner(_BY_ID["CROSS-SAFETY-1"].cypher_query, {})
    flagged = {r["violating_requirement"] for r in rows}
    assert "UAV-HAZ-2" in flagged  # hazardous, HW-only mitigation
    assert "UAV-HAZ-1" not in flagged  # catastrophic, dual-domain mitigation
    assert "UAV-HAZ-3" not in flagged  # major, below threshold
    assert len(rows) == 1


def test_each_objective_fires_on_exactly_its_seeded_violation(uav_runner):
    """Every objective returns exactly one row — its seeded violation."""
    for obj in CROSS_DOMAIN_OBJECTIVES:
        rows = uav_runner(obj.cypher_query, {})
        assert len(rows) == 1, (obj.objective_id, rows)


def test_run_compliance_check_end_to_end(uav_runner):
    """The engine runs the 3 CROSS-* objectives and reports 3 violations."""
    report = run_compliance_check(
        uav_runner, CROSS_DOMAIN_OBJECTIVES, standard_name="cross-domain (UAV)"
    )
    assert report.total_objectives_checked == 3
    assert report.violation_count == 3
    assert report.passing_objective_ids == []  # all three seeded to fail
    for v in report.violations:
        assert v.explanation
        assert not v.explanation.startswith(f"{v.title} (data:")
    # One violation per objective, matching the seeded registry.
    by_obj = report.violations_by_objective()
    for oid in _SEEDED:
        assert len(by_obj.get(oid, [])) == 1, oid
