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
