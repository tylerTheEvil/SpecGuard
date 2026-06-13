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


def test_export_empty_when_none_accepted():
    queue = _two_proposal_queue()
    assert export_accepted_edges(queue) == []


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
