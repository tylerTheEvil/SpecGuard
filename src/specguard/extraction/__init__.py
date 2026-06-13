"""SpecGuard LLM-assisted edge extraction — optional research extension.

This package addresses the *graph-population cost* adoption barrier (improvement
plan, motivating finding #5): the ``MENTIONS`` / ``DERIVES_FROM`` / ``MITIGATES``
edges of the knowledge graph are otherwise hand-built, which does not scale to
industrial requirement sets living in DOORS / Polarion / Jama.

An LLM *proposes* candidate edges from requirement text; a human *confirms*
them before any edge enters the graph. This is architecturally identical to the
Layer 2 augmentative pattern used elsewhere in SpecGuard: the LLM is never
authoritative, and the export path structurally requires human confirmation
(there is deliberately no auto-accept). The subsystem depends only on
:mod:`specguard.llm` and the standard library — it sits outside the
DO-330-qualifiable deterministic core, the same quarantine discipline applied
to :mod:`specguard.linguistic`.

Install the LLM extra before using a live provider:

    pip install -e '.[llm]'
"""

from __future__ import annotations

from specguard.extraction.extractor import (
    EdgeProposal,
    EdgeType,
    ExtractionResult,
    extract_edges,
    extract_edges_for_requirement,
)
from specguard.extraction.review import (
    ReviewItem,
    ReviewQueue,
    ReviewStatus,
    export_accepted_edges,
)

__all__ = [
    "EdgeProposal",
    "EdgeType",
    "ExtractionResult",
    "ReviewItem",
    "ReviewQueue",
    "ReviewStatus",
    "export_accepted_edges",
    "extract_edges",
    "extract_edges_for_requirement",
]
