"""Deterministic spec <-> tasks traceability checks.

The deterministic counterpart of the coverage part of ``/speckit.analyze``:
it only uses links that are *written down* — ``[US#]`` task tags and
FR/SC/NFR IDs mentioned in task text. Nothing is inferred from wording; a
requirement no task mentions is reported, not guessed at.

Severity choices follow 159 in-the-wild spec/tasks pairs (experiments/):

- ``[US#]`` tags are feature-local by convention, so an undefined tag is an
  error (TR-001). Requirement IDs are not: tasks legitimately cite another
  feature's or project's FR ("mirrors the Linear bridge's FR-034"), so an
  undefined requirement ID is a warning (TR-006).
- Most projects cite FRs in tasks only sporadically (median ~30% of FRs), so
  per-FR "unreferenced" warnings would be noise. TR-003 warns per FR only when
  referencing is systematic (>= :data:`SYSTEMATIC_FR_COVERAGE` of FRs cited);
  otherwise one info finding lists the unreferenced FRs.
"""

from __future__ import annotations

from collections import defaultdict

from .model import Finding, SpecDocument, TasksDocument

SYSTEMATIC_FR_COVERAGE = 0.5

CHECKS = {
    "TR-001": ("error", "Task tagged with a user story the spec does not define"),
    "TR-002": ("warn", "User story with no tagged task"),
    "TR-003": ("warn", "Functional requirement no task references"),
    "TR-004": ("error", "Duplicate task ID"),
    "TR-005": ("info", "Coverage not checkable from the written links"),
    "TR-006": ("warn", "Task references a requirement ID this spec does not define"),
}


def _finding(check_id: str, message: str, line: int | None = None, ref: str | None = None,
             severity: str | None = None) -> Finding:
    return Finding(check_id=check_id, severity=severity or CHECKS[check_id][0],
                   message=message, line=line, ref=ref)


def check_trace(spec: SpecDocument, tasks: TasksDocument) -> tuple[list[Finding], dict]:
    """Return findings and a coverage summary (counts per artifact kind)."""
    out: list[Finding] = []
    defined = set(spec.ids())
    story_labels = {s.label for s in spec.stories if s.number is not None}

    by_task_id: dict[str, list[int]] = defaultdict(list)
    for t in tasks.tasks:
        by_task_id[t.task_id].append(t.line)
    for tid, lines in sorted(by_task_id.items()):
        if len(lines) > 1:
            where = ", ".join(f"L{n}" for n in lines)
            out.append(_finding("TR-004", f"{tid} appears {len(lines)} times ({where})",
                                lines[1], tid))

    for t in tasks.tasks:
        for ref in t.refs:
            if ref not in defined:
                out.append(_finding("TR-006", f"{t.task_id} references {ref}, not defined in "
                                    "this spec.md (another feature's ID, or stale)", t.line, ref))
        for tag in t.story_tags:
            if tag not in story_labels:
                out.append(_finding("TR-001", f"{t.task_id} is tagged [{tag}], but spec.md has "
                                    "no such user story", t.line, tag))

    tagged = {tag for t in tasks.tasks for tag in t.story_tags}
    if not tasks.tasks:
        out.append(_finding("TR-005", "tasks.md contains no '- [ ] T###' task lines"))
    elif not tagged:
        out.append(_finding("TR-005", "No task carries a [US#] tag; story coverage not checkable"))
    else:
        for s in spec.stories:
            if s.number is not None and s.label not in tagged:
                out.append(_finding("TR-002", f"{s.label} ({s.title}) has no [{s.label}] task",
                                    s.line, s.label))

    referenced = {ref for t in tasks.tasks for ref in t.refs}
    fr_ids = spec.ids("FR")
    covered = [rid for rid in fr_ids if rid in referenced]
    missing = [rid for rid in fr_ids if rid not in referenced]
    if not tasks.tasks:
        pass  # already reported as TR-005 above
    elif not covered:
        out.append(_finding("TR-005", "No task mentions an FR-### ID of this spec; requirement "
                            "coverage not checkable"))
    elif missing:
        share = len(covered) / len(fr_ids)
        if share >= SYSTEMATIC_FR_COVERAGE:
            line_of = {r.req_id: r.line for r in spec.requirements}
            for rid in missing:
                out.append(_finding("TR-003", f"{rid} is not referenced by any task",
                                    line_of.get(rid), rid))
        else:
            out.append(_finding(
                "TR-003",
                f"Tasks cite FRs sporadically ({len(covered)}/{len(fr_ids)}); not referenced: "
                f"{', '.join(missing)}",
                severity="info"))

    done = sum(t.done for t in tasks.tasks)
    summary = {
        "tasks": len(tasks.tasks),
        "tasks_done": done,
        "stories": len(spec.stories),
        "stories_with_tasks": len({s.label for s in spec.stories} & tagged),
        "functional_requirements": len(fr_ids),
        "functional_requirements_referenced": len(covered),
    }
    return sorted(out, key=lambda f: f.sort_key()), summary
