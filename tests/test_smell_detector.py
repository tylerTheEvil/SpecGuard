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
