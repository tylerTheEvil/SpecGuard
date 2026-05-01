"""Unit tests for quality scoring."""

import pytest

from specguard.core.quality_scorer import QualityScores, score_requirement
from specguard.core.smell_detector import analyze_requirement


class TestScoreRequirement:
    def test_returns_quality_scores(self):
        report = analyze_requirement("T1", "The system shall respond within 100 ms.")
        scores = score_requirement("The system shall respond within 100 ms.", report)
        assert isinstance(scores, QualityScores)

    def test_scores_in_unit_interval(self):
        report = analyze_requirement("T2", "The system shall respond within 100 ms.")
        scores = score_requirement("The system shall respond within 100 ms.", report)
        for attr in ("completeness", "consistency", "verifiability", "overall"):
            v = getattr(scores, attr)
            assert 0.0 <= v <= 1.0, f"{attr} out of [0, 1]: {v}"

    def test_vague_requirement_lower_verifiability(self):
        clean_report = analyze_requirement("T3", "The system shall respond within 100 ms.")
        clean = score_requirement("The system shall respond within 100 ms.", clean_report)
        vague_report = analyze_requirement("T4", "The system shall be fast.")
        vague = score_requirement("The system shall be fast.", vague_report)
        assert vague.verifiability < clean.verifiability

    def test_overall_is_weighted_combination(self):
        report = analyze_requirement("T5", "The system shall be fast.")
        scores = score_requirement("The system shall be fast.", report)
        expected = round(
            0.30 * scores.completeness + 0.25 * scores.consistency + 0.45 * scores.verifiability, 3
        )
        assert scores.overall == pytest.approx(expected, abs=0.001)
