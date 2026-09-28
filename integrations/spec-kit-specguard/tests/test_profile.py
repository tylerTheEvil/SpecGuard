"""Profile rules P1/P2/P4/NC/P3 and lock-step with the vendored core scorer."""

from __future__ import annotations

import pytest
from specguard_speckit._vendor.specguard_core.quality_scorer import (
    compute_completeness,
    score_requirement,
)
from specguard_speckit._vendor.specguard_core.smell_detector import (
    SmellReport,
    SmellType,
    analyze_requirement,
)
from specguard_speckit.assess import assess_requirement
from specguard_speckit.model import Requirement
from specguard_speckit.profile import (
    BINARY,
    QUANTIFIED,
    UNMEASURED,
    combine,
    measurability_class,
    score_outcome,
)


def req(text: str, kind: str = "FR", markers=None) -> Requirement:
    return Requirement(req_id=f"{kind}-001", kind=kind, text=text, raw=text, line=1,
                       markers=list(markers or []))


class TestRegisterRules:
    def test_p1_entity_count_suppressed(self):
        res = assess_requirement(req("The album MUST hold up to 500 photos."))
        assert SmellType.MISSING_UNIT not in {h.smell_type for h in res.hits}
        assert [s.rule for s in res.suppressed] == ["P1"]

    def test_p1_comma_grouped_count(self):
        res = assess_requirement(req("The service MUST serve 1,000 concurrent users."))
        assert [s.rule for s in res.suppressed] == ["P1"]

    def test_p1_count_with_two_modifiers(self):
        res = assess_requirement(req("The service MUST sustain 1,000 concurrent redirect calls."))
        assert [s.rule for s in res.suppressed] == ["P1"]

    def test_p1_keeps_bare_number(self):
        res = assess_requirement(req("The timeout MUST be 30 after the last request."))
        assert SmellType.MISSING_UNIT in {h.smell_type for h in res.hits}

    def test_p2_any_suppressed(self):
        res = assess_requirement(req("The system MUST reject any expired code."))
        assert not res.hits
        assert [s.rule for s in res.suppressed] == ["P2"]

    def test_p4_different_suppressed(self):
        res = assess_requirement(req("A token for a different repository MUST be rejected."))
        assert [s.rule for s in res.suppressed] == ["P4"]

    def test_other_vagueness_kept(self):
        res = assess_requirement(req("The report MUST list several causes."))
        assert SmellType.VAGUENESS in {h.smell_type for h in res.hits}

    def test_default_profile_keeps_everything(self):
        res = assess_requirement(req("The system MUST reject any expired code."), "default")
        assert SmellType.VAGUENESS in {h.smell_type for h in res.hits}
        assert res.suppressed == []


class TestClarificationMarkers:
    def test_marker_becomes_high_placeholder_hit(self):
        res = assess_requirement(req("The export MUST be delivered as", markers=["format?"]))
        placeholders = [h for h in res.hits if h.smell_type == SmellType.PLACEHOLDER]
        assert len(placeholders) == 1 and placeholders[0].severity == "high"
        assert res.gate != "PASS"

    def test_default_profile_adds_no_marker_hit(self):
        res = assess_requirement(req("The export MUST be delivered as", markers=["x"]), "default")
        assert SmellType.PLACEHOLDER not in {h.smell_type for h in res.hits}


class TestMeasurability:
    @pytest.mark.parametrize("text", [
        "90% of readers bookmark a recipe in under 5 seconds.",
        "The list opens within 2 seconds.",
        "Reconcile issues no more than 3 writes per run.",
        "The export completes for 10,000 accounts.",
        "7/7 release checks are green.",
    ])
    def test_quantified(self, text):
        assert measurability_class(text) == QUANTIFIED

    @pytest.mark.parametrize("text", [
        "Two runs over identical inputs produce byte-identical reports.",
        "Every accepted invitation adds exactly one member.",
        "The command never blocks waiting for input.",
        "An unknown key exits with code 3.",
    ])
    def test_binary(self, text):
        assert measurability_class(text) == BINARY

    def test_function_words_are_not_count_modifiers(self):
        # "0 on all runs" is not a count of runs; the exit predicate makes it BINARY
        assert measurability_class("The command exits 0 on all runs") == BINARY

    def test_count_with_modifiers_is_quantified(self):
        text = "The service sustains 1,000 concurrent redirect requests without errors."
        assert measurability_class(text) == QUANTIFIED

    @pytest.mark.parametrize("text", [
        "Users see results instantly.",
        "Invited people find joining the team straightforward.",
        "Operators trust the dashboard.",
        # rank cut-off, not an outcome magnitude (pilot 003/SC-006)
        "An operator can name the top 5 endpoints from the report alone.",
    ])
    def test_unmeasured(self, text):
        assert measurability_class(text) == UNMEASURED

    def test_known_false_negative_is_documented_behaviour(self):
        # Lexicon limit (docs/checks.md): an absolute quantifier makes a
        # subjective outcome look binary.
        assert measurability_class("All users are satisfied.") == BINARY


class TestOutcomeRegister:
    def test_unmeasured_sc_warns(self):
        res = assess_requirement(req("Users see results instantly.", kind="SC"))
        assert res.sc_class == UNMEASURED and res.gate == "WARN"

    def test_quantified_sc_passes_without_modal(self):
        res = assess_requirement(req("95% of searches return results in under 1 second.", "SC"))
        assert res.sc_class == QUANTIFIED and res.gate == "PASS"

    def test_binary_sc_passes(self):
        res = assess_requirement(req("Every export is byte-identical across runs.", "SC"))
        assert res.sc_class == BINARY and res.gate == "PASS"

    def test_default_profile_scores_sc_like_core(self):
        text = "95% of searches return results in under 1 second."
        res = assess_requirement(req(text, "SC"), "default")
        core = score_requirement(text, analyze_requirement("SC-001", text))
        assert res.sc_class is None
        assert res.scores.overall == core.overall


class TestLockStepWithCore:
    """The profile mirrors core constants; these tests fail if the core moves."""

    @pytest.mark.parametrize("text", [
        "The CVA6 cache MUST respond within 3 cycles.",
        "The system shall be fast and TBD.",
        "Users MUST be able to export data.",
    ])
    def test_combine_matches_core_weights(self, text):
        core = score_requirement(text, analyze_requirement("X", text))
        assert combine(core.completeness, core.consistency, core.verifiability) == core.overall

    @pytest.mark.parametrize("text", [
        "The CVA6 cache MUST respond within 3 cycles.",
        "The system shall be fast and TBD.",
        "Users MUST be able to export data.",
    ])
    def test_outcome_completeness_equals_core_when_modal_present(self, text):
        report = analyze_requirement("X", text)
        ours = score_outcome(text, report, QUANTIFIED).completeness
        assert ours == compute_completeness(text, report)

    def test_fr_path_is_core_exactly(self):
        text = "The CVA6 cache MUST respond within 3 cycles."
        res = assess_requirement(req(text))
        core = score_requirement(text, SmellReport("FR-001", text, res.hits))
        assert res.scores == core
