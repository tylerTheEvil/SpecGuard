"""spec.md parser: template form, in-the-wild format drift, markers, stories."""

from __future__ import annotations

import pytest
from specguard_speckit.parse_spec import parse_spec, strip_markup


class TestRequirementForms:
    @pytest.mark.parametrize(
        "opening,inner,closing",
        [
            ("````markdown", "```python", "````"),
            ("~~~markdown", "```", "~~~"),
            ("```markdown", "~~~", "```"),
            ("```markdown", "```python", "`````  "),
            ("~~~~markdown", "~~~", "~~~~"),
        ],
    )
    def test_fence_closes_only_with_matching_character_length_and_no_info(
        self, opening, inner, closing
    ):
        doc = parse_spec("\n".join([
            opening, inner,
            "- **FR-999**: Example [NEEDS CLARIFICATION: example only].",
            closing, "## Requirements",
            "- **FR-001**: The system shall respond within 10 ms.",
        ]))
        assert doc.ids() == ["FR-001"]
        assert doc.requirements[0].line == 6
        assert doc.markers == []

    def test_unclosed_fence_hides_remaining_examples(self):
        assert parse_spec("````markdown\n```\n- **FR-999**: Example.\n").ids() == []

    def test_backtick_in_info_string_is_not_a_fence_opener(self):
        assert parse_spec("```example`text\n- **FR-001**: Real requirement.\n").ids() == [
            "FR-001"
        ]

    def test_all_definition_variants_found_once(self, fixture_text):
        doc = parse_spec(fixture_text("spec_formats.md"))
        assert doc.ids() == [
            "FR-001", "FR-002", "FR-003", "FR-004", "FR-005", "FR-006", "FR-011",
            "SC-001", "NFR-001",
        ]

    def test_references_in_prose_tables_and_fences_are_not_definitions(self, fixture_text):
        ids = parse_spec(fixture_text("spec_formats.md")).ids()
        for ref_only in ("FR-007", "FR-008", "FR-009", "FR-010"):
            assert ref_only not in ids

    def test_bold_title_kept_in_text(self, fixture_text):
        doc = parse_spec(fixture_text("spec_formats.md"))
        fr2 = next(r for r in doc.requirements if r.req_id == "FR-002")
        assert fr2.text.startswith("Titles inside bold. The parser MUST")

    def test_wrapped_lines_and_sub_bullets_joined(self, fixture_text):
        doc = parse_spec(fixture_text("spec_formats.md"))
        fr5 = next(r for r in doc.requirements if r.req_id == "FR-005")
        assert fr5.text == (
            "The parser MUST join wrapped lines into one requirement text and include "
            "indented sub-bullets: (a) the first sub-item (b) the second sub-item"
        )

    def test_sibling_bullet_ends_requirement(self, fixture_text):
        doc = parse_spec(fixture_text("spec_formats.md"))
        fr6 = next(r for r in doc.requirements if r.req_id == "FR-006")
        assert "Plain sibling" not in fr6.text

    def test_kind_and_line_recorded(self, fixture_text):
        doc = parse_spec(fixture_text("spec_formats.md"))
        by_id = {r.req_id: r for r in doc.requirements}
        assert by_id["SC-001"].kind == "SC"
        assert by_id["NFR-001"].kind == "NFR"
        assert by_id["FR-001"].line == 23

    def test_custom_prefixes(self):
        doc = parse_spec("- **SR-001**: Tokens MUST rotate every 24 hours.\n", prefixes=("SR",))
        assert doc.ids() == ["SR-001"]

    def test_bold_title_wrapping_to_next_line(self):
        doc = parse_spec(
            "- **FR-015 — Ordering is proven by commit ancestry, against an anchor the\n"
            "  run records.** The check MUST fail on a non-ancestor.\n"
            "- **SC-010 (Lightness budget, codified per Clarifications\n"
            "  §Session 2)**: 95% of runs finish in under 2 seconds.\n"
        )
        assert doc.ids() == ["FR-015", "SC-010"]
        fr = doc.requirements[0]
        assert fr.text == ("Ordering is proven by commit ancestry, against an anchor the run "
                           "records. The check MUST fail on a non-ancestor.")
        assert "**" not in doc.requirements[1].text

    def test_unbolded_id_without_colon_is_prose(self):
        assert parse_spec("- FR-010 makes every unresolved run write nothing.\n").ids() == []


class TestMarkers:
    def test_open_marker_in_requirement_recorded_and_removed_from_text(self, fixture_text):
        doc = parse_spec(fixture_text("spec_open_marker.md"))
        fr2 = next(r for r in doc.requirements if r.req_id == "FR-002")
        assert fr2.markers == ["file format not specified - JSON, CSV, or both?"]
        assert "NEEDS CLARIFICATION" not in fr2.text
        assert [m.question for m in doc.markers] == [
            "file format not specified - JSON, CSV, or both?"
        ]

    def test_bare_mention_has_no_question(self, fixture_text):
        doc = parse_spec(fixture_text("spec_structural.md"))
        assert [(m.line, m.question) for m in doc.markers] == [(28, None)]

    def test_markers_in_comments_and_fences_ignored(self, fixture_text):
        assert parse_spec(fixture_text("spec_template_leftovers.md")).markers == []
        assert parse_spec(fixture_text("spec_formats.md")).markers == []


class TestStories:
    def test_priority_title_and_scenarios(self, fixture_text):
        doc = parse_spec(fixture_text("spec_clean.md"))
        assert [(s.label, s.priority) for s in doc.stories] == [("US1", "P1"), ("US2", "P2")]
        assert doc.stories[0].title == "Bookmark a recipe"
        assert [s.is_gwt for s in doc.stories[0].scenarios] == [True, True]

    def test_emdash_heading_and_mvp_marker(self, fixture_text):
        story = parse_spec(fixture_text("spec_formats.md")).stories[0]
        assert (story.label, story.priority, story.title) == ("US1", "P1", "Parse every variant")

    def test_short_story_heading_form(self):
        doc = parse_spec("### US1 — Triage act versus escalate (P1)\n\n"
                         "### US2 — Know whether a label is measured\n")
        assert [(s.label, s.priority, s.title) for s in doc.stories] == [
            ("US1", "P1", "Triage act versus escalate"),
            ("US2", None, "Know whether a label is measured"),
        ]

    def test_usage_heading_is_not_a_story(self):
        assert parse_spec("### Usage\n\n### USB support\n").stories == []

    def test_deeper_heading_stays_in_story(self, fixture_text):
        story = parse_spec(fixture_text("spec_formats.md")).stories[0]
        assert [s.line for s in story.scenarios] == [9, 13]

    def test_wrapped_scenario_lines_joined(self):
        # in-the-wild form: "**Then**" on a continuation line of the list item
        doc = parse_spec(
            "### User Story 1 - Validate (Priority: P1)\n\n**Acceptance Scenarios**:\n\n"
            "1. **Given** a corpus where every record is well-formed, **When** the maintainer\n"
            "   runs validate, **Then** the command exits zero.\n"
            "2. **Given** a malformed record,\n"
            "   **When** validate runs,\n"
            "   **Then** it names the record.\n\n"
            "**Why this priority**: when it fails, then nothing else matters.\n"
        )
        story = doc.stories[0]
        assert [(s.line, s.is_gwt) for s in story.scenarios] == [(5, True), (7, True)]
        assert story.scenarios[0].text.endswith("the command exits zero.")

    def test_missing_priority_and_non_gwt_items(self, fixture_text):
        doc = parse_spec(fixture_text("spec_structural.md"))
        assert doc.stories[0].priority is None
        assert not any(s.is_gwt for s in doc.stories[1].scenarios)


class TestTemplateLeftovers:
    def test_placeholders_found_with_lines(self, fixture_text):
        found = parse_spec(fixture_text("spec_template_leftovers.md")).template_leftovers
        assert ("[FEATURE NAME]", 1) in found
        assert ("[DATE]", 3) in found
        assert ("[Brief Title]", 12) in found
        assert {p for p, line in found if line == 18} == {
            "[initial state]", "[action]", "[expected outcome]"
        }

    def test_filled_spec_has_none(self, fixture_text):
        assert parse_spec(fixture_text("spec_clean.md")).template_leftovers == []

    def test_generic_bracket_words_outside_gwt_not_flagged(self):
        doc = parse_spec("- **FR-001**: The log MUST record the [action] name.\n")
        assert doc.template_leftovers == []


def test_title():
    assert parse_spec("# Feature Specification: Recipe Bookmarks\n").title == "Recipe Bookmarks"


def test_strip_markup():
    assert strip_markup("**Bold** `code` *em* [link](http://x)  x") == "Bold code em link x"
