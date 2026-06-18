"""Disjointness invariant for the independent fault-injection lexicon.

The de-circularized validation in ``experiments/seeded_faults_independent.py``
is only meaningful if its injection terms are genuinely NOT in the detector's
lexicons (otherwise recall would again be true by construction). These tests
pin that invariant so it survives future lexicon edits on either side.

The ``experiments`` directory is not an installed package, so we add it to
``sys.path`` to import the lexicon module.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import independent_lexicon as il  # noqa: E402

from specguard.core.smell_detector import (  # noqa: E402
    AMBIGUITY_TERMS,
    COMPARATIVE_PATTERN,
    OPTIONALITY_TERMS,
    PLACEHOLDER_PATTERN,
    SUBJECTIVITY_TERMS,
    VAGUENESS_TERMS,
    WEAKNESS_TERMS,
)


def _detector_lexicon(fault_type: str) -> set[str]:
    """The detector's recognition vocabulary for a fault type (lower-cased)."""
    if fault_type == "ambiguity":
        return {t.lower() for t in (AMBIGUITY_TERMS | SUBJECTIVITY_TERMS)}
    if fault_type == "vagueness":
        return {t.lower() for t in VAGUENESS_TERMS}
    if fault_type == "optionality":
        return {t.lower() for t in (OPTIONALITY_TERMS | WEAKNESS_TERMS)}
    if fault_type == "comparative":
        return il._regex_alternation_tokens(COMPARATIVE_PATTERN.pattern)
    if fault_type == "placeholder":
        return il._regex_alternation_tokens(PLACEHOLDER_PATTERN.pattern)
    raise AssertionError(fault_type)


FAULT_TYPES = ["ambiguity", "vagueness", "optionality", "comparative", "placeholder"]


@pytest.mark.parametrize("fault_type", FAULT_TYPES)
def test_injected_terms_disjoint_from_detector_lexicon(fault_type: str) -> None:
    """No injected term is an exact member of the detector's lexicon."""
    detector = _detector_lexicon(fault_type)
    for term in il.independent_terms(fault_type):
        assert term.lower() not in detector, (
            f"{fault_type!r} injection term {term!r} is in the detector lexicon; "
            "it must be excluded and reported in OVERLAP_REPORT instead."
        )


@pytest.mark.parametrize("fault_type", FAULT_TYPES)
def test_no_injected_term_word_overlaps_detector(fault_type: str) -> None:
    """No injected term shares a whole word with a detector single-word term.

    Guards against subtle re-introduction of detector vocabulary inside a
    multi-word injection phrase (the same rule the module's own filter applies).
    """
    detector = _detector_lexicon(fault_type)
    single_word_detector = {k for k in detector if " " not in k}
    for term in il.independent_terms(fault_type):
        words = set(term.lower().split())
        clash = words & single_word_detector
        assert not clash, (
            f"{fault_type!r} injection term {term!r} shares word(s) {clash} "
            "with the detector lexicon; should be in OVERLAP_REPORT."
        )


def test_overlap_report_terms_are_actually_known() -> None:
    """Every excluded term really is recognised by the detector (no fake reports)."""
    assert il.OVERLAP_REPORT, "expected at least one genuine overlap to be reported"
    for entry in il.OVERLAP_REPORT:
        assert il._detector_knows(entry["fault_type"], entry["term"]), (
            f"OVERLAP_REPORT lists {entry['term']!r} but the detector does not "
            "actually know it — overlap reporting must be truthful."
        )


def test_every_fault_type_has_injection_terms() -> None:
    """Each fault type retains at least one disjoint injection term."""
    sizes = il.lexicon_sizes()
    for fault_type in FAULT_TYPES:
        assert sizes[fault_type] >= 1, f"{fault_type} has no disjoint injection terms"
