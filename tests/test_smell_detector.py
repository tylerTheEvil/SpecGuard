"""Unit tests for the smell detector — covers the canonical 11 smell types."""


from specguard.core.smell_detector import SmellType, analyze_requirement


class TestAmbiguityDetection:
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
        report = analyze_requirement("T28", "The system shall use hardware acceleration where applicable.")
        assert SmellType.OPTIONALITY in report.smell_types_found


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
