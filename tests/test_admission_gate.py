"""Structural human-gate tests for the LLM-originated Neo4j write path (P0.3).

These run WITHOUT a database: :func:`merge_accepted_edges` validates provenance
*before* opening any connection, so the rejection path is exercised purely in
memory (no ``@pytest.mark.neo4j``). The happy path — an actual MERGE — lives in
``test_neo4j_io.py`` behind the neo4j marker.

What is under test is the P0.3 fix: the public write path refuses any edge that
is not shaped like review-queue output (``human_confirmed is True`` **and**
``review_status == "ACCEPTED"``), so a raw ``list[dict]`` can no longer be
written to the graph in silent bypass of human review.
"""

from __future__ import annotations

import pytest

from specguard.extraction.extractor import EdgeProposal, EdgeType
from specguard.extraction.review import ReviewQueue, export_accepted_edges
from specguard.graph.neo4j_io import _is_human_accepted, merge_accepted_edges


def _raw_edge(properties: dict) -> dict:
    """A structurally-valid edge dict with caller-controlled provenance props."""
    return {
        "from_label": "Requirement",
        "from_id": "R-1",
        "to_label": "Component",
        "to_id": "MMU",
        "rel_type": "MENTIONS",
        "properties": properties,
    }


def _accepted_queue() -> ReviewQueue:
    queue = ReviewQueue()
    queue.add(
        EdgeProposal(
            edge_type=EdgeType.MENTIONS,
            source_id="R-1",
            target_entity="MMU",
            confidence=0.9,
            evidence_span="the MMU",
        )
    )
    queue.accept(0)
    return queue


def test_merge_refuses_edge_with_no_provenance():
    with pytest.raises(ValueError, match="human-review provenance"):
        merge_accepted_edges([_raw_edge({})])


def test_merge_refuses_human_confirmed_without_accepted_status():
    # human_confirmed alone is not enough — the ACCEPTED lifecycle marker that
    # only the review queue stamps must also be present.
    with pytest.raises(ValueError):
        merge_accepted_edges([_raw_edge({"human_confirmed": True})])


def test_merge_refuses_forged_status_without_human_confirmed():
    with pytest.raises(ValueError):
        merge_accepted_edges([_raw_edge({"review_status": "ACCEPTED"})])


def test_merge_refuses_batch_if_any_edge_unconfirmed():
    good = export_accepted_edges(_accepted_queue())[0]
    bad = _raw_edge({"human_confirmed": True})  # missing review_status
    with pytest.raises(ValueError):
        merge_accepted_edges([good, bad])


def test_export_output_passes_the_gate_predicate():
    """Edges emitted by export_accepted_edges satisfy the write-path predicate."""
    edges = export_accepted_edges(_accepted_queue())
    assert edges
    assert all(_is_human_accepted(e) for e in edges)
