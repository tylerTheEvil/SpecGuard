"""LLM-assisted edge extraction.

Given a requirement's text and a known entity inventory (components, standards,
configurations, and other requirement ids), an LLM proposes candidate graph
edges of type ``MENTIONS``, ``DERIVES_FROM`` or ``MITIGATES``. Each proposal
carries a confidence and a verbatim **evidence span** that must occur in the
source text.

Proposal guards (decision rationale)
------------------------------------
Three deterministic guards run on every proposal before it can reach the review
queue. All are cheap, stdlib-only, and exactly the kind of check that keeps the
LLM layer *augmentative* rather than authoritative:

1. **Evidence-span validation** — the ``evidence_span`` must be a substring that
   literally appears in the requirement text. This anchors every proposal to a
   checkable textual quote instead of a free-floating model assertion.
2. **Ontology-membership** — the ``target_entity`` must be a known id from the
   supplied inventory. The system prompt already asks the model to only use
   inventory ids, but instruction-following is not a guarantee, so this is
   enforced in code: sentinel or hallucinated targets (e.g.
   ``"NOT_IN_INVENTORY"``) are rejected regardless of what the model returns.
3. **Evidence-binding (MENTIONS only)** — for a component/standard mention the
   evidence span must actually name the target (the entity id is expected to
   appear in the text), so a target/evidence mismatch such as ``target="MMU"``
   justified by ``"the FPU"`` is rejected. ``DERIVES_FROM`` / ``MITIGATES``
   targets are requirement/hazard ids that legitimately need not appear verbatim
   in the child's evidence, so this guard is scoped to ``MENTIONS``.

These guards reduce the noise a human reviewer must wade through; they do not
make the LLM authoritative. The human remains the sole authority — only
human-accepted proposals are ever written to the graph (see
:mod:`specguard.extraction.review`). The guards enforce *eligibility* for
review; a human still decides *admission*.

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

    These mirror, one-for-one, the relationship *types* the deterministic
    builder emits for semantic links, so a proposal can be scored against a
    typed reference rather than collapsed into a single entity-link set:

    - ``MENTIONS`` (requirement -> **component**) — builder-typed against
      ``KNOWN_COMPONENTS``; dictionary-matched surrogate reference.
    - ``REFERS_TO`` (requirement -> **standard**) — builder-typed against
      ``KNOWN_STANDARDS``. Split out from ``MENTIONS`` (which previously covered
      "component or standard") so component-mentions and standard-references are
      distinct typed edges, matching ``build_graph``.
    - ``DERIVES_FROM`` (requirement -> requirement) — small hand-annotated set
      (3 pairs, illustrative only — see ``HAND_BUILT_DERIVES_FROM`` in
      :mod:`specguard.graph.builder`).
    - ``MITIGATES`` (requirement -> hazard/requirement) — no ground truth yet.
    """

    MENTIONS = "MENTIONS"
    REFERS_TO = "REFERS_TO"
    DERIVES_FROM = "DERIVES_FROM"
    MITIGATES = "MITIGATES"


# Map an inventory *kind* (the grouping key callers pass to the extractor, e.g.
# ``"components"``) to the graph node *label* its members carry (``"Component"``).
# This is what lets the true target type flow through the pipeline instead of
# being guessed from the edge type at export time. Kinds absent from the map
# fall back to a naive de-pluralise-and-capitalise rule (``"hazards"`` ->
# ``"Hazard"``), so a new inventory bucket labels sensibly without a code change.
_INVENTORY_KIND_TO_LABEL: dict[str, str] = {
    "components": "Component",
    "standards": "Standard",
    "requirements": "Requirement",
    "configurations": "Configuration",
    "hazards": "Hazard",
}

# Fallback label by edge type, used ONLY when a proposal was constructed without
# inventory context (e.g. hand-built in a test) so ``target_label`` is unset.
# The authoritative source is the inventory bucket (see ``_target_labels``); this
# is a best-effort default, not the primary typing path.
_EDGE_TYPE_FALLBACK_LABEL: dict[EdgeType, str] = {
    EdgeType.MENTIONS: "Component",
    EdgeType.REFERS_TO: "Standard",
    EdgeType.DERIVES_FROM: "Requirement",
    EdgeType.MITIGATES: "Hazard",
}


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
        target_label: graph node label of the target, derived from the inventory
            bucket the target belongs to (``"Component"``, ``"Standard"``,
            ``"Requirement"``, ``"Hazard"`` ...). Carries the *true* target type
            downstream so the export need not infer it from ``edge_type``.
            ``None`` for proposals built without inventory context.
    """

    edge_type: EdgeType
    source_id: str
    target_entity: str
    confidence: float
    evidence_span: str
    target_label: str | None = None


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
    "- MENTIONS: the requirement names a known component "
    "(target_entity = that component id).\n"
    "- REFERS_TO: the requirement cites an external standard "
    "(target_entity = that standard id).\n"
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
    *,
    system_prompt: str | None = None,
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
        system_prompt: optional override of the default system prompt, for
            prompt-tuning experiments. The evidence guard is applied
            identically regardless of prompt.

    Returns:
        An :class:`ExtractionResult` with validated proposals and a record of
        any proposals rejected by the guard.
    """
    prompt = _build_prompt(requirement_id, text, inventory)
    response = complete_structured(
        provider, prompt, _RESPONSE_SCHEMA, system=system_prompt or _SYSTEM_PROMPT
    )

    raw_edges = response.get("edges", [])
    if not isinstance(raw_edges, list):
        raw_edges = []
    return _validate_proposals(requirement_id, text, raw_edges, inventory)


def _label_for_kind(kind: str) -> str:
    """Graph node label for an inventory kind (e.g. ``"standards"`` -> ``"Standard"``)."""
    if kind in _INVENTORY_KIND_TO_LABEL:
        return _INVENTORY_KIND_TO_LABEL[kind]
    singular = kind[:-1] if kind.endswith("s") else kind
    return singular.capitalize() or "Entity"


def _target_labels(inventory: dict[str, list[str]]) -> dict[str, str]:
    """Map every allowed target id to the node label of its inventory bucket.

    First bucket wins if an id somehow appears under two kinds (not expected).
    The keyset is exactly the set of allowed targets, so callers can use it for
    the membership check and the label lookup at once.
    """
    labels: dict[str, str] = {}
    for kind, ids in inventory.items():
        if not ids:
            continue
        label = _label_for_kind(kind)
        for target_id in ids:
            labels.setdefault(target_id, label)
    return labels


def _validate_proposals(
    requirement_id: str,
    text: str,
    raw_edges: list,
    inventory: dict[str, list[str]],
) -> ExtractionResult:
    """Validate raw proposal dicts into an :class:`ExtractionResult`.

    Applies the three deterministic proposal guards described in the module
    docstring — evidence-span validation, ontology-membership, and (for
    ``MENTIONS``) evidence-binding. Factored out so multi-pass experiments can
    run the guards on a final filtered list; ``inventory`` is the same allowed-
    target inventory passed to :func:`extract_edges_for_requirement`.
    """
    result = ExtractionResult(requirement_id=requirement_id)
    target_labels = _target_labels(inventory)

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

        # Guard 1 — hallucination: evidence must occur verbatim in the source.
        if evidence not in text:
            result.rejected.append(
                {"reason": "fabricated evidence_span", "raw": raw}
            )
            continue

        # Guard 2 — ontology-membership: target must be a known inventory id.
        # Enforced in code (not left to the prompt) so sentinel / hallucinated
        # targets such as "NOT_IN_INVENTORY" cannot be admitted. The bucket the
        # target lives in also fixes its true node label (P0.4).
        if target not in target_labels:
            result.rejected.append(
                {"reason": "target not in inventory", "raw": raw}
            )
            continue

        # Guard 3 — evidence-binding (named-entity edges only): the span must
        # name the target entity, not merely be *some* substring of the
        # requirement. Rejects target/evidence mismatches (e.g. target="MMU"
        # justified by "the FPU"). Scoped to MENTIONS / REFERS_TO, whose targets
        # (components / standards) are expected to appear in the text;
        # DERIVES_FROM / MITIGATES targets are requirement/hazard ids that need
        # not appear verbatim in the evidence.
        if (
            edge_type in (EdgeType.MENTIONS, EdgeType.REFERS_TO)
            and target.lower() not in evidence.lower()
        ):
            result.rejected.append(
                {"reason": "evidence does not name target", "raw": raw}
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
                target_label=target_labels[target],
            )
        )

    return result


def extract_edges(
    provider: ModelProvider,
    requirements: list[tuple[str, str]],
    inventory: dict[str, list[str]],
    *,
    system_prompt: str | None = None,
) -> list[ExtractionResult]:
    """Extract edges over many requirements (one call each).

    Args:
        provider: BYOM provider.
        requirements: list of ``(requirement_id, text)`` pairs.
        inventory: shared allowed-target inventory.
        system_prompt: optional system-prompt override, passed through to
            :func:`extract_edges_for_requirement`.

    Returns:
        One :class:`ExtractionResult` per input requirement, in input order.
    """
    return [
        extract_edges_for_requirement(
            provider, req_id, text, inventory, system_prompt=system_prompt
        )
        for req_id, text in requirements
    ]
