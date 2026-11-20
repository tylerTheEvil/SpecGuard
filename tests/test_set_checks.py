"""Tests for set-level screening (core.set_checks).

Criteria come from TfNSW T MU AM 06007 GU, App. E, Table 13 (necessary / no
duplicates; defined terms and acronyms; consistent terms). CVA6 cases pin the
false-positive guards that the in-repo dataset exposed.
"""

import json

import pytest

from specguard.cli import main
from specguard.core.set_checks import (
    defined_in_text,
    find_duplicates,
    find_term_variants,
    find_undefined_acronyms,
    load_glossary,
    run_set_checks,
)
from specguard.data.cva6_requirements import get_all_requirements


def cva6() -> list[tuple[str, str]]:
    return [(r.req_id, r.text) for r in get_all_requirements()]


def kinds(reqs, **kw):
    return {(d.a_id, d.b_id): (d.kind, d.variant_reason) for d in find_duplicates(reqs, **kw)}


class TestDuplicates:
    def test_exact_after_normalisation(self):
        reqs = [
            ("R1", "When the GNSS fix is lost, the FC shall enter Hold mode."),
            ("R2", "When GNSS fix is lost the FC shall enter Hold mode"),
        ]
        assert kinds(reqs) == {("R1", "R2"): ("exact", None)}

    def test_near_duplicate_wording(self):
        reqs = [
            ("R1", "The FC shall log every parameter change to the flight log."),
            ("R2", "The FC shall record every parameter change to the flight log."),
        ]
        assert kinds(reqs) == {("R1", "R2"): ("near", None)}

    def test_polarity_difference_is_not_a_duplicate(self):
        reqs = [
            ("R1", "The FC shall arm the motors when the safety switch is pressed."),
            ("R2", "The FC shall not arm the motors when the safety switch is pressed."),
        ]
        assert kinds(reqs) == {("R1", "R2"): ("variant", "polarity")}

    def test_modal_difference_is_not_a_duplicate(self):
        reqs = [
            ("R1", "The FC shall log every parameter change to the flight log."),
            ("R2", "The FC may log every parameter change to the flight log."),
        ]
        assert kinds(reqs) == {("R1", "R2"): ("variant", "polarity")}

    def test_parametric_family_is_a_variant(self):
        # CVA6 L1W-40 / L1I-20: same wording, different cache.
        found = kinds(cva6())
        assert found[("L1W-40", "L1I-20")] == ("variant", "parameter")

    def test_extension_names_are_parameters(self):
        # CVA6 ISA-140 / ISA-150 differ only in "Zcb" vs "Zcmp".
        assert kinds(cva6())[("ISA-140", "ISA-150")] == ("variant", "parameter")

    def test_unrelated_requirements_are_not_paired(self):
        reqs = [
            ("R1", "The FC shall respond within 100 ms."),
            ("R2", "The GCS shall display battery voltage in volts."),
        ]
        assert kinds(reqs) == {}

    def test_threshold_is_respected(self):
        reqs = [
            ("R1", "The FC shall log every parameter change to the flight log."),
            ("R2", "The FC shall record every parameter change to the flight log."),
        ]
        assert kinds(reqs, near_threshold=0.99) == {}


class TestAcronyms:
    def test_defined_in_text_both_directions(self):
        texts = [
            "The Inertial Measurement Unit (IMU) shall report attitude.",
            "GNSS (Global Navigation Satellite System) data shall be logged.",
        ]
        assert defined_in_text(texts) == {"IMU", "GNSS"}

    def test_unknown_without_glossary(self):
        findings, defined = find_undefined_acronyms([("R1", "The FC shall log EKF2 faults.")])
        assert {f.term: f.status for f in findings} == {"FC": "unknown", "EKF2": "unknown"}
        assert defined == set()

    def test_undefined_with_glossary(self):
        findings, defined = find_undefined_acronyms(
            [("R1", "The FC shall log EKF2 faults.")], glossary={"FC"}
        )
        assert [(f.term, f.status) for f in findings] == [("EKF2", "undefined")]
        assert defined == {"FC"}

    @pytest.mark.parametrize(
        "text",
        [
            "The unit SHALL NOT reset.",  # RFC 2119 keywords
            "The rate TBD shall apply.",  # placeholder — own smell
            "The FIFO shall hold 4 KB.",  # unit
            "As defined in section E1.1 of the spec.",  # numbered reference
            "Derived from UAV-SYS-10.",  # requirement-ID shape
        ],
    )
    def test_non_acronyms_are_ignored(self, text):
        findings, _ = find_undefined_acronyms([("R1", text)])
        assert {f.term for f in findings} <= {"FIFO"}

    def test_cross_reference_to_requirement_id_is_ignored(self):
        findings, _ = find_undefined_acronyms([("HLR1", "Refines HLR1."), ("X", "See HLR1.")])
        assert findings == []

    def test_dotted_instruction_name_is_one_term(self):
        findings, _ = find_undefined_acronyms([("R", "It shall support the FENCE.T command.")])
        assert [f.term for f in findings] == ["FENCE.T"]

    def test_glossary_formats(self, tmp_path):
        p = tmp_path / "g.txt"
        p.write_text("# comment\nIMU: Inertial Measurement Unit\nGNSS, sat nav\nEKF2\tfilter\n\n")
        assert load_glossary(p) == {"IMU", "GNSS", "EKF2"}


class TestTermVariants:
    def test_hyphen_variant(self):
        reqs = [("R1", "The I-TLB shall flush."), ("R2", "The ITLB shall hold 16 entries.")]
        [v] = find_term_variants(reqs)
        assert v.spellings == ("I-TLB", "ITLB") and v.requirement_ids == ("R1", "R2")

    def test_cva6_itlb(self):
        assert [v.spellings for v in find_term_variants(cva6())] == [("I-TLB", "ITLB")]


class TestReportAndRegression:
    def test_cva6_counts(self):
        # Pinned so later tuning is visible in review, not silent.
        r = run_set_checks(cva6())
        by_kind = [(d.kind, d.variant_reason) for d in r.duplicates]
        assert by_kind.count(("exact", None)) == 0
        assert by_kind.count(("near", None)) == 1  # PPA-50 ~ PPA-60 (both TBD placeholders)
        assert by_kind.count(("variant", "parameter")) == 7
        assert by_kind.count(("variant", "polarity")) == 1
        assert len(r.acronyms) == 26 and all(a.status == "unknown" for a in r.acronyms)
        assert r.acronyms_defined == {"LRU", "PMP", "TRI"}

    def test_variants_and_unknown_are_not_findings(self):
        reqs = [
            ("R1", "The FC shall arm the motors."),
            ("R2", "The FC shall not arm the motors."),
        ]
        assert not run_set_checks(reqs).has_findings

    def test_layer1_gate_does_not_depend_on_set_checks(self):
        from pathlib import Path

        import specguard.core.pipeline as pipeline

        assert "set_checks" not in Path(pipeline.__file__).read_text(encoding="utf-8")


class TestCli:
    def test_exit_codes_and_json(self, tmp_path, capsys):
        f = tmp_path / "r.txt"
        f.write_text("R1: The FC shall land.\nR2: The FC shall land.\n")
        assert main(["setcheck", str(f), "--json"]) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["duplicates"][0]["kind"] == "exact"
        assert payload["glossary_provided"] is False

        clean = tmp_path / "c.txt"
        clean.write_text("R1: The unit shall land.\nR2: The display shall show voltage in volts.\n")
        assert main(["setcheck", str(clean)]) == 0

    def test_glossary_turns_unknown_into_undefined(self, tmp_path, capsys):
        f = tmp_path / "r.txt"
        f.write_text("R1: The FC shall log EKF2 faults.\n")
        g = tmp_path / "g.txt"
        g.write_text("FC: flight controller\n")
        assert main(["setcheck", str(f), "--glossary", str(g), "--json"]) == 1
        payload = json.loads(capsys.readouterr().out)
        assert [(a["term"], a["status"]) for a in payload["acronyms"]] == [("EKF2", "undefined")]

    def test_bad_inputs_exit_3(self, tmp_path):
        f = tmp_path / "r.txt"
        f.write_text("R1: The FC shall land.\n")
        assert main(["setcheck", str(f), "--glossary", str(tmp_path / "missing.txt")]) == 3
        assert main(["setcheck", str(f), "--near-threshold", "1.5"]) == 3
