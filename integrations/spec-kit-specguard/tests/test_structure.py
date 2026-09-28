"""Structural checks SK-001..SK-013 — one positive and one negative case each."""

from __future__ import annotations

from specguard_speckit.assess import assess_all
from specguard_speckit.model import verdict_from
from specguard_speckit.parse_spec import parse_spec
from specguard_speckit.structure import CHECKS, NOT_CHECKED, check_structure


def run(text: str):
    doc = parse_spec(text)
    results = assess_all(doc.requirements)
    findings = check_structure(doc, results)
    return doc, results, findings


def ids(findings):
    return [f.check_id for f in findings]


def test_clean_spec_has_no_findings_and_passes(fixture_text):
    _, results, findings = run(fixture_text("spec_clean.md"))
    assert findings == []
    assert verdict_from(findings, [r.gate for r in results]) == "PASS"


def test_sk001_open_marker_is_error_and_fails(fixture_text):
    _, results, findings = run(fixture_text("spec_open_marker.md"))
    sk1 = [f for f in findings if f.check_id == "SK-001"]
    assert len(sk1) == 1 and sk1[0].severity == "error" and sk1[0].line == 26
    assert verdict_from(findings, [r.gate for r in results]) == "FAIL"


def test_sk002_template_leftovers(fixture_text):
    _, _, findings = run(fixture_text("spec_template_leftovers.md"))
    assert ids(findings).count("SK-002") == 8
    assert "SK-001" not in ids(findings)  # the marker lives in an HTML comment


def test_sk003_missing_mandatory_sections(fixture_text):
    _, _, findings = run(fixture_text("spec_missing_sections.md"))
    missing = sorted(f.message for f in findings if f.check_id == "SK-003")
    assert missing == [
        "Mandatory section missing: Success Criteria",
        "Mandatory section missing: User Scenarios & Testing",
    ]


def test_structural_fixture_findings(fixture_text):
    _, _, findings = run(fixture_text("spec_structural.md"))
    got = {(f.check_id, f.ref) for f in findings}
    assert ("SK-004", "FR-002") in got
    assert ("SK-006", "US1") in got
    assert ("SK-007", "US2") in got
    assert ("SK-008", "FR-005") in got
    assert ("SK-009", "SC-001") in got
    assert ("SK-010", "SC-002") in got
    assert {"SK-011", "SK-012", "SK-013"} <= set(ids(findings))
    gap = next(f for f in findings if f.check_id == "SK-012")
    assert gap.message == "Missing IDs in sequence: FR-003, FR-004"


def test_sk005_no_functional_requirements():
    _, _, findings = run("# Feature Specification: X\n\n## Success Criteria\n\n"
                         "- **SC-001**: 90% of users finish in under 1 minute.\n")
    assert "SK-005" in ids(findings)


def test_sk008_lowercase_modal_accepted():
    _, _, findings = run("- **FR-001**: The bundle must preserve file paths.\n")
    assert "SK-008" not in ids(findings)


def test_findings_sorted_by_severity_then_line(fixture_text):
    _, _, findings = run(fixture_text("spec_structural.md"))
    order = {"error": 0, "warn": 1, "info": 2}
    assert [order[f.severity] for f in findings] == sorted(order[f.severity] for f in findings)


def test_every_check_has_catalog_entry_and_valid_severity():
    for check_id, (severity, title) in CHECKS.items():
        assert check_id.startswith("SK-") and severity in ("error", "warn", "info") and title
    assert NOT_CHECKED  # the report must always say what is not checked
