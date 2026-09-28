"""tasks.md parser."""

from __future__ import annotations

from specguard_speckit.parse_tasks import parse_tasks


def test_tasks_fields(fixture_text):
    doc = parse_tasks(fixture_text("tasks_ok.md"))
    assert [t.task_id for t in doc.tasks] == ["T001", "T002", "T003", "T004", "T005", "T006"]
    t2 = doc.tasks[1]
    assert t2.done and t2.parallel
    assert t2.story_tags == ["US1"]
    assert t2.refs == ["FR-001", "FR-002"]
    assert t2.phase.startswith("Phase 2: User Story 1")
    assert t2.text.startswith("Contract test for bookmark endpoint")


def test_unchecked_and_untagged(fixture_text):
    doc = parse_tasks(fixture_text("tasks_ok.md"))
    t1, t4 = doc.tasks[0], doc.tasks[3]
    assert t1.story_tags == [] and not t1.parallel
    assert not t4.done


def test_fenced_examples_ignored(fixture_text):
    ids = [t.task_id for t in parse_tasks(fixture_text("tasks_ok.md")).tasks]
    assert "T999" not in ids


def test_nested_fenced_tasks_do_not_create_trace_links():
    doc = parse_tasks(
        "````markdown\n```\n- [ ] T999 Example FR-999\n```\n````\n"
        "- [ ] T001 Implement FR-001\n"
    )
    assert [(t.task_id, t.refs, t.line) for t in doc.tasks] == [("T001", ["FR-001"], 6)]


def test_uppercase_x_and_refs_sorted_numerically():
    doc = parse_tasks("- [X] T010 [US2] Covers FR-010, FR-002 and SC-001\n")
    t = doc.tasks[0]
    assert t.done
    assert t.refs == ["FR-002", "FR-010", "SC-001"]


def test_hierarchical_ids_and_notes():
    doc = parse_tasks("- [x] T004-001 Scaffold\n- [x] T004-002 Wire CI\n"
                      "- [X] T052/T053 note: both passed on first run\n")
    assert [t.task_id for t in doc.tasks] == ["T004-001", "T004-002"]


def test_combined_story_tag():
    doc = parse_tasks("- [ ] T001 [P] [US1, US2] Shared fixture\n")
    assert doc.tasks[0].story_tags == ["US1", "US2"]
