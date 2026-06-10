"""Edge-extraction validation experiment (Phase 3b).

Runs LLM-assisted edge extraction *blind* over the 64 CVA6 requirements and
compares the proposals — **pre-review**, since this measures the model, not the
human gate — against the hand-built CVA6 graph relationships from
``specguard.graph.builder``. Reports precision/recall per edge type and writes
``results/edge_extraction_eval.json``.

Ground truth: the deterministic builder produces ``MENTIONS`` edges
(requirement -> component) via dictionary matching. Those are the relations
with hand-built ground truth and form the evaluable set. ``DERIVES_FROM`` /
``MITIGATES`` have no hand-built ground truth (the builder leaves them as
placeholders), so for those types we report proposal counts only and a null
recall — honestly labelled, never silently scored against an empty set.

Quantified question: how much graph-population labour does the
propose-then-confirm pattern save? Recall answers "of the edges a human would
have hand-drawn, how many did the model surface for one-click confirmation".

Usage:
    python experiments/edge_extraction_eval.py --provider mock      # offline smoke
    python experiments/edge_extraction_eval.py --provider anthropic [--model ...]

The mock run executes now and is deterministic. The anthropic run needs
ANTHROPIC_API_KEY; if selected without a key (or without the package) the
script prints a clear message and exits non-zero gracefully.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from specguard.data.cva6_requirements import get_all_requirements
from specguard.extraction.extractor import EdgeType, extract_edges
from specguard.graph.builder import (
    KNOWN_COMPONENTS,
    KNOWN_STANDARDS,
    build_graph,
)

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "edge_extraction_eval.json"


def _build_inventory() -> dict[str, list[str]]:
    """Allowed extraction targets, drawn from the builder's known entities."""
    reqs = get_all_requirements()
    return {
        "components": list(KNOWN_COMPONENTS.keys()),
        "standards": list(KNOWN_STANDARDS.keys()),
        "requirements": [r.req_id for r in reqs],
    }


def _ground_truth_mentions() -> set[tuple[str, str]]:
    """The hand-built MENTIONS edges as (source_id, target) pairs."""
    graph = build_graph(get_all_requirements())
    return {
        (rel.from_id, rel.to_id)
        for rel in graph.relationships
        if rel.rel_type == "MENTIONS"
    }


def _make_mock_provider():
    """A MockProvider that replays plausible per-requirement proposals.

    For each requirement, it proposes a MENTIONS edge to every known component
    whose token literally occurs in the text, quoting that token as the
    evidence span. This produces a realistic, deterministic offline run that
    overlaps heavily (but not perfectly) with ground truth, so the eval
    machinery and metrics are exercised end-to-end without a network call.
    """
    from specguard.llm.mock_provider import MockProvider

    responses: dict[str, str] = {}
    for req in get_all_requirements():
        edges = []
        for comp in KNOWN_COMPONENTS:
            if comp in req.text:
                edges.append(
                    {
                        "edge_type": "MENTIONS",
                        "target_entity": comp,
                        "confidence": 0.9,
                        "evidence_span": comp,
                    }
                )
        # Key the canned response by the unique requirement id present in prompt.
        responses[f"Requirement id: {req.req_id}\n"] = json.dumps({"edges": edges})
    return MockProvider(responses=responses, default=json.dumps({"edges": []}))


def _make_anthropic_provider(model: str | None):
    from specguard.llm.anthropic_provider import DEFAULT_MODEL, AnthropicProvider

    return AnthropicProvider(model=model or DEFAULT_MODEL)


def _score(proposals: set[tuple[str, str]], truth: set[tuple[str, str]]) -> dict:
    tp = len(proposals & truth)
    fp = len(proposals - truth)
    fn = len(truth - proposals)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
    }


def run(provider, *, provider_name: str, model: str | None) -> dict:
    reqs = get_all_requirements()
    inventory = _build_inventory()
    pairs = [(r.req_id, r.text) for r in reqs]

    results = extract_edges(provider, pairs, inventory)

    proposals_by_type: dict[str, set[tuple[str, str]]] = {e.value: set() for e in EdgeType}
    total_rejected = 0
    for res in results:
        total_rejected += len(res.rejected)
        for p in res.proposals:
            proposals_by_type[p.edge_type.value].add((p.source_id, p.target_entity))

    gt_mentions = _ground_truth_mentions()

    per_type: dict[str, dict] = {}
    # MENTIONS has hand-built ground truth.
    per_type["MENTIONS"] = {
        "proposed": len(proposals_by_type["MENTIONS"]),
        "ground_truth": len(gt_mentions),
        **_score(proposals_by_type["MENTIONS"], gt_mentions),
    }
    # DERIVES_FROM / MITIGATES: no hand-built ground truth — counts only.
    for et in ("DERIVES_FROM", "MITIGATES"):
        per_type[et] = {
            "proposed": len(proposals_by_type[et]),
            "ground_truth": None,
            "note": "no hand-built ground truth; counts reported, not scored",
        }

    return {
        "provider": provider_name,
        "model": model,
        "requirements_evaluated": len(reqs),
        "evidence_guard_rejections": total_rejected,
        "per_edge_type": per_type,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=["mock", "anthropic"], default="mock"
    )
    parser.add_argument("--model", default=None, help="Model id (anthropic only).")
    parser.add_argument(
        "--out", default=str(RESULTS_PATH), help="Output JSON path."
    )
    args = parser.parse_args(argv)

    if args.provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print(
                "ANTHROPIC_API_KEY is not set — the live edge-extraction eval "
                "cannot run.\nSet the key and re-run, or use --provider mock for "
                "the offline smoke test.",
                file=sys.stderr,
            )
            return 1
        try:
            provider = _make_anthropic_provider(args.model)
        except ImportError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    else:
        provider = _make_mock_provider()

    report = run(provider, provider_name=args.provider, model=args.model)

    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print("=" * 70)
    print(f"EDGE-EXTRACTION EVAL  (provider={report['provider']})")
    print("=" * 70)
    print(f"Requirements evaluated : {report['requirements_evaluated']}")
    print(f"Evidence-guard rejects : {report['evidence_guard_rejections']}")
    m = report["per_edge_type"]["MENTIONS"]
    prec = "n/a" if m["precision"] is None else f"{m['precision']:.3f}"
    rec = "n/a" if m["recall"] is None else f"{m['recall']:.3f}"
    print(
        f"MENTIONS: proposed={m['proposed']} truth={m['ground_truth']} "
        f"precision={prec} recall={rec}"
    )
    for et in ("DERIVES_FROM", "MITIGATES"):
        print(f"{et}: proposed={report['per_edge_type'][et]['proposed']} (unscored)")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
