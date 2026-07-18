"""Unit tests for quality scoring."""

import pytest

from specguard.core.quality_scorer import (
    QualityScores,
    _has_measurable_criterion,
    score_requirement,
)
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


class TestMeasurablePatternFixes:
    """G5 regression tests: quantification idioms recognized after the
    spec-kit pilot (results/speckit_pilot/pilot_report.md).

    The headline bug: in the old `(?:%|percent)\\b` the trailing \\b after '%'
    can never match before whitespace, so "90%" was never measurable.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "95% of searches return results in under 1 second.",  # % boundary bug
            "Users can complete checkout in under 3 minutes.",  # under-N + minutes
            "Data shall be retained for 7 years.",  # calendar unit
            "The service sustains 1,000 concurrent requests.",  # comma numeral
            "Ingestion completes with zero data loss.",  # exact zero-count
            "The monitor raises no more than 2 false alerts.",  # bounded comparator
        ],
    )
    def test_quantified_text_is_measurable(self, text):
        assert _has_measurable_criterion(text)

    def test_unquantified_text_not_measurable(self):
        assert not _has_measurable_criterion("Users are satisfied with the experience.")
