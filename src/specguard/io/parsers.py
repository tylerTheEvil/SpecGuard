"""Stdlib-only parsers for engineer-supplied requirement files.

Three lowest-common-denominator formats are supported so an engineer can feed
SpecGuard without tooling:

1. **Plain text** — one requirement per ``ID: text`` line. Blank lines and
   ``#`` comment lines are ignored. A line that does not contain an ``ID:``
   prefix is treated as a *continuation* of the previous requirement and its
   text is appended (so multi-line requirements survive copy-paste).
2. **Markdown table** — a GitHub-flavoured pipe table with at least an ``ID``
   and a ``Text`` column. Header matching is case-insensitive and flexible
   (``id``/``req_id``/``identifier`` and ``text``/``requirement``/
   ``description`` are all accepted).
3. **CSV** — a header row with ``id`` and ``text`` columns (same flexible
   header matching), parsed via the stdlib ``csv`` module so quoting/embedded
   commas are handled correctly.

Design decisions
----------------
* **Reuses the canonical ``Requirement`` dataclass** from
  :mod:`specguard.data.cva6_requirements` rather than introducing a parallel
  type. ``assess_dataset`` / ``build_graph`` read ``.req_id``, ``.text``,
  ``.category``, ``.safety_critical_context``, ``.parent_section``, ``.notes``;
  ``Requirement`` supplies all of these with sensible defaults, so parsed
  requirements flow through the existing pipeline unchanged. ``ParsedRequirement``
  is a thin alias kept for naming clarity at the CLI boundary.
* **Auto-detection is by extension first, then a content sniff** so ``-``
  (stdin) and extension-less paths still work. Sniffing is conservative: an
  unambiguous Markdown table header (a ``|---|`` separator row) wins, otherwise
  a comma-bearing header row is treated as CSV, otherwise plain text.
* **Errors are explicit.** Unparseable input raises :class:`ParseError` with a
  message naming the format and the offending content, never a silent empty
  result — a CLI user must know why nothing was extracted.

The module is intentionally LLM-free and deterministic, consistent with the
DO-330-qualifiable posture of the rest of the deterministic surface.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from specguard.data.cva6_requirements import Requirement

# ``ParsedRequirement`` is the canonical Requirement type — aliased so callers
# at the CLI / parser boundary read intent without coupling to the dataset
# module name. They are the *same* class; isinstance checks hold either way.
ParsedRequirement = Requirement

# Accepted header spellings (lower-cased, stripped) for the two required
# columns. Order does not matter; first match wins per column.
_ID_HEADERS = {"id", "req_id", "reqid", "identifier", "requirement id", "key"}
_TEXT_HEADERS = {
    "text",
    "requirement",
    "requirement text",
    "description",
    "statement",
    "body",
}

# Optional metadata columns we pass through when present.
_CATEGORY_HEADERS = {"category", "type", "section"}
_PARENT_HEADERS = {"parent_section", "parent", "parent section"}

_DEFAULT_CATEGORY = "Uncategorized"

# ``ID:`` prefix at the start of a plain-text line. The id is the leading token
# up to the first colon; it must look like an identifier (letters/digits/dashes/
# dots/underscores) so prose colons ("Note: ...") are treated as continuations.
_PLAINTEXT_ID = re.compile(r"^\s*(?P<id>[A-Za-z][\w.\-]*)\s*:\s*(?P<text>.*)$")


class ParseError(ValueError):
    """Raised when input cannot be parsed into requirements."""


def parse_requirements(
    path_or_text: str | Path,
    fmt: str = "auto",
) -> list[Requirement]:
    """Parse requirements from a file path or a raw text string.

    Args:
        path_or_text: an existing file path (``str`` or ``Path``) OR a raw
            text payload. If the argument is not an existing file, it is
            treated as inline text — this is how the CLI feeds stdin.
        fmt: one of ``"auto"`` (default), ``"text"``, ``"md"``/``"markdown"``,
            ``"csv"``. ``"auto"`` resolves by extension (when a path) then by
            content sniffing.

    Returns:
        A list of :class:`Requirement` objects ready for ``assess_dataset`` /
        ``build_graph``.

    Raises:
        ParseError: on an unknown format, empty/whitespace input, or content
            that matches no requirement in the chosen format.
    """
    text, source_label, ext = _read_source(path_or_text)

    if not text.strip():
        raise ParseError(f"No content to parse ({source_label} is empty or whitespace).")

    resolved = _resolve_format(fmt, ext, text)
    if resolved == "csv":
        reqs = _parse_csv(text)
    elif resolved == "md":
        reqs = _parse_markdown(text)
    elif resolved == "text":
        reqs = _parse_plaintext(text)
    else:  # pragma: no cover - guarded by _resolve_format
        raise ParseError(f"Unknown format: {fmt!r}")

    if not reqs:
        raise ParseError(
            f"Parsed 0 requirements from {source_label} as {resolved!r}. "
            "Check the format: plain text needs 'ID: text' lines, Markdown/CSV "
            "need ID and Text columns."
        )
    return reqs


# ---------------------------------------------------------------------------
# Source reading + format resolution
# ---------------------------------------------------------------------------


def _read_source(path_or_text: str | Path) -> tuple[str, str, str]:
    """Return (text, human_label, extension_lowercase_without_dot).

    Treats the argument as a file path only if it actually exists, so a raw
    requirement string never accidentally hits the filesystem.
    """
    candidate = Path(path_or_text) if isinstance(path_or_text, (str, Path)) else None
    if candidate is not None:
        try:
            is_file = candidate.is_file()
        except OSError:
            is_file = False
        if is_file:
            return (
                candidate.read_text(encoding="utf-8"),
                f"file {candidate}",
                candidate.suffix.lstrip(".").lower(),
            )
    return str(path_or_text), "input", ""


def _resolve_format(fmt: str, ext: str, text: str) -> str:
    """Normalise the requested format, sniffing content when ``auto``."""
    fmt = fmt.lower()
    if fmt in ("markdown", "md"):
        return "md"
    if fmt in ("text", "txt", "plain"):
        return "text"
    if fmt == "csv":
        return "csv"
    if fmt != "auto":
        raise ParseError(
            f"Unknown format {fmt!r}. Use one of: auto, text, md, csv."
        )

    # auto: extension first
    if ext in ("md", "markdown"):
        return "md"
    if ext == "csv":
        return "csv"
    if ext in ("txt", "text"):
        return "text"

    # auto: content sniff
    return _sniff_format(text)


def _sniff_format(text: str) -> str:
    """Best-effort content sniff (no extension available)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "text"

    # Markdown table: a header pipe row followed by a |---|--- separator row.
    has_pipe_header = any("|" in ln for ln in lines[:2])
    has_separator = any(re.match(r"^\|?[\s:|-]+\|[\s:|-]*$", ln) and "-" in ln for ln in lines)
    if has_pipe_header and has_separator:
        return "md"

    # CSV: first non-empty line is a comma-bearing header naming an id column.
    header = lines[0]
    if "," in header and _looks_like_csv_header(header):
        return "csv"

    return "text"


def _looks_like_csv_header(header: str) -> bool:
    cols = {c.strip().strip('"').lower() for c in header.split(",")}
    return bool(cols & _ID_HEADERS) and bool(cols & _TEXT_HEADERS)


# ---------------------------------------------------------------------------
# Per-format parsers
# ---------------------------------------------------------------------------


def _parse_plaintext(text: str) -> list[Requirement]:
    """Parse ``ID: text`` lines with continuation-line support."""
    reqs: list[Requirement] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _PLAINTEXT_ID.match(line)
        if match:
            reqs.append(
                Requirement(
                    req_id=match.group("id").strip(),
                    text=match.group("text").strip(),
                    category=_DEFAULT_CATEGORY,
                )
            )
        elif reqs:
            # Continuation of the previous requirement.
            reqs[-1].text = f"{reqs[-1].text} {stripped}".strip()
        else:
            raise ParseError(
                f"Plain-text input must start with an 'ID: text' line; got: {stripped!r}"
            )
    return reqs


def _parse_markdown(text: str) -> list[Requirement]:
    """Parse a GitHub-flavoured pipe table with ID and Text columns."""
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        # Separator row (|---|---|): skip.
        if re.match(r"^\|[\s:|-]+\|?$", line) and "-" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)

    if len(rows) < 2:
        raise ParseError(
            "Markdown table needs a header row plus at least one data row "
            "(pipe-delimited, with ID and Text columns)."
        )

    header = [h.lower() for h in rows[0]]
    col = _map_columns(header)
    if col["id"] is None or col["text"] is None:
        raise ParseError(
            f"Markdown table header must contain an ID and a Text column; got {rows[0]}."
        )

    reqs: list[Requirement] = []
    for cells in rows[1:]:
        reqs.append(_row_to_requirement(cells, col))
    return [r for r in reqs if r is not None]  # type: ignore[misc]


def _parse_csv(text: str) -> list[Requirement]:
    """Parse a CSV with id and text columns via the stdlib csv module."""
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        raise ParseError("CSV needs a header row plus at least one data row.")

    header = [h.strip().lower() for h in rows[0]]
    col = _map_columns(header)
    if col["id"] is None or col["text"] is None:
        raise ParseError(
            f"CSV header must contain an ID and a Text column; got {rows[0]}."
        )

    reqs: list[Requirement] = []
    for cells in rows[1:]:
        req = _row_to_requirement(cells, col)
        if req is not None:
            reqs.append(req)
    return reqs


# ---------------------------------------------------------------------------
# Tabular helpers (shared by Markdown + CSV)
# ---------------------------------------------------------------------------


def _map_columns(header: list[str]) -> dict[str, int | None]:
    """Map our logical columns to 0-based indices in a (lower-cased) header."""
    mapping: dict[str, int | None] = {
        "id": None,
        "text": None,
        "category": None,
        "parent_section": None,
    }
    for idx, name in enumerate(header):
        key = name.strip().strip('"')
        if mapping["id"] is None and key in _ID_HEADERS:
            mapping["id"] = idx
        elif mapping["text"] is None and key in _TEXT_HEADERS:
            mapping["text"] = idx
        elif mapping["category"] is None and key in _CATEGORY_HEADERS:
            mapping["category"] = idx
        elif mapping["parent_section"] is None and key in _PARENT_HEADERS:
            mapping["parent_section"] = idx
    return mapping


def _row_to_requirement(cells: list[str], col: dict[str, int | None]) -> Requirement | None:
    """Build a Requirement from a row, skipping rows with no id/text."""

    def get(key: str) -> str:
        idx = col[key]
        if idx is None or idx >= len(cells):
            return ""
        return cells[idx].strip()

    req_id = get("id")
    text = get("text")
    if not req_id and not text:
        return None
    if not req_id:
        raise ParseError(f"Row missing an ID value: {cells}")
    if not text:
        raise ParseError(f"Requirement {req_id!r} has empty text.")

    category = get("category") or _DEFAULT_CATEGORY
    return Requirement(
        req_id=req_id,
        text=text,
        category=category,
        parent_section=get("parent_section"),
    )
