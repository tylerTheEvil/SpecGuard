"""Independent fault-injection lexicons for de-circularized validation.

Why this module exists
----------------------
The original seeded-fault experiment (`experiments/seeded_faults.py`) injects
faults using the *detector's own* trigger words (e.g. it inserts "appropriate",
"fast", "user-friendly" — words that literally live in
``smell_detector.AMBIGUITY_TERMS``). Any tool will report ~100% recall against
faults drawn from its own lexicon: the result is true *by construction* and
validates the implementation, not the detection *method*.

This module supplies an INDEPENDENT vocabulary — terms taken from published
requirements-quality literature that are NOT the detector's lexicons — so that
re-running the experiment measures genuine lexicon *coverage* rather than a
tautology. Recall below 100% here is the expected, more credible, and
publishable outcome (it quantifies the coverage gap of a closed lexicon).

Sources (honest attribution)
-----------------------------
Every term group below is annotated with its published source. The four primary
sources are:

* **INCOSE Guide to Writing Requirements (GtWR), v3.1 (2022)** — Appendix C
  "Use of Language" enumerates vague terms, vague adjectives/adverbs, vague
  quantifiers, escape ("loophole") clauses, comparatives and superlatives. This
  is the richest published controlled vocabulary and the backbone of the
  independent ambiguity / vagueness / optionality / comparative lists.
  https://www.incose.org/ (RWG Guide to Writing Requirements)
* **Femmer et al. (2017), "Rapid Quality Assurance with Requirements Smells",
  Journal of Systems and Software** — the foundational smell taxonomy. The
  smelly-word *categories* (subjective language, ambiguous adverbs/adjectives,
  comparatives, superlatives, vague pronouns, loopholes, non-verifiable terms)
  come from here; representative example words are reproduced where the paper /
  its replications (Zakeri-Nasrabadi et al. 2024, Table 3) cite them.
* **Berry, Kamsties & Krieger (2003), "From Contract Drafting to Software
  Specification: Linguistic Sources of Ambiguity" (the *ambiguity handbook*)**
  — source of "dangerous" vague adverbs and indefinite quantifier phrasing.
* **ISO/IEC/IEEE 29148:2018, §5.2.7** — language-criteria examples of imprecise
  and superlative terms.

Disjointness discipline (the core invariant)
--------------------------------------------
Each candidate term is checked programmatically against the detector's actual
lexicons (imported from ``specguard.core.smell_detector``). Terms that the
detector already knows are EXCLUDED from injection and recorded in
``OVERLAP_REPORT`` — they are reported, never silently injected. Only terms the
detector does NOT explicitly know survive into the injection lists exposed by
``independent_terms()``.

Honest limitation — placeholders are a closed vocabulary
--------------------------------------------------------
The PLACEHOLDER smell is detected by a fixed regex over {TBD, TODO, FIXME, XXX,
TBC}. A marker is *either* one of those tokens (in which case it overlaps the
detector and full disjointness is impossible) *or* it is some other phrasing
("to be confirmed", "[placeholder]", ...) which the detector cannot match at
all. There is no independent token that is both a recognisable placeholder *and*
disjoint-yet-detected. We therefore inject *disjoint* placeholder phrasings
(spelled-out markers the detector does NOT know) on purpose: the resulting
misses are the honest evidence that the placeholder lexicon is a closed set.
This is stated, not faked. See ``PLACEHOLDER_CLOSED_VOCAB_NOTE``.

Stdlib-only: this experiment module imports only the detector lexicons and the
standard library, consistent with the core's quarantine rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from specguard.core.smell_detector import (
    AMBIGUITY_TERMS,
    COMPARATIVE_PATTERN,
    OPTIONALITY_TERMS,
    PLACEHOLDER_PATTERN,
    SUBJECTIVITY_TERMS,
    VAGUENESS_TERMS,
    WEAKNESS_TERMS,
)

# ---------------------------------------------------------------------------
# Candidate vocabulary, BEFORE disjointness filtering.
# These are the raw published terms. The disjointness pass below removes any
# that the detector already knows and records them in OVERLAP_REPORT.
# ---------------------------------------------------------------------------

# Ambiguity — single subjective adjectives/adverbs the detector might catch via
# AMBIGUITY_TERMS. Drawn from INCOSE GtWR Appendix C "vague adjectives" list and
# the Femmer/Zakeri subjective-language category. Chosen to AVOID the detector's
# own set (which already has fast/easy/appropriate/efficient/robust/...).
_AMBIGUITY_CANDIDATES = {
    # INCOSE GtWR vague adjectives (Appendix C):
    "ancillary", "relevant", "routine", "generic", "significant",
    "expandable", "typical", "effective", "proficient", "customary",
    "ergonomic", "versatile", "convenient", "comprehensive", "graceful",
    "state-of-the-art",  # Femmer subjective language; multi-word handled by detector SUBJECTIVITY
    # Berry & Kamsties / ISO 29148 imprecise adjectives:
    "satisfactory", "acceptable", "desirable", "feasible",
}

# Vagueness — imprecise quantifiers the detector might catch via VAGUENESS_TERMS
# (which already has some/any/many/several/few/various/etc/approximately/...).
# Independent quantifier phrasings from INCOSE GtWR "vague quantifiers" and the
# Berry & Kamsties dangerous-plural/quantifier discussion.
_VAGUENESS_CANDIDATES = {
    # INCOSE GtWR vague quantifiers not in the detector set:
    "a few", "a lot of", "allowable", "almost always", "very nearly",
    "close to", "about", "as much as possible", "as little as possible",
    "to the extent possible",
    # Berry & Kamsties indefinite quantifiers / dangerous plurals:
    "all", "each", "every", "most", "majority of", "a number of",
    "multiple", "certain",
}

# Optionality — escape/loophole clauses. Detector OPTIONALITY_TERMS covers the
# "if X" / "where X" family (if possible/needed/applicable/...; where
# possible/applicable/required). Independent escape phrasings from INCOSE GtWR
# loophole rule (R29) and Femmer "loopholes" category.
_OPTIONALITY_CANDIDATES = {
    # INCOSE GtWR loophole clauses + Femmer loopholes (distinct phrasings):
    "as far as possible", "to the extent practical", "to the extent feasible",
    "unless otherwise specified", "subject to", "at the discretion of",
    "may be omitted", "optionally", "on a best-effort basis",
    "wherever feasible", "as deemed necessary", "to the maximum extent possible",
}

# Comparative — bare comparatives without baseline. Detector COMPARATIVE_PATTERN
# is a CLOSED regex over a fixed list (faster/slower/better/worse/higher/lower/
# larger/smaller and a few "more/less X"). Independent comparatives from INCOSE
# GtWR comparative rule (R27) and Femmer comparative category — chosen to lie
# OUTSIDE that regex.
_COMPARATIVE_CANDIDATES = {
    "quicker", "stronger", "cheaper", "lighter", "heavier", "wider",
    "narrower", "longer", "shorter", "denser", "tighter", "richer",
    "more accurate", "less complex", "more responsive", "more compact",
    "improved", "enhanced", "superior",
}

# Placeholder — see PLACEHOLDER_CLOSED_VOCAB_NOTE. Detector PLACEHOLDER_PATTERN
# is a closed regex over {TBD, TODO, FIXME, XXX, TBC}. These independent markers
# are deliberately DISJOINT spelled-out placeholders the detector cannot match;
# injecting them surfaces the closed-vocabulary coverage gap honestly.
_PLACEHOLDER_CANDIDATES = {
    "to be confirmed", "to be defined", "to be determined later",
    "to be specified", "to be decided", "value pending",
    "[placeholder]", "to be completed", "details forthcoming",
    "to be supplied",
}

PLACEHOLDER_CLOSED_VOCAB_NOTE = (
    "PLACEHOLDER detection uses a closed regex over {TBD, TODO, FIXME, XXX, "
    "TBC}. Full disjointness while staying detectable is impossible: a marker "
    "is either one of those exact tokens (overlap) or an alternative phrasing "
    "the detector cannot match. The independent list intentionally uses "
    "alternative phrasings, so misses on this type are EXPECTED and document "
    "the closed-lexicon coverage limit rather than a detector bug."
)


@dataclass(frozen=True)
class _DetectorView:
    """How the detector recognises a given fault type, for disjointness checks.

    `terms` is the explicit lexicon set (lower-cased) when detection is
    lexicon-based; `regex_tokens` is the explicit alternation when detection is
    a closed regex. Exactly one is populated per fault type.
    """

    terms: frozenset[str]
    regex_tokens: frozenset[str]


def _regex_alternation_tokens(pattern_source: str) -> frozenset[str]:
    """Extract the literal alternatives from a simple ``\\b(a|b|c)\\b`` regex.

    Used only for the closed COMPARATIVE / PLACEHOLDER patterns whose body is a
    plain alternation of literals. Not a general regex parser.
    """
    body = pattern_source
    start = body.find("(")
    end = body.rfind(")")
    if start == -1 or end == -1:
        return frozenset()
    inner = body[start + 1 : end]
    return frozenset(tok.strip().lower() for tok in inner.split("|") if tok.strip())


# Map each fault type to the detector's recognition surface.
_DETECTOR_VIEWS: dict[str, _DetectorView] = {
    "ambiguity": _DetectorView(
        # Ambiguity injects single adjectives; the detector would catch them via
        # AMBIGUITY_TERMS, and multi-word judgement phrases via SUBJECTIVITY_TERMS.
        terms=frozenset(t.lower() for t in (AMBIGUITY_TERMS | SUBJECTIVITY_TERMS)),
        regex_tokens=frozenset(),
    ),
    "vagueness": _DetectorView(
        terms=frozenset(t.lower() for t in VAGUENESS_TERMS),
        regex_tokens=frozenset(),
    ),
    "optionality": _DetectorView(
        # Escape clauses are caught by OPTIONALITY_TERMS; some softeners by WEAKNESS.
        terms=frozenset(t.lower() for t in (OPTIONALITY_TERMS | WEAKNESS_TERMS)),
        regex_tokens=frozenset(),
    ),
    "comparative": _DetectorView(
        terms=frozenset(),
        regex_tokens=_regex_alternation_tokens(COMPARATIVE_PATTERN.pattern),
    ),
    "placeholder": _DetectorView(
        terms=frozenset(),
        regex_tokens=_regex_alternation_tokens(PLACEHOLDER_PATTERN.pattern),
    ),
}

_RAW_CANDIDATES: dict[str, set[str]] = {
    "ambiguity": _AMBIGUITY_CANDIDATES,
    "vagueness": _VAGUENESS_CANDIDATES,
    "optionality": _OPTIONALITY_CANDIDATES,
    "comparative": _COMPARATIVE_CANDIDATES,
    "placeholder": _PLACEHOLDER_CANDIDATES,
}


def _detector_knows(fault_type: str, term: str) -> bool:
    """True if the detector would recognise `term` for this fault type.

    A term is considered "known" if it equals, or contains as a whole-word
    substring, any detector lexicon term / regex token (so that injecting
    'a number of' is flagged as overlapping if the detector knew 'number',
    and conversely a detector multi-word term contained in the candidate
    counts as overlap).
    """
    view = _DETECTOR_VIEWS[fault_type]
    known = view.terms | view.regex_tokens
    t = term.lower()
    if t in known:
        return True
    t_words = set(t.split())
    for k in known:
        # whole single-word overlap (e.g. candidate 'a lot of' vs detector 'lot of'),
        # or detector phrase fully contained in the candidate phrase.
        if k in t_words:
            return True
        if " " in k and k in t:
            return True
    return False


def _build() -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    """Run the disjointness pass: keep disjoint terms, report overlaps."""
    independent: dict[str, list[str]] = {}
    overlaps: list[dict[str, str]] = []
    for fault_type, candidates in _RAW_CANDIDATES.items():
        kept: list[str] = []
        for term in sorted(candidates):
            if _detector_knows(fault_type, term):
                overlaps.append(
                    {
                        "fault_type": fault_type,
                        "term": term,
                        "reason": "overlaps detector lexicon/regex; excluded from injection",
                    }
                )
            else:
                kept.append(term)
        independent[fault_type] = kept
    return independent, overlaps


# Public, frozen-at-import results.
_INDEPENDENT, OVERLAP_REPORT = _build()


def independent_terms(fault_type: str) -> list[str]:
    """Return the disjoint independent injection terms for a fault type."""
    return list(_INDEPENDENT[fault_type])


def all_independent_terms() -> dict[str, list[str]]:
    """Return the full {fault_type: [disjoint terms]} mapping (copy)."""
    return {k: list(v) for k, v in _INDEPENDENT.items()}


def lexicon_sizes() -> dict[str, int]:
    """Sizes of the disjoint independent lexicon per fault type."""
    return {k: len(v) for k, v in _INDEPENDENT.items()}


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import json

    print("Independent lexicon sizes (after disjointness filtering):")
    print(json.dumps(lexicon_sizes(), indent=2))
    print(f"\nOverlaps excluded: {len(OVERLAP_REPORT)}")
    for o in OVERLAP_REPORT:
        print(f"  - [{o['fault_type']}] {o['term']}")
    print(f"\n{PLACEHOLDER_CLOSED_VOCAB_NOTE}")
