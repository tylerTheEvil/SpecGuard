"""Tests for the opt-in structural smells (core.structure).

Positive cases reuse the smell examples of Veizaga et al. (2024), Table III,
so the adaptation can be checked against its source; negative cases pin the
false-positive guards found on CVA6 and on PX4-style wording.
"""

import pytest

from specguard.core import assess_requirement
from specguard.core.smell_detector import analyze_requirement
from specguard.core.structure import (
    StructuralSmellType as S,
)
from specguard.core.structure import (
    analyze_structure,
    detect_structural_smells,
    segment_requirement,
)
from specguard.data.cva6_requirements import get_all_requirements


def kinds(text: str) -> set[S]:
    return {h.smell_type for h in detect_structural_smells(text)}


class TestSegmentation:
    def test_ears_event_driven(self):
        s = segment_requirement("When the RC link is lost, the FC shall enter failsafe mode.")
        assert s.condition == "When the RC link is lost"
        assert s.actor == "the FC"
        assert s.modal == "shall"
        assert s.response == "enter failsafe mode."

    def test_ubiquitous(self):
        s = segment_requirement("The FC shall respond within 100 ms.")
        assert s.condition is None
        assert s.actor == "The FC"

    def test_actor_undecidable_without_separator(self):
        # No comma: the actor is inside the condition text; a parser would be
        # needed, so the segmenter must not claim it is missing.
        s = segment_requirement("When the link is lost the FC shall land.")
        assert s.actor is None
        assert S.INCOMPLETE_RESPONSE not in kinds("When the link is lost the FC shall land.")

    def test_negative_modal(self):
        s = segment_requirement("The FC shall not arm while the GPS fix is invalid.")
        assert s.modal == "shall not"


class TestPaskaExamples:
    """Veizaga et al. (2024) Table III examples (anonymised there)."""

    def test_non_atomic_two_actions(self):
        text = (
            "System-A must add System-B to their downstream systems "
            "and allow System-C to subscribe."
        )
        assert S.NON_ATOMIC in kinds(text)

    def test_incomplete_requirement(self):
        text = (
            "When System-A receives a message from Security Manager and if the "
            "message is part of the B-file, according to the mapping rules."
        )
        assert S.INCOMPLETE_REQUIREMENT in kinds(text)

    def test_incorrect_order(self):
        text = (
            "When the user is on the Utilities page, System-A must open the Alert "
            "section when the user launches System-A."
        )
        assert S.INCORRECT_ORDER in kinds(text)

    def test_coordination_ambiguity(self):
        text = (
            "When System-A performs eligibility check for a participant or if the "
            "holding type is complex, then System-B must reject the instruction."
        )
        assert S.COORDINATION_AMBIGUITY in kinds(text)

    def test_not_a_requirement(self):
        text = "The R6 instruction defines the original instruction."
        assert kinds(text) == {S.NOT_A_REQUIREMENT}

    def test_missing_modal_with_condition(self):
        # Paska's "incomplete system response" example lacks the modal verb.
        text = "When the user clicks on the Filter button, System-A opens the Filter screen."
        assert S.INCOMPLETE_REQUIREMENT in kinds(text)

    def test_passive_condition(self):
        text = (
            "When a rejection order is received for a cancellation request, "
            "System-A must raise a web alert."
        )
        assert S.PASSIVE_VOICE in kinds(text)


class TestOtherPositives:
    def test_missing_actor(self):
        text = "When the RC link is lost, shall enter failsafe mode."
        assert S.INCOMPLETE_RESPONSE in kinds(text)

    def test_empty_response(self):
        assert S.INCOMPLETE_RESPONSE in kinds("The FC shall.")

    def test_two_modal_clauses(self):
        assert S.NON_ATOMIC in kinds("The FC shall arm the motors. The FC shall log the event.")

    def test_mixed_and_or(self):
        text = (
            "When the link is lost or the battery is low and the vehicle is "
            "in mission mode, the FC shall land."
        )
        assert S.COORDINATION_AMBIGUITY in kinds(text)

    def test_passive_response_without_agent(self):
        assert S.PASSIVE_VOICE in kinds("The parameter shall be set to 5.")


class TestFalsePositiveGuards:
    @pytest.mark.parametrize(
        "text",
        [
            "When battery voltage drops below 10.5 V, the FC shall initiate RTL within 1 s.",
            "While the vehicle is armed, the FC shall reject parameter writes.",
            "The FC shall respond within 100 ms.",
            "The parameter shall be set to 5 by the operator.",
            "The FC shall hold altitude while maintaining heading.",
            "The module shall cache results if possible.",  # optionality, not order
            "FENCE.T should be available in all modes (machine, user and hypervisor if present).",
            "CVA6 shall have a coprocessor interface of the [CV-X-IF] specification.",
            "L1WTD shall have a command that invalidates the content of a line upon request.",
            "L1WTD shall reflect all writes within a bounded number of cycles. "
            "The bound is fixed but not specified here.",
        ],
    )
    def test_clean(self, text):
        assert kinds(text) == set()

    def test_while_condition_is_a_state_not_passive(self):
        text = "While the GPS fix is degraded, the FC shall hold position."
        assert S.PASSIVE_VOICE not in kinds(text)


class TestOptInContract:
    def test_default_detectors_do_not_emit_structural_smells(self):
        report = analyze_requirement("R", "The R6 instruction defines the original instruction.")
        assert not any(isinstance(h.smell_type, S) for h in report.hits)

    def test_default_gate_unchanged_on_cva6(self):
        # Published Layer 1 numbers must reproduce without the flag.
        reqs = get_all_requirements()
        base = [assess_requirement(r.req_id, r.text).gate_decision for r in reqs]
        assert base.count("PASS") == 61 and base.count("WARN") == 1 and base.count("FAIL") == 2

    def test_structural_flag_adds_hits_and_affects_score(self):
        text = "System-A must add System-B to downstream systems and allow System-C to subscribe."
        off = assess_requirement("R", text)
        on = assess_requirement("R", text, structural=True)
        assert S.NON_ATOMIC in on.smell_report.smell_types_found
        assert on.quality_scores.overall < off.quality_scores.overall

    def test_report_shape_matches_lexical_report(self):
        report = analyze_structure("R", "The FC shall.")
        assert report.requirement_id == "R"
        assert report.severity_counts["medium"] >= 1
        assert all(h.smell_type.value for h in report.hits)
