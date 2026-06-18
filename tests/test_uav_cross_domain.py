"""Dataset-integrity tests for the UAV cross-domain dataset (no DB needed).

These tests validate :mod:`specguard.data.uav_cross_domain` independently of
Neo4j: counts, level vocabulary, the arithmetic / structure behind every seeded
violation, the existence of compliant counterparts, and that the requirement
texts are smell-clean (none are deliberately smelly — the seeded defects are
graph-structural, not lexical).

The DB-backed discrimination tests live in ``tests/test_neo4j_integration.py``
behind ``@pytest.mark.neo4j``.
"""

from __future__ import annotations

import pytest

from specguard import assess_requirement
from specguard.data.uav_cross_domain import (
    HAZARDS,
    INTERFACES,
    SEEDED_VIOLATIONS,
    SYSTEM_REQUIREMENTS,
    all_requirement_texts,
    dataset_stats,
    get_domain_requirements,
    get_hwr_requirements,
)

_ARP4761_SEVERITIES = {"catastrophic", "hazardous", "major", "minor"}
_LEVELS = {"HLR", "HWR"}


# ---------------------------------------------------------------------------
# Shape & vocabulary
# ---------------------------------------------------------------------------


def test_dataset_shape_in_spec_range():
    """~20-25 paired requirements, 3-4 interfaces, 2-3 hazards."""
    stats = dataset_stats()
    assert 20 <= stats["total_requirements"] <= 25
    assert 4 <= stats["system_requirements"] <= 6
    assert 3 <= stats["interfaces"] <= 4
    assert 2 <= stats["hazards"] <= 3
    assert stats["seeded_violations"] == 3


def test_system_requirements_have_budgets_and_dal():
    """Every system requirement carries a positive ns budget and a DAL."""
    assert len(SYSTEM_REQUIREMENTS) >= 4
    for r in SYSTEM_REQUIREMENTS:
        assert r.timing_budget_ns > 0
        assert r.dal in {"A", "B", "C", "D"}
        assert " shall " in r.text


def test_domain_levels_are_valid():
    """Every domain requirement is HLR or HWR and derives from a system req."""
    sys_ids = {r.req_id for r in SYSTEM_REQUIREMENTS}
    for r in get_domain_requirements():
        assert r.level in _LEVELS
        assert r.derives_from in sys_ids, r.req_id


def test_hwr_requirements_anchor_in_cva6():
    """Every HWR references a real CVA6 requirement ID (HW/FPGA anchor)."""
    from specguard.data.cva6_requirements import get_all_requirements

    cva6_ids = {r.req_id for r in get_all_requirements()}
    for r in get_hwr_requirements():
        assert r.cva6_ref in cva6_ids, f"{r.req_id} -> {r.cva6_ref}"


def test_hazard_severities_use_arp4761_vocabulary():
    for h in HAZARDS:
        assert h.severity in _ARP4761_SEVERITIES


def test_each_system_req_decomposes_into_both_domains():
    """Each system req with a timing budget has at least one HLR and one HWR child."""
    by_parent_levels: dict[str, set[str]] = {}
    for r in get_domain_requirements():
        by_parent_levels.setdefault(r.derives_from, set()).add(r.level)
    for sysreq in SYSTEM_REQUIREMENTS:
        levels = by_parent_levels.get(sysreq.req_id, set())
        assert "HLR" in levels, sysreq.req_id
        assert "HWR" in levels, sysreq.req_id


# ---------------------------------------------------------------------------
# Seeded violations are genuinely present in the data
# ---------------------------------------------------------------------------


def _budget_sum(parent_id: str) -> int:
    return sum(
        r.timing_budget_ns or 0
        for r in get_domain_requirements()
        if r.derives_from == parent_id
    )


def test_seeded_timing_overrun_really_overruns():
    sv = next(s for s in SEEDED_VIOLATIONS if s.key == "TIMING_OVERRUN")
    parent = next(r for r in SYSTEM_REQUIREMENTS if r.req_id == sv.violating_element)
    allocated = _budget_sum(parent.req_id)
    assert allocated > parent.timing_budget_ns, (allocated, parent.timing_budget_ns)


def test_compliant_timing_pairs_stay_within_budget():
    """Every non-seeded system req's children sum within (or equal to) budget."""
    overrun_id = next(
        s.violating_element for s in SEEDED_VIOLATIONS if s.key == "TIMING_OVERRUN"
    )
    for r in SYSTEM_REQUIREMENTS:
        if r.req_id == overrun_id:
            continue
        assert _budget_sum(r.req_id) <= r.timing_budget_ns, r.req_id


def test_seeded_missing_consistency_interface_exists_and_is_inconsistent():
    sv = next(s for s in SEEDED_VIOLATIONS if s.key == "MISSING_CONSISTENCY")
    iface = next(i for i in INTERFACES if i.name == sv.violating_element)
    assert iface.consistent is False
    # The compliant counterpart interface must actually assert consistency.
    twin = next(i for i in INTERFACES if i.name == sv.compliant_counterpart)
    assert twin.consistent is True


def test_all_other_interfaces_are_consistent():
    """Exactly one interface is seeded inconsistent; the rest are consistent."""
    inconsistent = [i for i in INTERFACES if not i.consistent]
    assert len(inconsistent) == 1
    assert inconsistent[0].name == "FPU_CSR_BLOCK"


def test_seeded_single_domain_hazard_lacks_one_side():
    sv = next(s for s in SEEDED_VIOLATIONS if s.key == "SINGLE_DOMAIN_HAZARD")
    haz = next(h for h in HAZARDS if h.haz_id == sv.violating_element)
    assert haz.severity in {"catastrophic", "hazardous"}
    assert haz.mitigation_domain in {"both", "sw_and_hw"}
    # Exactly one domain mitigated (the seeded gap).
    assert bool(haz.sw_mitigators) != bool(haz.hw_mitigators)


def test_compliant_hazard_has_dual_domain_mitigation():
    sv = next(s for s in SEEDED_VIOLATIONS if s.key == "SINGLE_DOMAIN_HAZARD")
    twin = next(h for h in HAZARDS if h.haz_id == sv.compliant_counterpart)
    assert twin.severity in {"catastrophic", "hazardous"}
    assert twin.sw_mitigators and twin.hw_mitigators


def test_major_hazard_is_below_dual_domain_threshold():
    """The 'major' hazard is single-domain by design and must not be flaggable."""
    major = [h for h in HAZARDS if h.severity == "major"]
    assert major
    for h in major:
        assert h.severity not in {"catastrophic", "hazardous"}


def test_mitigator_ids_resolve_to_real_requirements():
    req_ids = {r.req_id for r in get_domain_requirements()}
    for h in HAZARDS:
        for rid in (*h.sw_mitigators, *h.hw_mitigators):
            assert rid in req_ids, rid


def test_seeded_violations_cover_all_three_cross_objectives():
    objectives = {s.objective_id for s in SEEDED_VIOLATIONS}
    assert objectives == {"CROSS-HW-SW-1", "CROSS-TIMING-1", "CROSS-SAFETY-1"}


# ---------------------------------------------------------------------------
# Requirement text quality
# ---------------------------------------------------------------------------


def test_all_requirement_texts_are_smell_clean():
    """No requirement is deliberately smelly; all texts pass the smell check."""
    offenders: dict[str, list[str]] = {}
    for rid, text in all_requirement_texts().items():
        report = assess_requirement(rid, text)
        if report.smell_report.hits:
            offenders[rid] = [
                f"{h.smell_type.value}:{h.trigger}" for h in report.smell_report.hits
            ]
    assert not offenders, offenders


@pytest.mark.parametrize(
    "rid,text",
    sorted(all_requirement_texts().items()),
    ids=lambda v: v if isinstance(v, str) and v.startswith("UAV") else "",
)
def test_each_requirement_is_a_shall_statement(rid, text):
    assert " shall " in text, rid
