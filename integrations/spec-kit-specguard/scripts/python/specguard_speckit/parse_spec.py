"""Tolerant parser for Spec Kit ``spec.md`` feature specifications.

Targets the structure of Spec Kit's ``templates/spec-template.md`` and the
format drift observed in 187 in-the-wild specs (see experiments/README.md):

- ``- **FR-001**: text`` (template form, >95% of requirement bullets)
- ``- **FR-020 — Title.** text`` (title inside the bold span)
- ``- FR-001: text`` (unbolded) and ``**FR-001**: text`` (no bullet)
- wrapped requirements: continuation lines and indented sub-bullets
- FR IDs inside tables or prose are *references*, never definitions

Fenced code blocks and HTML comments are ignored everywhere, so template
guidance comments and examples cannot produce findings.
"""

from __future__ import annotations

import re

from .model import Heading, Marker, Requirement, Scenario, SpecDocument, UserStory

DEFAULT_PREFIXES = ("FR", "SC", "NFR")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
BULLET_RE = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")
MARKER_RE = re.compile(r"\[NEEDS CLARIFICATION(?:\s*:\s*(?P<q>[^\]]*))?\]", re.IGNORECASE)
# "User Story 1 - Title (Priority: P1)" (template) or "US1 — Title (P1)" (short form,
# 34 headings in 8 of 193 in-the-wild specs)
STORY_RE = re.compile(
    r"^(?:User Story\b\s*(?P<num>\d+)?|US\s?(?P<num2>\d+)\b)\s*(?P<rest>.*)$", re.IGNORECASE
)
PRIORITY_RE = re.compile(r"\(\s*(?:Priority\s*:\s*)?(P\d+)\s*\)", re.IGNORECASE)

# Unfilled placeholders copied verbatim from spec-template.md (pinned spec-kit
# c00dc05). Bracketed prose that merely resembles them is not matched: every
# alternative is the template's exact wording (or its fixed prefix).
TEMPLATE_PLACEHOLDER_RE = re.compile(
    r"\[(?:FEATURE NAME|DATE|###-feature-name|Brief Title|Title|"
    r"Describe this user journey in plain language|"
    r"Explain the value and why it has this priority level|"
    r"Describe how this can be tested independently[^\]]*|"
    r"Add more user stories as needed[^\]]*|"
    r"boundary condition|error scenario|Entity \d+|"
    r"What it represents, key attributes without implementation|"
    r"What it represents, relationships to other entities|"
    r"specific capability, e\.g\.[^\]]*|key interaction, e\.g\.[^\]]*|"
    r"data requirement, e\.g\.[^\]]*|behavior, e\.g\.[^\]]*|"
    r"Measurable metric, e\.g\.[^\]]*|User satisfaction metric, e\.g\.[^\]]*|"
    r"Business metric, e\.g\.[^\]]*|Assumption about [^\]]*|"
    r"Dependency on existing system/service[^\]]*)\]"
)
# G/W/T placeholders only count right after the keyword (they are too generic
# to match anywhere: "[action]" can be legitimate prose).
GWT_PLACEHOLDER_RE = re.compile(
    r"(?:Given|When|Then)\**\s*\[(initial state|action|expected outcome)\]", re.IGNORECASE
)


def requirement_start_res(prefixes: tuple[str, ...]) -> tuple[re.Pattern, ...]:
    """Patterns for a requirement *definition* (never a mere reference).

    1. bullet + bold ID:   ``- **FR-001**: text`` / ``- **FR-020 — Title.** text``
    2. bold ID paragraph:  ``**FR-001**: text``
    3. bullet + plain ID + mandatory colon: ``- FR-001: text``
    4. bullet + bold title wrapping onto the next line:
       ``- **FR-015 — Ordering is proven by commit ancestry, against the`` ↵ ``...**``

    Prose that starts with an ID ("FR-010 makes every run ...") matches none:
    unbolded IDs need both a bullet and a colon.
    """
    alt = "|".join(re.escape(p) for p in sorted(prefixes, key=len, reverse=True))
    ident = rf"(?P<id>(?:{alt})-\d{{1,4}}[a-z]?)\b"
    bullet = r"(?:[-*+]|\d+[.)])\s+"
    bold = r"\*\*" + ident + r"(?P<boldtail>[^*]*)\*\*(?P<sep>\s*[:.—–-])?\s*(?P<text>.*)$"
    return (
        re.compile(r"^(?P<indent>\s*)" + bullet + bold),
        re.compile(r"^(?P<indent>\s*)" + bold),
        re.compile(
            r"^(?P<indent>\s*)" + bullet + ident + r"(?P<boldtail>)(?P<sep>\s*:)\s*(?P<text>.*)$"
        ),
        re.compile(
            r"^(?P<indent>\s*)" + bullet + r"\*\*" + ident
            + r"(?P<boldtail>)(?P<sep>)\s*(?P<text>[^*]*)$"
        ),
    )


def _match_definition(line: str, patterns: tuple[re.Pattern, ...]) -> re.Match | None:
    for i, pattern in enumerate(patterns):
        m = pattern.match(line)
        if not m:
            continue
        if i == 1:
            # bold paragraph form needs an explicit separator, otherwise it is
            # prose referencing the ID ("**FR-012** applies, and so ...")
            tail = (m.group("boldtail") or "").strip()
            if not (m.group("sep") or tail.endswith((":", "."))):
                return None
        return m
    return None


def strip_markup(text: str) -> str:
    """Remove Markdown emphasis, inline code ticks and links; collapse spaces."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _visible_lines(text: str) -> list[tuple[int, str]]:
    """(line_no, line) pairs outside fenced code and HTML comments."""
    out: list[tuple[int, str]] = []
    in_fence = False
    in_comment = False
    for no, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line) and not in_comment:
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        visible = ""
        rest = line
        while rest:
            if in_comment:
                end = rest.find("-->")
                if end < 0:
                    rest = ""
                else:
                    in_comment = False
                    rest = rest[end + 3 :]
            else:
                start = rest.find("<!--")
                if start < 0:
                    visible += rest
                    rest = ""
                else:
                    visible += rest[:start]
                    in_comment = True
                    rest = rest[start + 4 :]
        out.append((no, visible))
    return out


def parse_spec(text: str, path: str | None = None, prefixes: tuple[str, ...] = DEFAULT_PREFIXES):
    """Parse spec.md text into a :class:`SpecDocument`."""
    start_res = requirement_start_res(tuple(p.upper() for p in prefixes))
    doc = SpecDocument(path=path, title=None)
    lines = _visible_lines(text)

    current_heading = ""
    story: UserStory | None = None
    story_level = 0
    req: dict | None = None

    def close_req() -> None:
        nonlocal req
        if req is None:
            return
        raw = " ".join(req["parts"]).strip()
        payloads = [
            (m.group("q") or "").strip()
            for m in MARKER_RE.finditer(raw)
            if (m.group("q") or "").strip()
        ]
        # an unpaired "**" is left when a bold title wrapped across lines
        analysable = strip_markup(MARKER_RE.sub(" ", raw)).replace("**", "")
        analysable = re.sub(r"\s+", " ", analysable).lstrip(" —–-:.")
        doc.requirements.append(
            Requirement(
                req_id=req["id"],
                kind=req["id"].split("-")[0],
                text=analysable,
                raw=raw,
                line=req["line"],
                section=req["section"],
                markers=payloads,
            )
        )
        req = None

    item: dict | None = None

    def close_item() -> None:
        nonlocal item
        if item is None:
            return
        text = strip_markup(" ".join(item["parts"]))
        low = text.lower()
        has = [re.search(rf"\b{kw}\b", low) is not None for kw in ("given", "when", "then")]
        if any(has):
            item["story"].scenarios.append(Scenario(text=text, line=item["line"],
                                                    is_gwt=all(has)))
        item = None

    for no, line in lines:
        # --- markers and template leftovers (anywhere visible) ---------------
        for m in MARKER_RE.finditer(line):
            q = (m.group("q") or "").strip()
            doc.markers.append(Marker(line=no, question=q or None))
        for m in TEMPLATE_PLACEHOLDER_RE.finditer(line):
            doc.template_leftovers.append((m.group(0), no))
        for m in GWT_PLACEHOLDER_RE.finditer(strip_markup(line)):
            doc.template_leftovers.append((f"[{m.group(1)}]", no))

        # --- headings ---------------------------------------------------------
        h = HEADING_RE.match(line)
        if h:
            close_req()
            close_item()
            level, htext = len(h.group(1)), strip_markup(h.group(2))
            doc.headings.append(Heading(level=level, text=htext, line=no))
            if level == 1 and doc.title is None:
                doc.title = re.sub(r"^Feature Specification:\s*", "", htext, flags=re.I)
            if story is not None and level <= story_level:
                story = None
            sm = STORY_RE.match(htext)
            if sm:
                pm = PRIORITY_RE.search(htext)
                title = re.sub(r"🎯\s*MVP|🎯", "", PRIORITY_RE.sub("", sm.group("rest")))
                title = re.sub(r"\s+", " ", title).strip(" -—–:")
                num = sm.group("num") or sm.group("num2")
                story = UserStory(
                    number=int(num) if num else None,
                    title=title,
                    priority=pm.group(1).upper() if pm else None,
                    line=no,
                )
                story_level = level
                doc.stories.append(story)
            current_heading = htext
            continue

        # --- requirement bullets ---------------------------------------------
        m = _match_definition(line, start_res)
        if m:
            close_req()
            close_item()
            prefix, number = m.group("id").split("-", 1)
            rid = f"{prefix.upper()}-{number}"  # keep "FR-013c" suffix case as written
            tail = (m.group("boldtail") or "").strip(" —–-:.")
            body = m.group("text").strip()
            first = f"{tail}. {body}" if tail and body else (tail or body)
            req = {
                "id": rid,
                "line": no,
                "section": current_heading,
                "indent": len(m.group("indent")),
                "parts": [first],
            }
            continue

        if req is not None:
            stripped = line.strip()
            if not stripped or stripped.startswith("|"):
                close_req()
            else:
                b = BULLET_RE.match(line)
                if b and len(b.group(1)) <= req["indent"]:
                    close_req()  # sibling bullet: requirement ended
                else:
                    req["parts"].append(line[b.end():].strip() if b else stripped)
                    continue

        # --- acceptance scenarios inside a story ------------------------------
        # List items wrap: "**Then** ..." often sits on a continuation line.
        if story is not None:
            b = BULLET_RE.match(line)
            if b:
                close_item()
                item = {"story": story, "line": no, "indent": len(b.group(1)),
                        "parts": [line[b.end():]]}
            elif item is not None and line.strip():
                item["parts"].append(line.strip())
            else:
                close_item()

    close_req()
    close_item()
    return doc
