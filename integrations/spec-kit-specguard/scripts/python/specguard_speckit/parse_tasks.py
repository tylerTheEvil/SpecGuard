"""Parser for Spec Kit ``tasks.md``.

Task line format (``templates/tasks-template.md``)::

    - [ ] T012 [P] [US1] Create User model in src/models/user.py (FR-003)

Checkbox state, ``T###`` ID, the ``[P]`` parallel marker, leading ``[US#]``
story tags, the enclosing ``## Phase`` heading, and every FR/SC/NFR ID
mentioned in the text (70% of in-the-wild tasks.md files reference FR IDs
explicitly) are extracted. Fenced code and HTML comments are ignored.
"""

from __future__ import annotations

import re

from .model import Task, TasksDocument
from .parse_spec import DEFAULT_PREFIXES, HEADING_RE, _visible_lines, strip_markup

# The ID must end at whitespace: "T004-002" is one hierarchical ID, and a
# "T052/T053 note: ..." checkbox is a note about tasks, not a task definition.
TASK_RE = re.compile(
    r"^\s*[-*]\s+\[(?P<done>[ xX])\]\s+(?P<id>T\d{3,4}(?:-\d+)*)(?=\s|$)(?P<rest>.*)$"
)
LEADING_TAG_RE = re.compile(r"^\s*\[(?P<tag>[^\]]+)\]")


def parse_tasks(
    text: str, path: str | None = None, prefixes: tuple[str, ...] = DEFAULT_PREFIXES
) -> TasksDocument:
    alt = "|".join(re.escape(p.upper()) for p in sorted(prefixes, key=len, reverse=True))
    ref_re = re.compile(rf"\b(?:{alt})-\d{{1,4}}[a-z]?\b")
    doc = TasksDocument(path=path)
    phase = ""
    for no, line in _visible_lines(text):
        h = HEADING_RE.match(line)
        if h:
            phase = strip_markup(h.group(2))
            continue
        m = TASK_RE.match(line)
        if not m:
            continue
        rest = m.group("rest")
        parallel = False
        tags: list[str] = []
        while True:
            t = LEADING_TAG_RE.match(rest)
            if not t:
                break
            tag = t.group("tag").strip()
            if tag.upper() == "P":
                parallel = True
            else:
                tags.extend(s.strip().upper() for s in re.split(r"[,\s]+", tag) if s.strip())
            rest = rest[t.end() :]
        body = strip_markup(rest)
        refs = sorted(set(ref_re.findall(line)), key=lambda r: (r.split("-")[0], _num(r)))
        doc.tasks.append(
            Task(
                task_id=m.group("id"),
                done=m.group("done") in "xX",
                text=body,
                line=no,
                phase=phase,
                parallel=parallel,
                story_tags=[t for t in tags if re.fullmatch(r"US\d+", t)],
                refs=refs,
            )
        )
    return doc


def _num(req_id: str) -> int:
    digits = re.sub(r"\D", "", req_id)
    return int(digits) if digits else 0
