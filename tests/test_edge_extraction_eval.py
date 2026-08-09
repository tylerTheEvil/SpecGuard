"""Regression tests for the offline (mock) edge-extraction eval.

Pins the P0.1 payoff: REFERS_TO is scored as a first-class typed edge against
the builder's standards reference, not silently dropped. Runs the deterministic
mock provider over the 64 CVA6 requirements — no network, no live model.

``experiments`` is not an installed package, so it is added to ``sys.path``
(mirroring ``tests/test_independent_lexicon.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import edge_extraction_eval as ev  # noqa: E402


def _mock_report():
    return ev.run(ev._make_mock_provider(), provider_name="mock")


def test_refers_to_is_scored_first_class():
    report = _mock_report()
    per_type = report["per_edge_type"]
    # All four types are present; the three with references are scored.
    assert set(per_type) == {"MENTIONS", "REFERS_TO", "DERIVES_FROM", "MITIGATES"}

    refers = per_type["REFERS_TO"]
    # Builder emits 21 REFERS_TO edges (KNOWN_STANDARDS dictionary matcher).
    assert refers["ground_truth"] == 21
    # The mock proposes standard edges, so REFERS_TO is actually exercised.
    assert refers["proposed"] > 0
    # Scored, not dropped: precision/recall are real numbers.
    assert isinstance(refers["recall"], float)
    assert isinstance(refers["precision"], float)
    # Pair-level log carries REFERS_TO verdicts (TP/FP/FN), never "unscored".
    verdicts = {e["verdict"] for e in refers["edges"]}
    assert verdicts and "unscored" not in verdicts


def test_mentions_and_derives_still_scored():
    per_type = _mock_report()["per_edge_type"]
    assert per_type["MENTIONS"]["ground_truth"] == 75
    assert isinstance(per_type["MENTIONS"]["recall"], float)
    assert per_type["DERIVES_FROM"]["ground_truth"] == 3
    # MITIGATES stays counts-only (no ground truth), never silently scored.
    assert per_type["MITIGATES"]["ground_truth"] is None


def test_mock_refers_to_targets_are_known_standards():
    """Every mock REFERS_TO proposal targets a real standard id (guard-clean)."""
    from specguard.graph.builder import KNOWN_STANDARDS

    refers = _mock_report()["per_edge_type"]["REFERS_TO"]
    proposed_targets = {
        e["target"] for e in refers["edges"] if e["verdict"] in ("TP", "FP")
    }
    assert proposed_targets  # non-empty
    assert proposed_targets <= set(KNOWN_STANDARDS)


# ---------------------------------------------------------------------------
# Guard-rejection breakdown (Section V.D)
# ---------------------------------------------------------------------------


def test_guard_rejection_breakdown_consistent():
    """total == sum(by_reason); alias and audit log agree with it."""
    report = _mock_report()
    gr = report["guard_rejections"]
    assert set(gr) == {"total", "by_reason"}
    assert gr["total"] == sum(gr["by_reason"].values())
    # Every canonical reason is present (zero-filled), so "this guard fired
    # zero times" is a measured value, not a missing key.
    assert set(ev.GUARD_REJECTION_REASONS) <= set(gr["by_reason"])
    # Back-compat alias and the serialized audit log agree with the total.
    assert report["evidence_guard_rejections"] == gr["total"]
    assert len(report["rejected_proposals"]) == gr["total"]


def test_rejection_reasons_match_extractor():
    """Each extractor rejection path emits a reason in the canonical tuple.

    Exercises every guard in ``_validate_proposals`` with a minimal bad
    proposal; a renamed or newly added reason string fails here instead of
    silently landing outside the Section V.D breakdown.
    """
    from specguard.extraction.extractor import _validate_proposals

    text = "CVA6 shall support the FPU for RV64I."
    inventory = {
        "components": ["CVA6", "FPU"],
        "standards": ["RV64I"],
        "requirements": [],
    }
    ok = {"confidence": 0.9}
    bad_edges = [
        "not-a-dict",                                                  # non-object edge
        {"edge_type": "BOGUS", "target_entity": "FPU",
         "evidence_span": "the FPU", **ok},                            # unknown edge_type
        {"edge_type": "MENTIONS", "target_entity": "",
         "evidence_span": "the FPU", **ok},                            # missing target_entity
        {"edge_type": "MENTIONS", "target_entity": "FPU",
         "evidence_span": "   ", **ok},                                # empty evidence_span
        {"edge_type": "MENTIONS", "target_entity": "FPU",
         "evidence_span": "the MMU translates", **ok},                 # fabricated evidence_span
        {"edge_type": "MENTIONS", "target_entity": "NOT_IN_INVENTORY",
         "evidence_span": "the FPU", **ok},                            # target not in inventory
        # target type does not match edge type (standard under MENTIONS):
        {"edge_type": "MENTIONS", "target_entity": "RV64I",
         "evidence_span": "RV64I", **ok},
    ]
    result = _validate_proposals("REQ-1", text, bad_edges, inventory)

    assert not result.proposals
    reasons = {entry["reason"] for entry in result.rejected}
    # Every emitted reason is canonical, and every canonical reason was
    # exercised — the tuple and the extractor cannot drift apart silently.
    assert reasons == set(ev.GUARD_REJECTION_REASONS)


def test_unbound_evidence_flags_consistent():
    """Flag summary: total == len(proposals) == sum(by_edge_type); mock has 0.

    The mock replays literal dictionary tokens, so nothing is flagged — the
    zero is a measured value from a populated field, not a missing key.
    """
    report = _mock_report()
    flags = report["unbound_evidence_flags"]
    assert flags["total"] == sum(flags["by_edge_type"].values())
    assert flags["total"] == len(flags["proposals"])
    assert flags["total"] == 0
    # Pair-level logs carry the flag on every proposed (TP/FP) entry.
    for et in ("MENTIONS", "REFERS_TO"):
        for e in report["per_edge_type"][et]["edges"]:
            if e["verdict"] in ("TP", "FP"):
                assert e["evidence_names_target"] is True
