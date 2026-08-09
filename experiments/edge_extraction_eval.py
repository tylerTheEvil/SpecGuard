"""Edge-extraction validation experiment (Phase 3b).

Runs LLM-assisted edge extraction *blind* over the 64 CVA6 requirements and
compares the proposals — **pre-review**, since this measures the model, not the
human gate — against the hand-built CVA6 graph relationships from
``specguard.graph.builder``. Reports precision/recall per edge type and writes
``results/edge_extraction_eval.json``.

Ground truth: the deterministic builder produces ``MENTIONS`` edges
(requirement -> component) via dictionary matching (75 edges), and carries a
hand-built ``DERIVES_FROM`` set (3 pairs — see ``HAND_BUILT_DERIVES_FROM`` in
``specguard.graph.builder`` for the annotation decision record; illustrative,
not statistically meaningful, since CVA6 is structurally flat). Both are
scored. ``MITIGATES`` has no hand-built ground truth, so we report proposal
counts only and a null recall — honestly labelled, never silently scored
against an empty set.

Quantified question: how much graph-population labour does the
propose-then-confirm pattern save? Recall answers "of the edges a human would
have hand-drawn, how many did the model surface for one-click confirmation".

Usage:
    python experiments/edge_extraction_eval.py --provider mock      # offline smoke
    python experiments/edge_extraction_eval.py --provider anthropic [--model ...]
    python experiments/edge_extraction_eval.py --provider ollama --model gemma4:latest

The mock run executes now and is deterministic. The anthropic run needs
ANTHROPIC_API_KEY; if selected without a key (or without the package) the
script prints a clear message and exits non-zero gracefully. The ollama run
needs a running local Ollama server and an explicit --model (see
``ollama list``); the server is pinged before the run so an unreachable
backend fails fast with a hint instead of mid-run.

When comparing providers, pass --out to keep each run's artifact separate —
the default path is the canonical (anthropic) artifact cited in the docs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
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


def _ground_truth(rel_type: str) -> set[tuple[str, str]]:
    """The hand-built edges of ``rel_type`` as (source_id, target) pairs."""
    graph = build_graph(get_all_requirements())
    return {
        (rel.from_id, rel.to_id)
        for rel in graph.relationships
        if rel.rel_type == rel_type
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


def _make_ollama_provider(model: str):
    from specguard.llm.ollama_provider import OllamaProvider

    return OllamaProvider(model)


def _ping_ollama() -> str | None:
    """Return an error string if the Ollama server is unreachable, else None."""
    import urllib.error
    import urllib.request

    from specguard.llm.ollama_provider import DEFAULT_BASE_URL

    base_url = (os.environ.get("SPECGUARD_OLLAMA_URL") or DEFAULT_BASE_URL).rstrip("/")
    try:
        with urllib.request.urlopen(f"{base_url}/api/version", timeout=5):
            return None
    except urllib.error.URLError as exc:
        return f"Ollama server unreachable at {base_url} ({exc.reason}). Start it with `ollama serve`."


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


def _run_config(provider, provider_name: str) -> dict:
    """Snapshot of the run configuration actually in effect.

    Derived from the provider *instance*, not the CLI arguments, so the
    artifact records what ran (e.g. the resolved default model) rather than
    what was requested. Anthropic deliberately sends no sampling params
    (current Opus models reject them), so temperature is recorded as
    ``"api_default"`` — the limitation is explicit instead of hidden. The
    mock provider replays canned responses and samples nothing: null.
    """
    options = getattr(provider, "options", None) or {}
    anthropic_default = "api_default" if provider_name == "anthropic" else None
    config: dict = {
        "provider": provider_name,
        "model": getattr(provider, "model", None),
        "temperature": options.get("temperature", anthropic_default),
        "seed": options.get("seed"),
        "max_tokens": getattr(provider, "max_tokens", None),
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if "num_ctx" in options:
        config["num_ctx"] = options["num_ctx"]
    return config


def _edge_log(
    edge_type: str,
    proposals: dict[tuple[str, str], object],
    truth: set[tuple[str, str]] | None,
) -> list[dict]:
    """Pair-level record of every proposal (TP/FP) plus unproposed truth (FN).

    Enables post-hoc adjudication (which ground-truth pairs were recovered,
    what the spurious proposals actually were) without re-running the LLM.
    Sorted for stable artifact diffs. ``truth is None`` marks an unscored type.
    """
    entries = []
    for (src, tgt), p in sorted(proposals.items()):
        verdict = "unscored" if truth is None else ("TP" if (src, tgt) in truth else "FP")
        entries.append(
            {
                "source_id": src,
                "target": tgt,
                "edge_type": edge_type,
                "evidence_span": p.evidence_span,
                "confidence": p.confidence,
                "verdict": verdict,
            }
        )
    if truth is not None:
        for src, tgt in sorted(truth - set(proposals)):
            entries.append(
                {
                    "source_id": src,
                    "target": tgt,
                    "edge_type": edge_type,
                    "evidence_span": None,
                    "confidence": None,
                    "verdict": "FN",
                }
            )
    return entries


def run(provider, *, provider_name: str) -> dict:
    reqs = get_all_requirements()
    inventory = _build_inventory()
    pairs = [(r.req_id, r.text) for r in reqs]

    results = extract_edges(provider, pairs, inventory)

    # First proposal per unique (source, target) pair; duplicates collapse so
    # the aggregate counts keep their original set semantics.
    proposals_by_type: dict[str, dict[tuple[str, str], object]] = {
        e.value: {} for e in EdgeType
    }
    total_rejected = 0
    for res in results:
        total_rejected += len(res.rejected)
        for p in res.proposals:
            proposals_by_type[p.edge_type.value].setdefault(
                (p.source_id, p.target_entity), p
            )

    per_type: dict[str, dict] = {}
    # MENTIONS (75, dictionary-matched) and DERIVES_FROM (3, hand-annotated —
    # illustrative only, see HAND_BUILT_DERIVES_FROM) have ground truth.
    for et in ("MENTIONS", "DERIVES_FROM"):
        truth = _ground_truth(et)
        per_type[et] = {
            "proposed": len(proposals_by_type[et]),
            "ground_truth": len(truth),
            **_score(set(proposals_by_type[et]), truth),
            "edges": _edge_log(et, proposals_by_type[et], truth),
        }
    per_type["DERIVES_FROM"]["note"] = (
        "3-pair hand-built set; illustrative, not statistically meaningful "
        "(CVA6 is structurally flat — no genuine HLR->LLR hierarchy)"
    )
    # MITIGATES: no hand-built ground truth — counts only.
    per_type["MITIGATES"] = {
        "proposed": len(proposals_by_type["MITIGATES"]),
        "ground_truth": None,
        "note": "no hand-built ground truth; counts reported, not scored",
        "edges": _edge_log("MITIGATES", proposals_by_type["MITIGATES"], None),
    }

    return {
        "provider": provider_name,
        # The model the provider will actually call, never the raw CLI arg
        # (which is null on the Anthropic default path).
        "model": getattr(provider, "model", None),
        "config": _run_config(provider, provider_name),
        "requirements_evaluated": len(reqs),
        "evidence_guard_rejections": total_rejected,
        "per_edge_type": per_type,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=["mock", "anthropic", "ollama"], default="mock"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model id (anthropic: optional; ollama: required, see `ollama list`).",
    )
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
    elif args.provider == "ollama":
        if not args.model:
            print(
                "--provider ollama requires an explicit --model "
                "(e.g. --model gemma4:latest; see `ollama list`).",
                file=sys.stderr,
            )
            return 1
        error = _ping_ollama()
        if error is not None:
            print(error, file=sys.stderr)
            return 1
        provider = _make_ollama_provider(args.model)
    else:
        provider = _make_mock_provider()

    report = run(provider, provider_name=args.provider)

    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print("=" * 70)
    print(f"EDGE-EXTRACTION EVAL  (provider={report['provider']} model={report['model']})")
    print("=" * 70)
    print(f"Requirements evaluated : {report['requirements_evaluated']}")
    print(f"Evidence-guard rejects : {report['evidence_guard_rejections']}")
    for et in ("MENTIONS", "DERIVES_FROM"):
        m = report["per_edge_type"][et]
        prec = "n/a" if m["precision"] is None else f"{m['precision']:.3f}"
        rec = "n/a" if m["recall"] is None else f"{m['recall']:.3f}"
        print(
            f"{et}: proposed={m['proposed']} truth={m['ground_truth']} "
            f"precision={prec} recall={rec}"
        )
    print(f"MITIGATES: proposed={report['per_edge_type']['MITIGATES']['proposed']} (unscored)")
    # DERIVES_FROM is small (3 GT pairs) — show the pair-level verdicts inline.
    for e in report["per_edge_type"]["DERIVES_FROM"]["edges"]:
        print(f"  DERIVES_FROM {e['verdict']}: {e['source_id']} -> {e['target']}")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
