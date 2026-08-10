"""Tests for the independent human-annotated edge-extraction eval tooling.

These pin the *tooling* (deterministic sampling, scoring math, the surrogate-gap
report, and the independence guard) so it is trustworthy before any human
annotation exists. The gold labels themselves are authored by a human; here we
use tiny synthetic gold/proposal fixtures.

``experiments`` is not an installed package, so it is added to ``sys.path``
(mirroring ``tests/test_independent_lexicon.py``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import edge_extraction_human_eval as hev  # noqa: E402

from specguard.data.cva6_requirements import get_all_requirements  # noqa: E402

# ---------------------------------------------------------------------------
# Deterministic stratified sampling
# ---------------------------------------------------------------------------


def test_sample_subset_is_deterministic_and_sized():
    reqs = get_all_requirements()
    a = [r.req_id for r in hev.sample_subset(reqs, 20)]
    b = [r.req_id for r in hev.sample_subset(reqs, 20)]
    assert a == b  # no RNG — stable across calls
    assert len(a) == 20
    assert len(set(a)) == 20  # no duplicates


def test_sample_subset_stratifies_across_categories():
    reqs = get_all_requirements()
    subset = hev.sample_subset(reqs, 20)
    cats = {r.category for r in subset}
    # Hamilton apportionment should touch most categories, not collapse to one.
    assert len(cats) >= 5


def test_sample_subset_respects_size_bounds():
    reqs = get_all_requirements()
    assert len(hev.sample_subset(reqs, 1)) == 1
    assert len(hev.sample_subset(reqs, 5)) == 5


# ---------------------------------------------------------------------------
# Template + candidate pool structure
# ---------------------------------------------------------------------------


def test_template_is_empty_and_marked_unfilled():
    reqs = get_all_requirements()
    subset = hev.sample_subset(reqs, 6)
    tmpl = hev.build_template(subset, hev.build_inventory())
    assert tmpl["_meta"]["status"] == "TEMPLATE_UNFILLED"
    assert len(tmpl["items"]) == 6
    assert all(item["edges"] == [] for item in tmpl["items"])
    # Per-item review markers start UNREVIEWED — an unread item can never pass
    # as a genuine "no edges found" negative (the scorer enforces REVIEWED).
    assert all(item["annotation_status"] == "UNREVIEWED" for item in tmpl["items"])
    assert set(tmpl["inventory"]) == {"components", "standards", "requirements"}


def test_candidate_pool_separates_dict_and_surface_sources():
    reqs = get_all_requirements()
    subset = hev.sample_subset(reqs, 20)
    pool = hev.build_candidate_pool(subset, hev.build_inventory())
    sources = {
        c["source"] for item in pool["items"] for c in item["candidates"]
    }
    assert sources <= {"dict", "surface"}
    assert "_meta" in pool and "NOT gold" in pool["_meta"]["purpose"]


# ---------------------------------------------------------------------------
# Scoring math
# ---------------------------------------------------------------------------


def test_prf_basic():
    proposed = {("R1", "CVA6"), ("R1", "FPU"), ("R2", "MMU")}
    gold = {("R1", "CVA6"), ("R2", "MMU"), ("R3", "TLB")}
    m = hev._prf(proposed, gold)
    assert m["true_positives"] == 2
    assert m["false_positives"] == 1  # (R1, FPU)
    assert m["false_negatives"] == 1  # (R3, TLB)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)


def test_prf_empty_proposals_gives_none_precision():
    m = hev._prf(set(), {("R1", "CVA6")})
    assert m["precision"] is None
    assert m["recall"] == 0.0
    assert m["f1"] is None


# ---------------------------------------------------------------------------
# Surrogate gap and independence guard
# ---------------------------------------------------------------------------


def _typed(mentions=(), refers=(), derives=()):
    return {
        "MENTIONS": set(mentions),
        "REFERS_TO": set(refers),
        "DERIVES_FROM": set(derives),
    }


def test_surrogate_gap_reports_misses_and_false_alarms():
    gold = _typed(mentions={("R1", "CVA6"), ("R1", "LFSR")})  # LFSR not in dict
    surrogate = _typed(mentions={("R1", "CVA6"), ("R1", "FPU")})  # FPU dict false alarm
    gap = hev.surrogate_gap(gold, surrogate)
    assert gap["MENTIONS"]["dictionary_misses"] == [("R1", "LFSR")]
    assert gap["MENTIONS"]["dictionary_false_alarms"] == [("R1", "FPU")]


def test_independence_check_passes_when_gold_differs():
    gold = _typed(mentions={("R1", "CVA6"), ("R1", "LFSR")})
    surrogate = _typed(mentions={("R1", "CVA6")})
    stats = hev.independence_check(gold, surrogate)
    assert stats["per_type"]["MENTIONS"]["identical"] is False
    assert stats["per_type"]["MENTIONS"]["jaccard"] == pytest.approx(1 / 2)
    assert stats["identical_to_surrogate"] is False


def test_independence_check_refuses_identical_by_default():
    """Identity is refused as SUSPICIOUS — the message must not claim proof."""
    ref = _typed(mentions={("R1", "CVA6"), ("R2", "MMU")}, refers={("R1", "RV64I")})
    with pytest.raises(ValueError, match="SUSPICIOUS.*not proof"):
        hev.independence_check(ref, {k: set(v) for k, v in ref.items()})


def test_independence_check_identical_with_override_warns_loudly():
    """--allow-identical proceeds, with the caveat recorded in the report."""
    ref = _typed(mentions={("R1", "CVA6"), ("R2", "MMU")}, refers={("R1", "RV64I")})
    stats = hev.independence_check(
        ref, {k: set(v) for k, v in ref.items()}, allow_identical=True
    )
    assert stats["identical_to_surrogate"] is True
    assert "suspicious" in stats["note"]


# ---------------------------------------------------------------------------
# Gold loading guards
# ---------------------------------------------------------------------------


def test_load_gold_refuses_unfilled_template(tmp_path):
    reqs = get_all_requirements()
    tmpl = hev.build_template(hev.sample_subset(reqs, 3), hev.build_inventory())
    path = tmp_path / "tmpl.json"
    path.write_text(json.dumps(tmpl))
    with pytest.raises(ValueError, match="TEMPLATE_UNFILLED"):
        hev.load_gold(path)


def test_load_gold_refuses_filled_status_but_no_edges(tmp_path):
    reqs = get_all_requirements()
    tmpl = hev.build_template(hev.sample_subset(reqs, 3), hev.build_inventory())
    tmpl["_meta"]["status"] = "ANNOTATED"  # marked done but nothing annotated
    for item in tmpl["items"]:
        item["annotation_status"] = "REVIEWED"  # all reviewed, still no edges
    path = tmp_path / "tmpl.json"
    path.write_text(json.dumps(tmpl))
    with pytest.raises(ValueError, match="no annotated edges"):
        hev.load_gold(path)


def test_load_gold_refuses_partially_reviewed_template(tmp_path):
    """One annotated item does NOT make the file complete.

    Items never marked REVIEWED must fail loading — otherwise their empty
    `edges` lists would silently count as genuine negative annotations.
    """
    reqs = get_all_requirements()
    tmpl = hev.build_template(hev.sample_subset(reqs, 3), hev.build_inventory())
    inv = hev.build_inventory()
    first = tmpl["items"][0]
    first["edges"] = [
        {"edge_type": "MENTIONS", "target": inv["components"][0],
         "evidence_span": "x", "note": ""},
    ]
    first["annotation_status"] = "REVIEWED"  # the other two items stay UNREVIEWED
    tmpl["_meta"]["status"] = "ANNOTATED"
    path = tmp_path / "tmpl.json"
    path.write_text(json.dumps(tmpl))
    with pytest.raises(ValueError, match="annotation_status=REVIEWED"):
        hev.load_gold(path)


# ---------------------------------------------------------------------------
# End-to-end score() on a filled fixture
# ---------------------------------------------------------------------------


def test_score_end_to_end(tmp_path):
    """A filled gold + proposals file scores per type with a surrogate gap."""
    # Pick two real subset requirements so builder_reference has something.
    reqs = get_all_requirements()
    subset = hev.sample_subset(reqs, 20)
    inv = hev.build_inventory()
    tmpl = hev.build_template(subset, inv)

    # Annotate the first item with one plausible + one deliberately dict-absent
    # edge so the gold is NOT identical to the surrogate (independence holds).
    first = tmpl["items"][0]
    first["edges"] = [
        {"edge_type": "MENTIONS", "target": inv["components"][0],
         "evidence_span": "x", "note": ""},
    ]
    tmpl["_meta"]["status"] = "ANNOTATED"
    tmpl["_meta"]["annotator"] = "test-fixture"
    for item in tmpl["items"]:
        item["annotation_status"] = "REVIEWED"
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(tmpl))

    proposals = [
        {"source_id": first["req_id"], "edge_type": "MENTIONS",
         "target": inv["components"][0]},
        {"source_id": first["req_id"], "edge_type": "MENTIONS", "target": "BOGUS"},
    ]
    prop_path = tmp_path / "proposals.json"
    prop_path.write_text(json.dumps(proposals))

    report = hev.score(gold_path, prop_path)
    m = report["per_edge_type_vs_human"]["MENTIONS"]
    assert m["true_positives"] == 1
    assert m["false_positives"] == 1  # BOGUS
    assert "surrogate_gap" in report
    assert "independence" in report
    assert report["out_of_inventory_observations"] == []


def test_null_targets_become_observations_not_pairs(tmp_path):
    """target: null entries are coverage observations, never (req, None) pairs.

    Two distinct unknown entities on ONE requirement must both survive as
    separate observations (a set of (req, None) pairs would collapse them),
    and neither may leak into gold pairs, P/R/F1, or dictionary-miss sets.
    """
    reqs = get_all_requirements()
    subset = hev.sample_subset(reqs, 20)
    inv = hev.build_inventory()
    tmpl = hev.build_template(subset, inv)
    first = tmpl["items"][0]
    first["edges"] = [
        {"edge_type": "MENTIONS", "target": inv["components"][0],
         "evidence_span": "x", "note": ""},
        {"edge_type": "MENTIONS", "target": None,
         "evidence_span": "scratchpad", "note": "scratchpad unit not in inventory"},
        {"edge_type": "MENTIONS", "target": None,
         "evidence_span": "EDC", "note": "EDC not in inventory"},
    ]
    tmpl["_meta"]["status"] = "ANNOTATED"
    tmpl["_meta"]["annotator"] = "test-fixture"
    for item in tmpl["items"]:
        item["annotation_status"] = "REVIEWED"
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(tmpl))

    edges, observations = hev.gold_edges(json.loads(gold_path.read_text()))
    assert (first["req_id"], None) not in edges["MENTIONS"]
    assert len(observations) == 2  # distinct unknowns do not collapse
    assert {o["evidence_span"] for o in observations} == {"scratchpad", "EDC"}

    prop_path = tmp_path / "proposals.json"
    prop_path.write_text(json.dumps([]))
    report = hev.score(gold_path, prop_path)
    assert len(report["out_of_inventory_observations"]) == 2
    gap = report["surrogate_gap"]["MENTIONS"]
    assert all(t is not None for _, t in gap["dictionary_misses"])
