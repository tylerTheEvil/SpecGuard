"""LLM-assisted edge extraction.

Given a requirement's text and a known entity inventory (components, standards,
configurations, and other requirement ids), an LLM proposes candidate graph
edges of type ``MENTIONS``, ``DERIVES_FROM`` or ``MITIGATES``. Each proposal
carries a confidence and a verbatim **evidence span** that must occur in the
source text.

Hallucination guard (decision rationale)
----------------------------------------
The single most important defensive measure here is the *evidence-span
validation*: every proposal must quote a substring that literally appears in
the requirement text. Proposals whose evidence span cannot be located are
rejected before they ever reach the review queue. This converts a soft
"trust the model" interface into one where every surviving proposal is
grounded in a checkable textual anchor — cheap, deterministic, and exactly the
kind of guard that keeps the LLM layer *augmentative* rather than
authoritative. Note the LLM is still never trusted to create edges on its own:
the guard reduces noise the human reviewer must wade through; the human remains
the sole authority (see :mod:`specguard.extraction.review`).

Scope honesty: extraction quality is measured against the hand-built CVA6 graph
in ``experiments/edge_extraction_eval.py`` (precision/recall per edge type).
This subsystem is an adoption-cost reducer, not a correctness oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from specguard.llm.provider import ModelProvider, complete_structured


class EdgeType(StrEnum):
    """Graph edge types the extractor is allowed to propose.

    Restricted to the three relationship types the hand-built graph uses for
    semantic links. ``MENTIONS`` (requirement -> component/standard) is the
    one with hand-built ground truth; ``DERIVES_FROM`` (requirement ->
    requirement) and ``MITIGATES`` (requirement -> hazard/requirement) are the
    higher-value relations the deterministic builder leaves as placeholders.
    """

    MENTIONS = "MENTIONS"
    DERIVES_FROM = "DERIVES_FROM"
    MITIGATES = "MITIGATES"


@dataclass
class EdgeProposal:
    """A single LLM-proposed graph edge, pending human review.

    Attributes:
        edge_type: one of :class:`EdgeType`.
        source_id: requirement id the edge originates from.
        target_entity: id/name of the target entity (component, standard, or
            another requirement id).
        confidence: model-reported confidence in ``[0, 1]``.
        evidence_span: verbatim substring of the source requirement text that
            justifies the edge. Validated to occur in the text.
    """

    edge_type: EdgeType
    source_id: str
    target_entity: str
    confidence: float
    evidence_span: str


@dataclass
class ExtractionResult:
    """Outcome of extracting edges for one requirement.

    ``rejected`` holds proposals discarded by the evidence-span guard, retained
    for transparency (the eval and CLI can report how many hallucinated spans
    were filtered).
    """

    requirement_id: str
    proposals: list[EdgeProposal] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


# JSON schema for the structured response. Note the Anthropic constraints:
# every object carries additionalProperties: false; no minLength/maximum-style
# constraints are used (they are unsupported by the native structured mode).
_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "edge_type": {
                        "type": "string",
                        "enum": [e.value for e in EdgeType],
                    },
                    "target_entity": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence_span": {"type": "string"},
                },
                "required": [
                    "edge_type",
                    "target_entity",
                    "confidence",
                    "evidence_span",
                ],
            },
        },
    },
    "required": ["edges"],
}

_SYSTEM_PROMPT = (
    "You are a requirements-engineering assistant that proposes knowledge-graph "
    "edges from a single requirement. You never invent facts: every edge you "
    "propose must be justified by a verbatim quote ('evidence_span') copied "
    "exactly from the requirement text. Allowed edge types:\n"
    "- MENTIONS: the requirement names a known component or standard "
    "(target_entity = that component/standard id).\n"
    "- DERIVES_FROM: the requirement refines or depends on another requirement "
    "(target_entity = that requirement id).\n"
    "- MITIGATES: the requirement mitigates a hazard or constraint named in the "
    "inventory (target_entity = that hazard/requirement id).\n"
    "Only use target ids that appear in the provided inventory. Assign a "
    "confidence in [0,1]. If no edge is supported, return an empty list."
)


def _build_prompt(requirement_id: str, text: str, inventory: dict[str, list[str]]) -> str:
    """Construct the user prompt for one requirement."""
    lines = [f"Requirement id: {requirement_id}", f"Requirement text:\n{text}", ""]
    lines.append("Known entity inventory (only propose targets from these):")
    for kind, ids in inventory.items():
        if ids:
            lines.append(f"  {kind}: {', '.join(sorted(ids))}")
    lines.append("")
    lines.append(
        "Propose graph edges as JSON. Copy 'evidence_span' verbatim from the "
        "requirement text above."
    )
    return "\n".join(lines)


def extract_edges_for_requirement(
    provider: ModelProvider,
    requirement_id: str,
    text: str,
    inventory: dict[str, list[str]],
) -> ExtractionResult:
    """Extract candidate edges for a single requirement.

    One requirement per provider call (sensible batching: keeps each prompt
    small and the evidence-span check scoped to one text). Applies the
    evidence-span hallucination guard before returning.

    Args:
        provider: any BYOM :class:`~specguard.llm.provider.ModelProvider`.
        requirement_id: id of the source requirement.
        text: the requirement text (the only valid source of evidence spans).
        inventory: allowed targets, grouped by kind (e.g.
            ``{"components": [...], "standards": [...], "requirements": [...]}``).

    Returns:
        An :class:`ExtractionResult` with validated proposals and a record of
        any proposals rejected by the guard.
    """
    prompt = _build_prompt(requirement_id, text, inventory)
    response = complete_structured(provider, prompt, _RESPONSE_SCHEMA, system=_SYSTEM_PROMPT)

    result = ExtractionResult(requirement_id=requirement_id)
    raw_edges = response.get("edges", [])
    if not isinstance(raw_edges, list):
        raw_edges = []

    for raw in raw_edges:
        if not isinstance(raw, dict):
            result.rejected.append({"reason": "non-object edge", "raw": raw})
            continue

        edge_type_value = raw.get("edge_type")
        target = raw.get("target_entity")
        evidence = raw.get("evidence_span", "")
        confidence = raw.get("confidence", 0.0)

        try:
            edge_type = EdgeType(edge_type_value)
        except ValueError:
            result.rejected.append({"reason": "unknown edge_type", "raw": raw})
            continue

        if not isinstance(target, str) or not target:
            result.rejected.append({"reason": "missing target_entity", "raw": raw})
            continue

        if not isinstance(evidence, str) or evidence.strip() == "":
            result.rejected.append({"reason": "empty evidence_span", "raw": raw})
            continue

        # Hallucination guard: evidence must occur verbatim in the source text.
        if evidence not in text:
            result.rejected.append(
                {"reason": "fabricated evidence_span", "raw": raw}
            )
            continue

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        result.proposals.append(
            EdgeProposal(
                edge_type=edge_type,
                source_id=requirement_id,
                target_entity=target,
                confidence=confidence,
                evidence_span=evidence,
            )
        )

    return result


def extract_edges(
    provider: ModelProvider,
    requirements: list[tuple[str, str]],
    inventory: dict[str, list[str]],
) -> list[ExtractionResult]:
    """Extract edges over many requirements (one call each).

    Args:
        provider: BYOM provider.
        requirements: list of ``(requirement_id, text)`` pairs.
        inventory: shared allowed-target inventory.

    Returns:
        One :class:`ExtractionResult` per input requirement, in input order.
    """
    return [
        extract_edges_for_requirement(provider, req_id, text, inventory)
        for req_id, text in requirements
    ]
