"""Extended pipeline with optional linguistic metrics layer.

Wraps the deterministic core pipeline (assess_requirement) and attaches
LinguisticMetrics when the 'linguistic' extra is installed. The base
assessment is always produced; linguistic metrics degrade gracefully to
None when the extra is absent.

This module is intentionally separate from pipeline.py so that the
DO-330-qualifiable core remains untouched and stdlib-only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .pipeline import AssessmentResult, assess_requirement

logger = logging.getLogger(__name__)

_LINGUISTIC_UNAVAILABLE_MSG = (
    "specguard[linguistic] not installed; linguistic metrics will be None. "
    "Install with: pip install -e '.[linguistic]' && "
    "python -m spacy download en_core_web_sm"
)


@dataclass
class ExtendedAssessmentResult:
    """Assessment result enriched with optional linguistic metrics."""

    base: AssessmentResult
    linguistic: object | None  # LinguisticMetrics | None (typed loosely to avoid hard import)

    # Convenience pass-throughs
    @property
    def requirement_id(self) -> str:
        return self.base.requirement_id

    @property
    def gate_decision(self) -> str:
        return self.base.gate_decision


def assess_requirement_extended(
    req_id: str,
    text: str,
    metadata: dict | None = None,
    nlp=None,
) -> ExtendedAssessmentResult:
    """Run the full pipeline and attach linguistic metrics if available.

    Args:
        req_id: Requirement identifier.
        text: Natural language requirement text.
        metadata: Optional metadata forwarded to the core pipeline.
        nlp: Optional preloaded spacy.Language object. Pass once per batch
            to avoid repeated model loading.

    Returns:
        ExtendedAssessmentResult with .base always populated and
        .linguistic populated when the extra is installed, None otherwise.
    """
    base = assess_requirement(req_id, text, metadata=metadata)

    linguistic = None
    try:
        from specguard.linguistic import compute_linguistic_metrics  # noqa: PLC0415
        linguistic = compute_linguistic_metrics(req_id, text, nlp=nlp)
    except ImportError:
        logger.info(_LINGUISTIC_UNAVAILABLE_MSG)

    return ExtendedAssessmentResult(base=base, linguistic=linguistic)


def assess_dataset_extended(
    requirements: list,
    nlp=None,
) -> list[ExtendedAssessmentResult]:
    """Run the extended pipeline on a list of Requirement objects.

    Preloads the spaCy model once before the loop when the extra is
    installed, avoiding per-requirement model loading overhead.

    Args:
        requirements: List of Requirement objects (from cva6_requirements).
        nlp: Optional preloaded spacy.Language. If None and the linguistic
            extra is installed, the model is loaded once and reused.

    Returns:
        List of ExtendedAssessmentResult, one per requirement.
    """
    if nlp is None:
        try:
            from specguard.linguistic._spacy_loader import load_nlp  # noqa: PLC0415
            nlp = load_nlp()
        except ImportError:
            pass  # will degrade to linguistic=None per-requirement

    results = []
    for req in requirements:
        metadata = {
            "category": req.category,
            "safety_critical_context": req.safety_critical_context,
            "parent_section": req.parent_section,
        }
        result = assess_requirement_extended(req.req_id, req.text, metadata=metadata, nlp=nlp)
        results.append(result)
    return results
