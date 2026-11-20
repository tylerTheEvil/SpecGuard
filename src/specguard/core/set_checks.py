"""Set-level requirement checks — duplicates and undefined acronyms (stdlib-only).

Layer 1 assesses one requirement at a time. Some review criteria are only
meaningful over the *whole set* (ISO/IEC/IEEE 29148:2018 §5.2.6 characteristics
of a set of requirements). This module covers two of them, both listed as
quality-review criteria in TfNSW ASA *T MU AM 06007 GU — Guide to Requirements
Definition and Analysis* (v3.0, 2016), Appendix E, Table 13:

- **Necessary — no duplicated requirements** → ``find_duplicates``
- **Defined terms and acronyms** → ``find_undefined_acronyms``
- **Consistent terms** (narrow: acronym spelling variants only) →
  ``find_term_variants``

Both are *screening* checks. They produce **candidates for human review**, in
the same sense as ``q14_potential_conflicts``: a near-duplicate pair is not
proof that one requirement is redundant, and an acronym missing from a
glossary is not proof that it is undefined in the wider document set.

Design decisions (trade-offs, not novelty claims):

- **Deterministic, stdlib-only.** Token normalisation + Jaccard pre-filter +
  ``difflib.SequenceMatcher`` on token sequences. No embeddings: an embedding
  model would put a trained artefact into the detection path, which the
  DO-330 positioning of the core rules out (see ``docs/architecture.md``).
  Cost: paraphrases with little lexical overlap are not found.
- **Parametric variants are not duplicates.** Requirement families such as
  CVA6 ISA-10 / ISA-20 ("CV64A6 shall support RV64I ..." vs "CV32A6 shall
  support RV32I ...") are textually near-identical but intentionally
  distinct. A pair whose only differing tokens are identifiers or numbers is
  reported as ``variant`` (reason ``parameter``), not as a duplicate.
- **Polarity/modal differences are not duplicates.** "shall" vs "shall not",
  or "shall" vs "may", reverses or weakens meaning. Such pairs are reported
  as ``variant`` (reason ``polarity``) — worth a look as a possible conflict,
  but this module does not claim conflict detection.
- **No glossary → UNKNOWN, not FAIL.** Without a reference glossary an
  acronym can only be confirmed as defined in-text ("Global Navigation
  Satellite System (GNSS)"); everything else is ``unknown``. With a glossary,
  acronyms found neither in it nor in-text are ``undefined``. This mirrors
  the UNKNOWN discipline of ``docs/grounded_checks.md``.

Opt-in: not part of the per-requirement gate and not called by
``assess_requirement``; run via ``run_set_checks`` or ``specguard setcheck``.
Thresholds are provisional and uncalibrated.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*")

# Dropped before comparison: they carry no requirement content.
STOPWORDS = frozenset({"the", "a", "an"})

# Differences in these tokens change meaning (polarity / obligation strength).
POLARITY_TOKENS = frozenset({
    "not", "no", "never", "none", "shall", "must", "will", "should", "may",
    "can", "could", "might", "cannot",
})  # fmt: skip

DEFAULT_NEAR_THRESHOLD = 0.85
JACCARD_PREFILTER = 0.5


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_PATTERN.findall(text) if t.lower() not in STOPWORDS]


_SENTENCE_START = re.compile(r"(?:^|[.!?:;]\s+|\(\s*)$")


def _identifier_tokens(text: str) -> set[str]:
    """Lower-cased tokens written as names: acronyms, or capitalised mid-sentence.

    "the Zcb extension" (CVA6 ISA-140) and "the Zcmp extension" (ISA-150) differ
    only in an extension *name*; capitalisation outside sentence start is the
    stdlib-only signal for that.
    """
    names = {a.lower() for a in _acronym_tokens(text)}
    for m in TOKEN_PATTERN.finditer(text):
        tok = m.group(0)
        if tok[0].isupper() and not _SENTENCE_START.search(text[: m.start()]):
            names.add(tok.lower())
    return names


def _is_parameter_token(token: str, identifiers: set[str]) -> bool:
    """Identifier-like: contains a digit, or is written as a name in the source."""
    return any(c.isdigit() for c in token) or token in identifiers


# ---------------------------------------------------------------------------
# Duplicates (Table 13: "necessary — no duplication")
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateCandidate:
    """A pair of requirements with (near-)identical wording."""

    kind: str
    """``exact`` | ``near`` | ``variant``."""
    a_id: str
    b_id: str
    similarity: float
    """``SequenceMatcher`` ratio over normalised token sequences, in [0, 1]."""
    jaccard: float
    only_in_a: tuple[str, ...]
    only_in_b: tuple[str, ...]
    variant_reason: str | None = None
    """For ``variant``: ``parameter`` (identifiers/numbers differ) or ``polarity``."""


def find_duplicates(
    requirements: list[tuple[str, str]],
    *,
    near_threshold: float = DEFAULT_NEAR_THRESHOLD,
) -> list[DuplicateCandidate]:
    """Return exact / near-duplicate / variant candidate pairs.

    Args:
        requirements: ``(requirement_id, text)`` pairs.
        near_threshold: minimum token-sequence similarity for ``near`` and
            ``variant`` candidates. Exact duplicates are always reported.
    """
    # Indexed by position, not by ID: two different requirements may share an
    # ID (a defect reported by ``find_duplicate_ids``). Keying by ID would
    # overwrite the first text and pair the ID with itself.
    items = list(requirements)
    toks = [_tokens(text) for _, text in items]
    sets = [set(t) for t in toks]
    names_by_req = [_identifier_tokens(text) for _, text in items]

    # All pairs, no rare-token blocking. Blocking on tokens that are not
    # ubiquitous in the set silently drops exactly the pairs this check exists
    # for: near-identical requirements whose shared tokens are common across
    # the set (e.g. "shall" vs "shall not" differ by one rare token only).
    # Pairs are cheap to reject (Jaccard on token sets) before difflib runs;
    # O(n^2) is acceptable for a screening command over one specification.
    found: list[DuplicateCandidate] = []
    for i, j in combinations(range(len(items)), 2):
        a, b = items[i][0], items[j][0]
        if not toks[i] or not toks[j]:
            continue
        union = sets[i] | sets[j]
        jaccard = len(sets[i] & sets[j]) / len(union)
        if toks[i] == toks[j]:
            found.append(DuplicateCandidate("exact", a, b, 1.0, 1.0, (), ()))
            continue
        if jaccard < JACCARD_PREFILTER:
            continue
        ratio = SequenceMatcher(a=toks[i], b=toks[j], autojunk=False).ratio()
        if ratio < near_threshold:
            continue
        only_a = tuple(sorted(sets[i] - sets[j]))
        only_b = tuple(sorted(sets[j] - sets[i]))
        diff = set(only_a) | set(only_b)
        names = names_by_req[i] | names_by_req[j]
        if diff & POLARITY_TOKENS:
            kind, reason = "variant", "polarity"
        elif diff and all(_is_parameter_token(t, names) for t in diff):
            kind, reason = "variant", "parameter"
        else:
            kind, reason = "near", None
        found.append(
            DuplicateCandidate(
                kind, a, b, round(ratio, 3), round(jaccard, 3), only_a, only_b, reason
            )
        )
    return found


def find_duplicate_ids(requirements: list[tuple[str, str]]) -> list[tuple[str, int]]:
    """Requirement IDs used more than once, with their count, in first-seen order.

    A reused ID breaks traceability regardless of whether the texts match, so
    it is a finding of its own, separate from text duplicates.
    """
    counts: dict[str, int] = {}
    for rid, _ in requirements:
        counts[rid] = counts.get(rid, 0) + 1
    return [(rid, n) for rid, n in counts.items() if n > 1]


# ---------------------------------------------------------------------------
# Acronyms (Table 13: "defined terms and acronyms")
# ---------------------------------------------------------------------------

# Upper-case token of length >= 2 with >= 2 capitals or a capital + digit;
# hyphenated / dotted chains ("CV-X-IF", "FENCE.T") are one term.
ACRONYM_PATTERN = re.compile(r"(?<![\w.-])([A-Z][A-Z0-9]*(?:[.\-][A-Z0-9]+)*)(?![\w-])")
# Numbered references are not acronyms: "section E1.1" (CVA6 MEM-10).
_REFERENCE_PREFIX = re.compile(
    r"\b(?:section|clause|table|figure|fig\.|annex|appendix|chapter|paragraph)\s+$",
    re.IGNORECASE,
)
REQUIREMENT_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+$")

# Not acronyms for this purpose: RFC 2119 keywords, placeholder markers (own
# smell in smell_detector), upper-case units, roman numerals.
NON_ACRONYMS = frozenset({
    "SHALL", "MUST", "SHOULD", "MAY", "NOT", "REQUIRED", "RECOMMENDED",
    "OPTIONAL", "AND", "OR", "TBD", "TBC", "TODO", "FIXME", "XXX",
    "KB", "MB", "GB", "TB", "KIB", "MIB", "GIB", "II", "III", "IV", "VI",
    "VII", "VIII", "IX", "XI", "XII",
})  # fmt: skip

# "Global Navigation Satellite System (GNSS)" / "GNSS (Global Navigation ...)"
_DEF_AFTER_EXPANSION = re.compile(
    r"\b[A-Za-z][\w-]*(?:\s+[A-Za-z][\w-]*)+\s*\(([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)\)"
)
_DEF_BEFORE_EXPANSION = re.compile(
    r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)\s*\((?:[A-Za-z][\w-]*\s+){1,}[A-Za-z][\w-]*\)"
)


def _is_acronym(token: str) -> bool:
    if token in NON_ACRONYMS or len(token) < 2:
        return False
    if REQUIREMENT_ID_PATTERN.match(token):
        return False
    letters = sum(c.isupper() for c in token)
    digits = sum(c.isdigit() for c in token)
    return letters >= 2 or (letters >= 1 and digits >= 1)


def _acronym_tokens(text: str) -> list[str]:
    return [
        m.group(1)
        for m in ACRONYM_PATTERN.finditer(text)
        if _is_acronym(m.group(1)) and not _REFERENCE_PREFIX.search(text[: m.start()])
    ]


def defined_in_text(texts: list[str]) -> set[str]:
    """Acronyms introduced with an expansion somewhere in the given texts."""
    found: set[str] = set()
    for text in texts:
        for pattern in (_DEF_AFTER_EXPANSION, _DEF_BEFORE_EXPANSION):
            for m in pattern.finditer(text):
                if _is_acronym(m.group(1)):
                    found.add(m.group(1))
    return found


def load_glossary(path: str | Path) -> set[str]:
    """Read a glossary: one term per line, optionally ``TERM: definition``.

    ``,``, tab and `` - `` also separate term and definition. Blank lines and
    ``#`` comments are ignored. Terms are matched case-sensitively.
    """
    terms: set[str] = set()
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        term = re.split(r"\s*(?::|,|\t|\s-\s)\s*", line, maxsplit=1)[0].strip()
        if term:
            terms.add(term)
    return terms


@dataclass(frozen=True)
class AcronymFinding:
    term: str
    status: str
    """``undefined`` (glossary given, term in neither glossary nor text) or
    ``unknown`` (no glossary, term not defined in-text)."""
    requirement_ids: tuple[str, ...]


def find_undefined_acronyms(
    requirements: list[tuple[str, str]],
    glossary: set[str] | None = None,
) -> tuple[list[AcronymFinding], set[str]]:
    """Return acronym findings and the set of acronyms confirmed as defined."""
    ids = {rid for rid, _ in requirements}
    used: dict[str, list[str]] = defaultdict(list)
    for rid, text in requirements:
        for term in _acronym_tokens(text):
            if term in ids:
                continue  # a cross-reference to another requirement
            if rid not in used[term]:
                used[term].append(rid)
    defined = defined_in_text([t for _, t in requirements])
    if glossary is not None:
        defined |= {t for t in used if t in glossary}
    status = "undefined" if glossary is not None else "unknown"
    findings = [
        AcronymFinding(term, status, tuple(rids))
        for term, rids in sorted(used.items())
        if term not in defined
    ]
    return findings, {t for t in used if t in defined}


# ---------------------------------------------------------------------------
# Spelling variants (Table 13: "consistent terms" — narrow, acronym-only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TermVariant:
    """One acronym written in several spellings across the set."""

    key: str
    spellings: tuple[str, ...]
    requirement_ids: tuple[str, ...]


def find_term_variants(requirements: list[tuple[str, str]]) -> list[TermVariant]:
    """Acronyms that differ only by hyphens / dots, e.g. ``I-TLB`` vs ``ITLB``.

    Covers a narrow slice of "consistent terms": synonyms and expansions
    ("autopilot" vs "flight controller") are out of reach for a lexical check.
    """
    groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for rid, text in requirements:
        for term in _acronym_tokens(text):
            key = re.sub(r"[.\-]", "", term)
            if rid not in groups[key][term]:
                groups[key][term].append(rid)
    out: list[TermVariant] = []
    for key, spellings in sorted(groups.items()):
        if len(spellings) > 1:
            rids = sorted({r for ids in spellings.values() for r in ids})
            out.append(TermVariant(key, tuple(sorted(spellings)), tuple(rids)))
    return out


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------


@dataclass
class SetCheckReport:
    requirement_count: int
    duplicates: list[DuplicateCandidate] = field(default_factory=list)
    duplicate_ids: list[tuple[str, int]] = field(default_factory=list)
    acronyms: list[AcronymFinding] = field(default_factory=list)
    acronyms_defined: set[str] = field(default_factory=set)
    term_variants: list[TermVariant] = field(default_factory=list)
    glossary_provided: bool = False

    @property
    def has_findings(self) -> bool:
        """True for duplicate IDs, exact/near duplicates, undefined acronyms or term variants.

        ``variant`` pairs and ``unknown`` acronyms are informational: they need
        a human look but are not established defects.
        """
        return (
            bool(self.duplicate_ids)
            or any(d.kind in ("exact", "near") for d in self.duplicates)
            or any(a.status == "undefined" for a in self.acronyms)
            or bool(self.term_variants)
        )


def run_set_checks(
    requirements: list[tuple[str, str]],
    *,
    glossary: set[str] | None = None,
    near_threshold: float = DEFAULT_NEAR_THRESHOLD,
) -> SetCheckReport:
    """Run all set-level checks over ``(requirement_id, text)`` pairs."""
    acronyms, defined = find_undefined_acronyms(requirements, glossary)
    return SetCheckReport(
        requirement_count=len(requirements),
        duplicates=find_duplicates(requirements, near_threshold=near_threshold),
        duplicate_ids=find_duplicate_ids(requirements),
        acronyms=acronyms,
        acronyms_defined=defined,
        term_variants=find_term_variants(requirements),
        glossary_provided=glossary is not None,
    )
