"""Human-in-the-loop review queue for LLM-proposed graph edges.

Proposals from :mod:`specguard.extraction.extractor` are persisted to a JSON
file. A reviewer accepts or rejects them one by one (or by id) via the crude
CLI (``python -m specguard.extraction.review``). Only ACCEPTED edges can be
exported into the shape the graph builder consumes.

Authority model (decision rationale)
-------------------------------------
The export path is the architectural enforcement point for "the LLM is never
authoritative": :func:`export_accepted_edges` emits *only* items in the
``ACCEPTED`` state, and there is deliberately **no auto-accept** API — every
edge that reaches the graph passed through an explicit human decision. This
mirrors the Layer 2 analyst pattern: the model proposes, the human disposes.

The CLI is intentionally minimal (stdlib ``argparse``, line-based output). It
is a research scaffold to demonstrate the workflow, not a product UI.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from specguard.extraction.extractor import EdgeProposal, EdgeType, ExtractionResult


class ReviewStatus(StrEnum):
    """Lifecycle state of a queued proposal."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass
class ReviewItem:
    """A proposal plus its review state and a stable id."""

    item_id: int
    edge_type: EdgeType
    source_id: str
    target_entity: str
    confidence: float
    evidence_span: str
    status: ReviewStatus = ReviewStatus.PENDING

    @classmethod
    def from_proposal(cls, item_id: int, proposal: EdgeProposal) -> ReviewItem:
        return cls(
            item_id=item_id,
            edge_type=proposal.edge_type,
            source_id=proposal.source_id,
            target_entity=proposal.target_entity,
            confidence=proposal.confidence,
            evidence_span=proposal.evidence_span,
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["edge_type"] = self.edge_type.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ReviewItem:
        return cls(
            item_id=int(d["item_id"]),
            edge_type=EdgeType(d["edge_type"]),
            source_id=d["source_id"],
            target_entity=d["target_entity"],
            confidence=float(d["confidence"]),
            evidence_span=d["evidence_span"],
            status=ReviewStatus(d.get("status", "PENDING")),
        )


@dataclass
class ReviewQueue:
    """An ordered, persistable collection of review items."""

    items: list[ReviewItem] = field(default_factory=list)

    # ---- construction -----------------------------------------------------

    @classmethod
    def from_results(cls, results: list[ExtractionResult]) -> ReviewQueue:
        """Build a queue from extraction results, assigning sequential ids."""
        queue = cls()
        for result in results:
            for proposal in result.proposals:
                queue.add(proposal)
        return queue

    def add(self, proposal: EdgeProposal) -> ReviewItem:
        item = ReviewItem.from_proposal(len(self.items), proposal)
        self.items.append(item)
        return item

    # ---- queries ----------------------------------------------------------

    def get(self, item_id: int) -> ReviewItem | None:
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None

    def pending(self) -> list[ReviewItem]:
        return [i for i in self.items if i.status is ReviewStatus.PENDING]

    def accepted(self) -> list[ReviewItem]:
        return [i for i in self.items if i.status is ReviewStatus.ACCEPTED]

    # ---- decisions --------------------------------------------------------

    def accept(self, item_id: int) -> bool:
        item = self.get(item_id)
        if item is None:
            return False
        item.status = ReviewStatus.ACCEPTED
        return True

    def reject(self, item_id: int) -> bool:
        item = self.get(item_id)
        if item is None:
            return False
        item.status = ReviewStatus.REJECTED
        return True

    # ---- persistence ------------------------------------------------------

    def save(self, path: str | Path) -> None:
        payload = {"items": [i.to_dict() for i in self.items]}
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: str | Path) -> ReviewQueue:
        payload = json.loads(Path(path).read_text())
        return cls(items=[ReviewItem.from_dict(d) for d in payload.get("items", [])])


def export_accepted_edges(queue: ReviewQueue) -> list[dict]:
    """Emit ACCEPTED edges in the shape the graph builder consumes.

    Each edge mirrors :class:`specguard.graph.builder.GraphRelationship`
    fields (``from_label``, ``from_id``, ``to_label``, ``to_id``, ``rel_type``)
    plus provenance properties so a downstream merge is traceable to its
    LLM-proposed-then-human-confirmed origin.

    Only ``ACCEPTED`` items are emitted — this is the structural guarantee that
    the LLM is never authoritative. There is no parameter to relax it.
    """
    edges: list[dict] = []
    for item in queue.accepted():
        to_label = "Requirement" if item.edge_type is not EdgeType.MENTIONS else "Component"
        edges.append(
            {
                "from_label": "Requirement",
                "from_id": item.source_id,
                "to_label": to_label,
                "to_id": item.target_entity,
                "rel_type": item.edge_type.value,
                "properties": {
                    "source": "llm_extraction",
                    "confidence": item.confidence,
                    "evidence_span": item.evidence_span,
                    "human_confirmed": True,
                },
            }
        )
    return edges


# ============================================================================
# CLI — deliberately crude (research scaffold, not a product)
# ============================================================================


def _print_item(item: ReviewItem) -> None:
    print(
        f"[{item.item_id}] {item.status.value:8s} "
        f"{item.source_id} -[{item.edge_type.value}]-> {item.target_entity} "
        f"(conf={item.confidence:.2f})"
    )
    print(f"        evidence: \"{item.evidence_span}\"")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m specguard.extraction.review",
        description="Review LLM-proposed graph edges (human-in-the-loop).",
    )
    parser.add_argument("queue_file", help="Path to the JSON review-queue file.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List proposals.")
    p_list.add_argument(
        "--pending", action="store_true", help="Show only pending proposals."
    )

    p_accept = sub.add_parser("accept", help="Accept proposals by id.")
    p_accept.add_argument("ids", type=int, nargs="+", help="Item id(s) to accept.")

    p_reject = sub.add_parser("reject", help="Reject proposals by id.")
    p_reject.add_argument("ids", type=int, nargs="+", help="Item id(s) to reject.")

    p_export = sub.add_parser(
        "export", help="Write accepted edges (graph-builder shape) to a JSON file."
    )
    p_export.add_argument("out_file", help="Output path for accepted edges.")

    sub.add_parser(
        "merge-to-neo4j",
        help="MERGE accepted edges into the live Neo4j graph (needs the [graph] extra).",
    )

    args = parser.parse_args(argv)

    queue_path = Path(args.queue_file)
    if not queue_path.exists():
        print(f"Queue file not found: {queue_path}", file=sys.stderr)
        return 2
    queue = ReviewQueue.load(queue_path)

    if args.command == "list":
        items = queue.pending() if args.pending else queue.items
        if not items:
            print("(no items)")
        for item in items:
            _print_item(item)
        print(
            f"\nTotal: {len(queue.items)} | pending: {len(queue.pending())} | "
            f"accepted: {len(queue.accepted())}"
        )
        return 0

    if args.command in ("accept", "reject"):
        action = queue.accept if args.command == "accept" else queue.reject
        for item_id in args.ids:
            ok = action(item_id)
            if ok:
                print(f"{args.command}ed [{item_id}]")
            else:
                print(f"no such item: [{item_id}]", file=sys.stderr)
        queue.save(queue_path)
        return 0

    if args.command == "export":
        edges = export_accepted_edges(queue)
        Path(args.out_file).write_text(json.dumps(edges, indent=2, ensure_ascii=False))
        print(f"Exported {len(edges)} accepted edge(s) to {args.out_file}")
        return 0

    if args.command == "merge-to-neo4j":
        edges = export_accepted_edges(queue)
        if not edges:
            print("No accepted edges to merge.")
            return 0
        try:
            from specguard.graph.neo4j_io import merge_accepted_edges
        except ImportError as exc:  # pragma: no cover - only without [graph]
            print(f"Neo4j write requires the [graph] extra: {exc}", file=sys.stderr)
            return 2
        try:
            result = merge_accepted_edges(edges)
        except ImportError as exc:
            print(
                f"Neo4j driver not installed (install '.[graph]'): {exc}",
                file=sys.stderr,
            )
            return 2
        print(f"Merged {result['edges_merged']} accepted edge(s) into Neo4j.")
        return 0

    return 1  # pragma: no cover - argparse requires a subcommand


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
