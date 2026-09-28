"""Unit tests for the smell detector — covers the canonical 11 smell types."""


import pytest

from specguard.core.smell_detector import SmellType, analyze_requirement, detect_ambiguity


class TestAmbiguityDetection:
    @pytest.mark.parametrize(
        "compound", ["lightning-fast", "business-safe", "custom-thread-safe", "fail-safe-ish"]
    )
    def test_unknown_compounds_keep_ambiguous_terms(self, compound):
        assert detect_ambiguity(f"The service shall be {compound}.")

    @pytest.mark.parametrize("compound", ["fail-safe", "thread-safe", "share-safe", "FAIL-SAFE"])
    def test_recognized_technical_compounds_are_exempt(self, compound):
        assert not detect_ambiguity(f"The service shall be {compound}.")

    def test_detects_subjective_adjective(self):
        report = analyze_requirement("T1", "The system shall be fast.")
        assert SmellType.AMBIGUITY in report.smell_types_found

    def test_clean_requirement_has_no_ambiguity(self):
        report = analyze_requirement("T2", "The system shall respond within 100 ms.")
        assert SmellType.AMBIGUITY not in report.smell_types_found


class TestPlaceholderDetection:
    def test_detects_tbd(self):
        report = analyze_requirement("T3", "TBD: Performance target.")
        assert SmellType.PLACEHOLDER in report.smell_types_found

    def test_placeholder_is_high_severity(self):
        report = analyze_requirement("T4", "TBD: Performance target.")
        hits = [h for h in report.hits if h.smell_type == SmellType.PLACEHOLDER]
        assert hits, "Expected at least one placeholder hit"
        assert all(h.severity == "high" for h in hits)

    def test_detects_tbc(self):
        report = analyze_requirement("T5", "The system shall support TBC modes.")
        assert SmellType.PLACEHOLDER in report.smell_types_found


class TestVaguenessDetection:
    def test_detects_some(self):
        report = analyze_requirement("T6", "Some configurations shall be cacheable.")
        assert SmellType.VAGUENESS in report.smell_types_found

    def test_detects_several(self):
        report = analyze_requirement("T7", "Several modules shall support redundancy.")
        assert SmellType.VAGUENESS in report.smell_types_found


class TestOptionalityDetection:
    def test_detects_if_possible(self):
        report = analyze_requirement("T8", "The module shall cache results if possible.")
        assert SmellType.OPTIONALITY in report.smell_types_found

    def test_detects_where_applicable(self):
        text = "The system shall use hardware acceleration where applicable."
        report = analyze_requirement("T9", text)
        assert SmellType.OPTIONALITY in report.smell_types_found

    def test_shall_with_no_optional_phrase_has_no_optionality(self):
        report = analyze_requirement("T10", "The system shall support all features.")
        assert SmellType.OPTIONALITY not in report.smell_types_found


class TestComparativeDetection:
    def test_detects_faster(self):
        report = analyze_requirement("T11", "The module shall execute faster.")
        assert SmellType.COMPARATIVE in report.smell_types_found

    def test_detects_more_efficient(self):
        report = analyze_requirement("T12", "The system shall be more efficient.")
        assert SmellType.COMPARATIVE in report.smell_types_found

    def test_detects_lower(self):
        report = analyze_requirement("T13", "The system shall have lower latency.")
        assert SmellType.COMPARATIVE in report.smell_types_found


class TestSubjectivityDetection:
    def test_detects_as_appropriate(self):
        report = analyze_requirement("T14", "The system shall log errors as appropriate.")
        hits = [h for h in report.hits if h.smell_type == SmellType.SUBJECTIVITY]
        assert len(hits) == 1
        assert hits[0].trigger == "as appropriate"
        assert hits[0].severity == "medium"

    def test_no_subjectivity_in_measurable_requirement(self):
        report = analyze_requirement("T15", "The system shall log errors within 100 ms.")
        assert SmellType.SUBJECTIVITY not in report.smell_types_found

    def test_as_appropriate_is_subjectivity_not_optionality(self):
        report = analyze_requirement("T16", "The cache shall be flushed as appropriate.")
        assert SmellType.SUBJECTIVITY in report.smell_types_found
        assert SmellType.OPTIONALITY not in report.smell_types_found


class TestWeaknessDetection:
    def test_detects_might(self):
        report = analyze_requirement("T17", "The interface might support legacy protocols.")
        hits = [h for h in report.hits if h.smell_type == SmellType.WEAKNESS]
        assert len(hits) == 1
        assert hits[0].trigger == "might"
        assert hits[0].severity == "high"

    def test_detects_are_encouraged_to(self):
        report = analyze_requirement("T18", "Developers are encouraged to use the new API.")
        hits = [h for h in report.hits if h.smell_type == SmellType.WEAKNESS]
        assert len(hits) == 1
        assert hits[0].trigger == "are encouraged to"

    def test_no_weakness_for_rfc2119_should(self):
        report = analyze_requirement("T19", "The system should retry the request.")
        assert SmellType.WEAKNESS not in report.smell_types_found

    def test_no_weakness_for_rfc2119_may(self):
        report = analyze_requirement("T20", "The user may cancel the operation.")
        assert SmellType.WEAKNESS not in report.smell_types_found


class TestNonVerifiableDetection:
    def test_detects_handle_with_modal(self):
        report = analyze_requirement("T21", "The core shall handle error conditions.")
        hits = [h for h in report.hits if h.smell_type == SmellType.NON_VERIFIABLE]
        assert len(hits) == 1
        assert hits[0].trigger == "handle"
        assert hits[0].severity == "low"

    def test_no_flag_without_modal_context(self):
        report = analyze_requirement("T22", "Error handling is implemented in the driver.")
        assert SmellType.NON_VERIFIABLE not in report.smell_types_found


class TestNegativeStatementDetection:
    def test_detects_simple_negation(self):
        report = analyze_requirement("T23", "The system shall not crash.")
        hits = [h for h in report.hits if h.smell_type == SmellType.NEGATIVE_STATEMENT]
        assert len(hits) == 1
        assert hits[0].severity == "low"

    def test_detects_double_negation_as_high(self):
        report = analyze_requirement("T24", "The system shall not fail to log errors.")
        hits = [h for h in report.hits if h.smell_type == SmellType.NEGATIVE_STATEMENT]
        assert len(hits) == 1
        assert hits[0].severity == "high"

    def test_double_negation_suppresses_simple_overlap(self):
        report = analyze_requirement("T25", "The system shall not fail to log errors.")
        low_hits = [h for h in report.hits
                    if h.smell_type == SmellType.NEGATIVE_STATEMENT and h.severity == "low"]
        assert len(low_hits) == 0

    def test_no_negative_statement_in_positive_requirement(self):
        report = analyze_requirement("T26", "The system shall log all errors.")
        assert SmellType.NEGATIVE_STATEMENT not in report.smell_types_found


class TestOptionalityRefactorCorrectness:
    def test_if_possible_still_triggers_optionality(self):
        report = analyze_requirement("T27", "The module shall cache results if possible.")
        assert SmellType.OPTIONALITY in report.smell_types_found

    def test_if_applicable_still_triggers_optionality(self):
        report = analyze_requirement(
            "T28", "The system shall use hardware acceleration where applicable."
        )
        assert SmellType.OPTIONALITY in report.smell_types_found


class TestSpecKitPilotFixes:
    """Regression tests for lexical-collision fixes G1-G4 from the spec-kit
    pilot (results/speckit_pilot/pilot_report.md)."""

    # G1 — comma-grouped numerals tokenize as one number
    def test_comma_grouped_numeral_is_one_token(self):
        report = analyze_requirement("G1a", "The queue shall hold 1,000 pending entries.")
        hits = [h for h in report.hits if h.smell_type == SmellType.MISSING_UNIT]
        assert [h.trigger for h in hits] == ["1,000"]  # not the "000" tail artifact

    def test_comma_grouped_numeral_with_unit_not_flagged(self):
        report = analyze_requirement("G1b", "The link shall tolerate 1,000 ms of delay.")
        assert SmellType.MISSING_UNIT not in report.smell_types_found

    # G2 — "how many" is interrogative, not an imprecise quantifier
    def test_how_many_not_vague(self):
        report = analyze_requirement("G2a", "The tool shall report how many lines were skipped.")
        assert SmellType.VAGUENESS not in report.smell_types_found

    def test_plain_many_still_vague(self):
        report = analyze_requirement("G2b", "Many interrupts shall be maskable.")
        assert SmellType.VAGUENESS in report.smell_types_found

    def test_show_many_still_vague(self):
        # 'show' must not satisfy the 'how' guard (word boundary required)
        report = analyze_requirement("G2c", "The UI shall show many results.")
        assert SmellType.VAGUENESS in report.smell_types_found

    # G3 — calendar units are units
    def test_calendar_units_not_missing_unit(self):
        report = analyze_requirement("G3a", "Logs shall be retained for at least 12 months.")
        assert SmellType.MISSING_UNIT not in report.smell_types_found

    def test_unitless_number_still_flagged(self):
        report = analyze_requirement("G3b", "The buffer shall hold 128 pending entries.")
        assert SmellType.MISSING_UNIT in report.smell_types_found

    # G4 — comparative + technical noun is a noun phrase, not a comparison
    def test_lower_limit_noun_phrase_not_comparative(self):
        report = analyze_requirement(
            "G4a", "Operators shall set a lower limit, an upper limit, or both."
        )
        assert SmellType.COMPARATIVE not in report.smell_types_found

    def test_bare_lower_still_comparative(self):
        report = analyze_requirement("G4b", "The system shall have lower latency.")
        assert SmellType.COMPARATIVE in report.smell_types_found


class TestInTheWildCorpusFixes:
    """Regression tests for lexical-collision fixes G6-G9 from the in-the-wild
    spec-kit corpus (integrations/spec-kit-specguard/experiments)."""

    # G6 — identifier numerals are names, not quantities
    def test_hyphenated_identifier_not_missing_unit(self):
        report = analyze_requirement(
            "G6a", "The run MUST refuse the misplaced case of FR-036 as ADR-0015 records."
        )
        assert SmellType.MISSING_UNIT not in report.smell_types_found

    def test_hash_and_ratio_identifiers_not_missing_unit(self):
        report = analyze_requirement("G6b", "Issue #17 shall stay open until 7/7 checks pass.")
        assert SmellType.MISSING_UNIT not in report.smell_types_found

    def test_ordinal_label_not_missing_unit(self):
        report = analyze_requirement(
            "G6c", "Pass 0 MUST NOT write files and Phase 4 shall follow ISO 14971 guidance."
        )
        assert SmellType.MISSING_UNIT not in report.smell_types_found

    def test_quantity_after_identifier_still_flagged(self):
        report = analyze_requirement("G6d", "FR-036 shall allow 12 retries.")
        assert [h.trigger for h in report.hits if h.smell_type == SmellType.MISSING_UNIT] == [
            "12"
        ]

    # G7 — recognized technical compounds retain their exception
    def test_fail_safe_not_ambiguous(self):
        report = analyze_requirement("G7a", "The artifact shall be left untouched (fail-safe).")
        assert SmellType.AMBIGUITY not in report.smell_types_found

    def test_intensifier_compound_still_ambiguous(self):
        report = analyze_requirement("G7b", "The parser shall be super-fast.")
        assert SmellType.AMBIGUITY in report.smell_types_found

    def test_bare_safe_still_ambiguous(self):
        report = analyze_requirement("G7c", "Validation MUST enforce safe paths.")
        assert SmellType.AMBIGUITY in report.smell_types_found

    # G8 — 'clean' collocations and verb use are precise
    def test_clean_clone_not_ambiguous(self):
        report = analyze_requirement(
            "G8a", "All checks MUST run to completion on a clean clone and a clean working tree."
        )
        assert SmellType.AMBIGUITY not in report.smell_types_found

    def test_clean_as_verb_not_ambiguous(self):
        report = analyze_requirement("G8b", "The tool MUST clean the cache after each run.")
        assert SmellType.AMBIGUITY not in report.smell_types_found

    def test_clean_design_still_ambiguous(self):
        report = analyze_requirement("G8c", "The dashboard shall have a clean design.")
        assert SmellType.AMBIGUITY in report.smell_types_found

    # G9 — 'could not' is past-tense inability, not a softened modal
    def test_could_not_not_weak(self):
        report = analyze_requirement(
            "G9a", "The report MUST name the file and the reason it could not be loaded."
        )
        assert SmellType.WEAKNESS not in report.smell_types_found

    def test_could_still_weak(self):
        report = analyze_requirement("G9b", "The system could cache results.")
        assert SmellType.WEAKNESS in report.smell_types_found


class TestSmellReport:
    def test_smell_types_found_property(self):
        report = analyze_requirement("T12", "The system shall be fast.")
        assert isinstance(report.smell_types_found, set)

    def test_clean_requirement_has_no_hits(self):
        isa_req = (
            "The CVA6 processor shall implement the RV64GC ISA"
            " in compliance with [RVunpriv] v20191213."
        )
        report = analyze_requirement("T13", isa_req)
        assert len(report.hits) == 0
