"""Linguistic metrics for requirements text.

Implements four categories of metrics complementing the smell-based pipeline:

Readability (classical formulas):
- Flesch Reading Ease (Flesch 1948): 0-100, higher = easier
- Flesch-Kincaid Grade Level (Kincaid et al. 1975): US school grade

Syntactic complexity (dependency parsing via spaCy):
- Mean Dependency Length: Barbosa et al. (2024) INCOSE; correlates with
  understandability and is sensitive to template patterns common in
  requirements specifications.
- Max Dependency Length: longest arc in the sentence graph.

Structural (standard descriptive stats):
- Token count, sentence count, mean sentence length
- Lexical density: content words / total tokens

These metrics appear alongside (not inside) the smell-based assessment.
They are NOT part of the DO-330-qualifiable deterministic core. See
docs/architecture.md for the architectural rationale.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}


@dataclass(frozen=True)
class LinguisticMetrics:
    """Linguistic quality metrics for a single requirement."""

    requirement_id: str

    # Readability
    flesch_reading_ease: float
    flesch_kincaid_grade: float

    # Syntactic complexity
    mean_dependency_length: float
    max_dependency_length: int

    # Structural
    token_count: int
    sentence_count: int
    mean_sentence_length: float
    lexical_density: float


def _zero_metrics(req_id: str) -> LinguisticMetrics:
    return LinguisticMetrics(
        requirement_id=req_id,
        flesch_reading_ease=0.0,
        flesch_kincaid_grade=0.0,
        mean_dependency_length=0.0,
        max_dependency_length=0,
        token_count=0,
        sentence_count=0,
        mean_sentence_length=0.0,
        lexical_density=0.0,
    )


def _readability(text: str) -> tuple[float, float]:
    """Return (flesch_reading_ease, flesch_kincaid_grade)."""
    try:
        import textstat  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "textstat is required for readability metrics.\n"
            "Install with: pip install -e '.[linguistic]'"
        ) from exc

    # textstat emits a warning on very short texts; suppress it
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fre = float(textstat.flesch_reading_ease(text))
        fkg = float(textstat.flesch_kincaid_grade(text))

    return fre, fkg


def _syntactic(doc) -> tuple[float, int, int, int, float, float]:
    """Return (mdl, max_dl, token_count, sentence_count, mean_sent_len, lex_density)."""
    tokens = [t for t in doc if not t.is_space]
    n = len(tokens)
    if n == 0:
        return 0.0, 0, 0, 0, 0.0, 0.0

    # Dependency lengths — exclude root (head == self)
    arc_lengths = [abs(t.i - t.head.i) for t in tokens if t.head != t]
    mdl = sum(arc_lengths) / len(arc_lengths) if arc_lengths else 0.0
    max_dl = max(arc_lengths) if arc_lengths else 0

    # Sentence structure
    sents = list(doc.sents)
    sent_count = len(sents)
    mean_sent_len = n / sent_count if sent_count else float(n)

    # Lexical density
    content = sum(1 for t in tokens if t.pos_ in _CONTENT_POS)
    lex_density = content / n

    return mdl, max_dl, n, sent_count, mean_sent_len, lex_density


def compute_linguistic_metrics(
    requirement_id: str,
    text: str,
    nlp=None,
) -> LinguisticMetrics:
    """Compute all linguistic metrics for a single requirement.

    Args:
        requirement_id: Requirement identifier (e.g. "L1W-10").
        text: Natural language requirement text.
        nlp: Optional preloaded spacy.Language object. When processing
            a batch, pass a single preloaded object to avoid repeated
            model loading.

    Returns:
        LinguisticMetrics dataclass. All fields are 0 / 0.0 for empty text.

    Raises:
        ImportError: If spaCy, the en_core_web_sm model, or textstat is
            not installed. The message includes the exact install commands.
    """
    if not text or not text.strip():
        logger.warning("Empty text for requirement %s; returning zero metrics.", requirement_id)
        return _zero_metrics(requirement_id)

    if nlp is None:
        from ._spacy_loader import load_nlp  # noqa: PLC0415
        nlp = load_nlp()

    doc = nlp(text)

    fre, fkg = _readability(text)
    mdl, max_dl, tok_count, sent_count, mean_sl, lex_density = _syntactic(doc)

    return LinguisticMetrics(
        requirement_id=requirement_id,
        flesch_reading_ease=round(fre, 3),
        flesch_kincaid_grade=round(fkg, 3),
        mean_dependency_length=round(mdl, 3),
        max_dependency_length=max_dl,
        token_count=tok_count,
        sentence_count=sent_count,
        mean_sentence_length=round(mean_sl, 3),
        lexical_density=round(lex_density, 3),
    )
