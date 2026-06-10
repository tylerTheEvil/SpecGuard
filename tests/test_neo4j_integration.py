"""Integration tests: execute the 15 codified objectives on real Neo4j.

These tests implement Phase 1a of the evidence-hardening plan — they prove
that the constraint ``cypher_query`` strings are valid, executable Cypher (not
just interpreted by the in-memory demo runner) and that they discriminate
between compliant and violating elements on a graph seeded with MOCK
compliance metadata.

All tests are marked ``@pytest.mark.neo4j`` and **skip cleanly** when Neo4j is
unreachable or the ``neo4j`` driver is not installed, so plain ``pytest`` (no
database, no extras) keeps passing.

Honesty note: the metadata loaded by ``scripts/load_neo4j.py`` is synthetic.
These tests demonstrate executability, not certification fitness.
"""

from __future__ import annotations

import pytest

from specguard.compliance import (
    CROSS_DOMAIN_OBJECTIVES,
    DO_178C_OBJECTIVES,
    DO_254_OBJECTIVES,
    run_compliance_check,
)

pytestmark = pytest.mark.neo4j

# Connection timeout for the reachability probe (seconds). Kept short so the
# skip path is fast when no database is running.
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
def loaded_runner():
    """Load the graph + mock metadata once, yield a connected runner.

    Skips the whole module if Neo4j is unreachable.
    """
    if not _neo4j_available():
        pytest.skip("Neo4j not reachable — skipping integration tests")

    from scripts.load_neo4j import load_all
    from specguard.compliance.neo4j_runner import Neo4jGraphRunner

    load_all()
    runner = Neo4jGraphRunner()
    runner.verify_connectivity()
    yield runner
    runner.close()


# ---------------------------------------------------------------------------
# Smoke: every query parses and executes, returning rows of the right shape
# ---------------------------------------------------------------------------

ALL_OBJECTIVES = DO_178C_OBJECTIVES + DO_254_OBJECTIVES + CROSS_DOMAIN_OBJECTIVES


@pytest.mark.parametrize("objective", ALL_OBJECTIVES, ids=lambda o: o.objective_id)
def test_query_executes_and_shapes(loaded_runner, objective):
    """Each constraint query executes and every row is a violation dict."""
    rows = loaded_runner(objective.cypher_query, {})
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        # Every codified query returns a violating_requirement column.
        assert "violating_requirement" in row
        assert "reason" in row
        # The violation template must format without raising (no missing keys).
        explanation = objective.violation_template.format(**row)
        assert explanation


def test_all_15_objectives_present():
    """Guard against accidental count drift."""
    assert len(ALL_OBJECTIVES) == 15


# ---------------------------------------------------------------------------
# Discrimination: seeded conditions produce the expected violations
# ---------------------------------------------------------------------------


def test_do178c_a3_2_finds_known_high_smells(loaded_runner):
    """A-3-2 must flag exactly the three documented high-severity smells."""
    a3_2 = next(o for o in DO_178C_OBJECTIVES if o.objective_id == "DO-178C-A3-2")
    rows = loaded_runner(a3_2.cypher_query, {})
    flagged = {r["violating_requirement"] for r in rows}
    assert flagged == {"L1W-60", "PPA-50", "PPA-60"}


def test_do178c_a4_1_flags_orphan_llr(loaded_runner):
    """A-4-1 flags the orphan LLR (LLR-20) but not the traced one (LLR-10)."""
    a4_1 = next(o for o in DO_178C_OBJECTIVES if o.objective_id == "DO-178C-A4-1")
    flagged = {r["violating_requirement"] for r in loaded_runner(a4_1.cypher_query, {})}
    assert "LLR-20" in flagged
    assert "LLR-10" not in flagged


def test_do254_seeded_violations(loaded_runner):
    """Each DO-254 objective fires on exactly its seeded violation HWR."""
    expected = {
        "DO-254-6.2.1": "HWR-40",  # no verification method
        "DO-254-6.2.2": "HWR-50",  # derived, no rationale, no trace
        "DO-254-6.3.1": "HWR-50",  # derived without rationale
        "DO-254-6.3.2": "HWR-60",  # derived DAL-A without safety assessment
        "DO-254-6.4.1": "HWR-70",  # no passing verification
    }
    for obj in DO_254_OBJECTIVES:
        rows = loaded_runner(obj.cypher_query, {})
        flagged = {r["violating_requirement"] for r in rows}
        assert expected[obj.objective_id] in flagged, obj.objective_id
        # Compliant HWR-10/20/30 must never be flagged.
        assert not (flagged & {"HWR-10", "HWR-20", "HWR-30"}), obj.objective_id


def test_cross_domain_seeded_violations(loaded_runner):
    """Cross-domain objectives discriminate seeded violations from passes."""
    by_id = {o.objective_id: o for o in CROSS_DOMAIN_OBJECTIVES}

    iface_rows = loaded_runner(by_id["CROSS-HW-SW-1"].cypher_query, {})
    iface_flags = {r["violating_requirement"] for r in iface_rows}
    assert "IRQ_LINE" in str(iface_rows)  # the inconsistent interface fires
    assert "CSR_MMAP" not in str(iface_rows)  # the consistent one passes
    assert iface_flags  # at least one violation

    timing_rows = loaded_runner(by_id["CROSS-TIMING-1"].cypher_query, {})
    timing_flags = {r["violating_requirement"] for r in timing_rows}
    assert "SYS-4" in timing_flags  # 70 > 50 budget overrun
    assert "SYS-3" not in timing_flags  # 90 <= 100 is within budget

    safety_rows = loaded_runner(by_id["CROSS-SAFETY-1"].cypher_query, {})
    safety_flags = {r["violating_requirement"] for r in safety_rows}
    assert "HAZ-2" in safety_flags  # single-domain mitigation only
    assert "HAZ-1" not in safety_flags  # dual-domain mitigation present


def test_run_compliance_check_end_to_end(loaded_runner):
    """The engine runs all 15 objectives via the Neo4j runner without error."""
    report = run_compliance_check(loaded_runner, ALL_OBJECTIVES, standard_name="combined")
    assert report.total_objectives_checked == 15
    # Seeded data guarantees violations exist (DO-254 + cross-domain alone = 8).
    assert report.violation_count >= 8
    # No violation should fall back to the bare-title template.
    for v in report.violations:
        assert v.explanation
        assert not v.explanation.startswith(f"{v.title} (data:")
