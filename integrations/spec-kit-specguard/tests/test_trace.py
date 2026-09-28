"""spec <-> tasks traceability checks TR-001..TR-006."""

from __future__ import annotations

from specguard_speckit.model import verdict_from
from specguard_speckit.parse_spec import parse_spec
from specguard_speckit.parse_tasks import parse_tasks
from specguard_speckit.trace import check_trace


def run(fixture_text, spec: str, tasks: str):
    return check_trace(parse_spec(fixture_text(spec)), parse_tasks(fixture_text(tasks)))


def test_fully_linked_tasks_pass(fixture_text):
    findings, summary = run(fixture_text, "spec_clean.md", "tasks_ok.md")
    assert findings == []
    assert verdict_from(findings, []) == "PASS"
    assert summary == {
        "tasks": 6, "tasks_done": 3, "stories": 2, "stories_with_tasks": 2,
        "functional_requirements": 6, "functional_requirements_referenced": 6,
    }


def test_gaps(fixture_text):
    findings, summary = run(fixture_text, "spec_clean.md", "tasks_gaps.md")
    got = {(f.check_id, f.severity, f.ref) for f in findings}
    assert ("TR-001", "error", "US3") in got           # story tags are feature-local
    assert ("TR-006", "warn", "FR-009") in got         # may be another feature's FR
    assert ("TR-004", "error", "T002") in got          # duplicate task ID
    assert ("TR-002", "warn", "US2") in got            # story without tasks
    # 4/6 FRs cited -> systematic referencing -> per-FR warnings
    assert {("TR-003", "warn", "FR-003"), ("TR-003", "warn", "FR-004")} <= got
    assert verdict_from(findings, []) == "FAIL"
    assert summary["functional_requirements_referenced"] == 4


def test_undefined_requirement_reference_alone_is_warn(fixture_text):
    spec = parse_spec(fixture_text("spec_clean.md"))
    tasks = parse_tasks(fixture_text("tasks_ok.md") +
                        "- [ ] T007 [US1] Mirror the Linear bridge's FR-034 semantics\n")
    findings, _ = check_trace(spec, tasks)
    assert [(f.check_id, f.ref) for f in findings] == [("TR-006", "FR-034")]
    assert verdict_from(findings, []) == "WARN"


def test_sporadic_fr_referencing_is_one_info_finding(fixture_text):
    spec = parse_spec(fixture_text("spec_clean.md"))
    tasks = parse_tasks("- [ ] T001 [US1] Bookmark service (FR-001)\n"
                        "- [ ] T002 [US2] Bookmark list\n")
    findings, _ = check_trace(spec, tasks)
    tr3 = [f for f in findings if f.check_id == "TR-003"]
    assert len(tr3) == 1 and tr3[0].severity == "info"
    assert "1/6" in tr3[0].message and "FR-006" in tr3[0].message
    assert verdict_from(findings, []) == "PASS"


def test_unlinked_tasks_reported_as_not_checkable(fixture_text):
    findings, _ = run(fixture_text, "spec_clean.md", "tasks_no_links.md")
    assert [f.check_id for f in findings] == ["TR-005", "TR-005"]
    assert all(f.severity == "info" for f in findings)
    assert verdict_from(findings, []) == "PASS"


def test_empty_tasks_file(fixture_text):
    findings, _ = check_trace(parse_spec(fixture_text("spec_clean.md")), parse_tasks(""))
    assert [f.check_id for f in findings] == ["TR-005"]
