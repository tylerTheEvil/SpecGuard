"""Tests for the LLM-assisted edge-extraction subsystem (Phase 3b).

Exercises the extractor with a MockProvider: proposal parsing, the
evidence-span hallucination guard, and the review-queue accept/reject
round-trip including export-only-accepted. Runs WITHOUT the anthropic package.
"""

from __future__ import annotations

import json

from specguard.extraction.extractor import (
    EdgeType,
    extract_edges,
    extract_edges_for_requirement,
)
from specguard.extraction.review import (
    ReviewQueue,
    ReviewStatus,
    export_accepted_edges,
)
from specguard.llm.mock_provider import MockProvider

INVENTORY = {
    "components": ["CVA6", "FPU", "MMU"],
    "standards": ["RV64I"],
    "requirements": ["GEN-10", "ISA-10"],
}

REQ_TEXT = "CVA6 shall support the FPU when configured for RV64I operation."


def _provider(edges: list[dict]) -> MockProvider:
    return MockProvider(default=json.dumps({"edges": edges}))


# ---------------------------------------------------------------------------
# Proposal parsing
# ---------------------------------------------------------------------------


def test_valid_proposals_parsed():
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "CVA6",
                "confidence": 0.95,
                "evidence_span": "CVA6 shall support",
            },
            {
                "edge_type": "MENTIONS",
                "target_entity": "FPU",
                "confidence": 0.8,
                "evidence_span": "the FPU",
            },
        ]
    )
    result = extract_edges_for_requirement(provider, "ISA-50", REQ_TEXT, INVENTORY)
    assert len(result.proposals) == 2
    assert result.rejected == []
    assert {p.target_entity for p in result.proposals} == {"CVA6", "FPU"}
    assert all(p.source_id == "ISA-50" for p in result.proposals)
    assert all(p.edge_type is EdgeType.MENTIONS for p in result.proposals)


def test_confidence_clamped():
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "CVA6",
                "confidence": 1.7,
                "evidence_span": "CVA6",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert result.proposals[0].confidence == 1.0


# ---------------------------------------------------------------------------
# Hallucination guard
# ---------------------------------------------------------------------------


def test_fabricated_evidence_span_rejected():
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "MMU",
                "confidence": 0.9,
                "evidence_span": "the MMU translates virtual addresses",  # not in text
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert result.proposals == []
    assert len(result.rejected) == 1
    assert result.rejected[0]["reason"] == "fabricated evidence_span"


def test_mixed_valid_and_fabricated():
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "CVA6",
                "confidence": 0.9,
                "evidence_span": "CVA6 shall support",  # valid
            },
            {
                "edge_type": "MENTIONS",
                "target_entity": "MMU",
                "confidence": 0.9,
                "evidence_span": "MMU enabled",  # fabricated
            },
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert len(result.proposals) == 1
    assert result.proposals[0].target_entity == "CVA6"
    assert len(result.rejected) == 1


def test_unknown_edge_type_and_empty_evidence_rejected():
    provider = _provider(
        [
            {
                "edge_type": "INVENTED",
                "target_entity": "CVA6",
                "confidence": 0.9,
                "evidence_span": "CVA6",
            },
            {
                "edge_type": "MENTIONS",
                "target_entity": "FPU",
                "confidence": 0.9,
                "evidence_span": "",
            },
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert result.proposals == []
    reasons = {r["reason"] for r in result.rejected}
    assert reasons == {"unknown edge_type", "empty evidence_span"}


# ---------------------------------------------------------------------------
# Ontology-membership guard (P0.2)
# ---------------------------------------------------------------------------


def test_target_not_in_inventory_rejected():
    """A target absent from the inventory is refused, even with valid evidence.

    Covers the sentinel case: the model returns ``target="NOT_IN_INVENTORY"``
    but quotes a real in-text span (``"CVA6"``). Membership is enforced in code,
    so the proposal is rejected regardless of the (otherwise valid) evidence.
    """
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "NOT_IN_INVENTORY",
                "confidence": 0.9,
                "evidence_span": "CVA6",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert result.proposals == []
    assert len(result.rejected) == 1
    assert result.rejected[0]["reason"] == "target not in inventory"


def test_mention_to_standard_in_inventory_accepted():
    """A MENTIONS to an inventory standard whose id appears in evidence is kept."""
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "RV64I",
                "confidence": 0.9,
                "evidence_span": "RV64I operation",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert [p.target_entity for p in result.proposals] == ["RV64I"]
    assert result.rejected == []


# ---------------------------------------------------------------------------
# Evidence-binding guard, MENTIONS-scoped (P0.2)
# ---------------------------------------------------------------------------


def test_mentions_evidence_must_name_target():
    """``target="MMU"`` justified by ``"the FPU"`` is a mismatch and is rejected.

    Both entities are in the inventory and the span occurs verbatim in the text,
    so only the target/evidence-binding guard can catch this.
    """
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "MMU",
                "confidence": 0.9,
                "evidence_span": "the FPU",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert result.proposals == []
    assert len(result.rejected) == 1
    assert result.rejected[0]["reason"] == "evidence does not name target"


def test_derives_from_target_need_not_appear_in_evidence():
    """The binding guard is MENTIONS-scoped: DERIVES_FROM ids need not appear.

    A parent-requirement id (``GEN-10``) legitimately does not occur in the
    child's evidence span, so a DERIVES_FROM edge with a valid in-text span
    survives.
    """
    provider = _provider(
        [
            {
                "edge_type": "DERIVES_FROM",
                "target_entity": "GEN-10",
                "confidence": 0.7,
                "evidence_span": "shall support",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "ISA-50", REQ_TEXT, INVENTORY)
    assert [p.target_entity for p in result.proposals] == ["GEN-10"]
    assert [p.edge_type for p in result.proposals] == [EdgeType.DERIVES_FROM]
    assert result.rejected == []


# ---------------------------------------------------------------------------
# Typed edges (REFERS_TO) and true target labels (P0.1 / P0.4)
# ---------------------------------------------------------------------------


def test_refers_to_standard_parsed_with_standard_label():
    """A REFERS_TO to an inventory standard is parsed and labelled Standard."""
    provider = _provider(
        [
            {
                "edge_type": "REFERS_TO",
                "target_entity": "RV64I",
                "confidence": 0.9,
                "evidence_span": "RV64I operation",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert len(result.proposals) == 1
    p = result.proposals[0]
    assert p.edge_type is EdgeType.REFERS_TO
    assert p.target_entity == "RV64I"
    assert p.target_label == "Standard"


def test_mentions_component_carries_component_label():
    """A MENTIONS to a component carries the Component label from the inventory."""
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "CVA6",
                "confidence": 0.9,
                "evidence_span": "CVA6 shall support",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert result.proposals[0].target_label == "Component"


def test_refers_to_binding_guard_applies():
    """REFERS_TO is a named-entity edge, so evidence must name the standard."""
    provider = _provider(
        [
            {
                "edge_type": "REFERS_TO",
                "target_entity": "RV64I",
                "confidence": 0.9,
                "evidence_span": "CVA6 shall support",  # does not name RV64I
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "R1", REQ_TEXT, INVENTORY)
    assert result.proposals == []
    assert result.rejected[0]["reason"] == "evidence does not name target"


def test_extract_edges_batch_order():
    provider = MockProvider(default=json.dumps({"edges": []}))
    pairs = [("A", "text a"), ("B", "text b")]
    results = extract_edges(provider, pairs, INVENTORY)
    assert [r.requirement_id for r in results] == ["A", "B"]


# ---------------------------------------------------------------------------
# Review queue round-trip and export-only-accepted
# ---------------------------------------------------------------------------


def _two_proposal_queue() -> ReviewQueue:
    provider = _provider(
        [
            {
                "edge_type": "MENTIONS",
                "target_entity": "CVA6",
                "confidence": 0.95,
                "evidence_span": "CVA6 shall support",
            },
            {
                "edge_type": "MENTIONS",
                "target_entity": "FPU",
                "confidence": 0.8,
                "evidence_span": "the FPU",
            },
        ]
    )
    result = extract_edges_for_requirement(provider, "ISA-50", REQ_TEXT, INVENTORY)
    return ReviewQueue.from_results([result])


def test_review_accept_reject_roundtrip(tmp_path):
    queue = _two_proposal_queue()
    assert len(queue.pending()) == 2

    assert queue.accept(0) is True
    assert queue.reject(1) is True
    assert queue.accept(99) is False  # nonexistent id

    assert queue.get(0).status is ReviewStatus.ACCEPTED
    assert queue.get(1).status is ReviewStatus.REJECTED
    assert len(queue.pending()) == 0

    # Persistence round-trip preserves status.
    path = tmp_path / "queue.json"
    queue.save(path)
    reloaded = ReviewQueue.load(path)
    assert reloaded.get(0).status is ReviewStatus.ACCEPTED
    assert reloaded.get(1).status is ReviewStatus.REJECTED


def test_export_only_accepted():
    queue = _two_proposal_queue()
    queue.accept(0)
    # item 1 left PENDING (not rejected) — must still be excluded.

    edges = export_accepted_edges(queue)
    assert len(edges) == 1
    edge = edges[0]
    assert edge["from_id"] == "ISA-50"
    assert edge["to_id"] == "CVA6"
    assert edge["rel_type"] == "MENTIONS"
    assert edge["from_label"] == "Requirement"
    assert edge["to_label"] == "Component"
    assert edge["properties"]["source"] == "llm_extraction"
    assert edge["properties"]["human_confirmed"] is True
    assert edge["properties"]["review_status"] == "ACCEPTED"


def test_export_empty_when_none_accepted():
    queue = _two_proposal_queue()
    assert export_accepted_edges(queue) == []


def _standard_ref_queue() -> ReviewQueue:
    provider = _provider(
        [
            {
                "edge_type": "REFERS_TO",
                "target_entity": "RV64I",
                "confidence": 0.9,
                "evidence_span": "RV64I operation",
            }
        ]
    )
    result = extract_edges_for_requirement(provider, "ISA-50", REQ_TEXT, INVENTORY)
    return ReviewQueue.from_results([result])


def test_export_uses_true_label_for_standard():
    """P0.4: a standard target exports as Standard, not collapsed to Component."""
    queue = _standard_ref_queue()
    queue.accept(0)
    edges = export_accepted_edges(queue)
    assert len(edges) == 1
    assert edges[0]["to_label"] == "Standard"
    assert edges[0]["rel_type"] == "REFERS_TO"
    assert edges[0]["to_id"] == "RV64I"


def test_export_label_survives_queue_persistence(tmp_path):
    """The true target label round-trips through the queue JSON."""
    queue = _standard_ref_queue()
    queue.accept(0)
    path = tmp_path / "q.json"
    queue.save(path)
    reloaded = ReviewQueue.load(path)
    assert reloaded.get(0).target_label == "Standard"
    assert export_accepted_edges(reloaded)[0]["to_label"] == "Standard"


def test_export_fallback_label_for_hand_built_proposal():
    """A directly-built proposal (no inventory context) falls back by edge type."""
    from specguard.extraction.extractor import EdgeProposal

    queue = ReviewQueue()
    queue.add(
        EdgeProposal(
            edge_type=EdgeType.REFERS_TO,
            source_id="R-1",
            target_entity="AXI",
            confidence=0.8,
            evidence_span="AXI",
        )
    )
    queue.accept(0)
    edge = export_accepted_edges(queue)[0]
    assert edge["to_label"] == "Standard"  # from _EDGE_TYPE_FALLBACK_LABEL


def test_no_auto_accept_api_exists():
    """Structural guarantee: there is no auto-accept on the queue."""
    queue = _two_proposal_queue()
    assert not hasattr(queue, "auto_accept")
    assert not hasattr(queue, "accept_all")


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_list_accept_export(tmp_path, capsys):
    from specguard.extraction import review as review_cli

    queue = _two_proposal_queue()
    qpath = tmp_path / "q.json"
    queue.save(qpath)

    assert review_cli.main([str(qpath), "list"]) == 0
    assert review_cli.main([str(qpath), "accept", "0"]) == 0
    out_path = tmp_path / "edges.json"
    assert review_cli.main([str(qpath), "export", str(out_path)]) == 0

    exported = json.loads(out_path.read_text())
    assert len(exported) == 1
    assert exported[0]["to_id"] == "CVA6"


def test_cli_missing_queue_file(tmp_path):
    from specguard.extraction import review as review_cli

    rc = review_cli.main([str(tmp_path / "nope.json"), "list"])
    assert rc == 2


# ---------------------------------------------------------------------------
# Hand-built DERIVES_FROM ground truth (builder-side)
# ---------------------------------------------------------------------------


def test_derives_from_ground_truth_in_cva6_graph():
    """The 3 hand-annotated pairs are emitted, exactly and only, on CVA6."""
    from specguard.data.cva6_requirements import get_all_requirements
    from specguard.graph.builder import HAND_BUILT_DERIVES_FROM, build_graph

    graph = build_graph(get_all_requirements())
    derives = {
        (r.from_id, r.to_id)
        for r in graph.relationships
        if r.rel_type == "DERIVES_FROM"
    }
    assert derives == set(HAND_BUILT_DERIVES_FROM)
    assert derives == {("HPM-30", "HPM-20"), ("HPM-40", "HPM-30"), ("FET-20", "FET-10")}


def test_derives_from_not_emitted_for_foreign_datasets():
    """Graphs built from non-CVA6 requirement sets get no hand-built edges."""
    from specguard.data.cva6_requirements import Requirement
    from specguard.graph.builder import build_graph

    reqs = [
        Requirement(req_id="X-1", text="The system shall do X.", category="General"),
        # HPM-30 present but its parent HPM-20 absent: pair must NOT be emitted.
        Requirement(req_id="HPM-30", text="Partial overlap.", category="Performance"),
    ]
    graph = build_graph(reqs)
    assert not [r for r in graph.relationships if r.rel_type == "DERIVES_FROM"]
