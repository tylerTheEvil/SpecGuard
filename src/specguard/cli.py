"""Unified ``specguard`` console entry point (Phase 5a).

This is the deterministic tool surface an agent host (a Claude session, a CI
script, an MCP shim later) drives. It wraps the existing machinery —
Layer 1 pipeline, graph builder, compliance engine, NetworkX queries — behind
a single command with stable flags and a ``--json`` mode everywhere.

Hard invariant (per the improvement plan, "the invariant that must survive
integration"): **the CLI is LLM-free.** Verdicts come only from the
deterministic pipeline. The single exception is ``specguard extract``, an
explicit wrapper over the human-gated BYOM extraction module; even there the
LLM only *proposes* — nothing it produces reaches the graph without passing
through ``specguard review`` (accept) and the human-confirmed merge path.

Import discipline: the module imports with no optional extras. Anything that
needs ``neo4j`` (the ``[graph]`` extra) or ``anthropic`` (the ``[llm]`` extra)
is imported lazily inside the handler that uses it, so ``specguard assess`` /
``import`` (no DB) / ``comply --memory`` / ``graph <named>`` all run on the
bare core.

Exit codes for ``assess`` let a script/session branch on the worst gate:
``0`` all PASS, ``1`` at least one WARN (no FAIL), ``2`` at least one FAIL.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from specguard.core import aggregate_metrics, assess_dataset
from specguard.io.parsers import ParseError, parse_requirements

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _read_input_arg(path: str) -> str:
    """Return the raw payload for a path argument; ``-`` means stdin."""
    if path == "-":
        return sys.stdin.read()
    return path


def _emit_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _top_triggers(result, limit: int = 3) -> list[str]:
    """Return up to ``limit`` smell triggers, highest severity first."""
    order = {"high": 0, "medium": 1, "low": 2}
    hits = sorted(
        result.smell_report.hits,
        key=lambda h: order.get(h.severity, 9),
    )
    return [f"{h.smell_type.value}:{h.trigger}" for h in hits[:limit]]


# ---------------------------------------------------------------------------
# assess
# ---------------------------------------------------------------------------


def cmd_assess(args: argparse.Namespace) -> int:
    """Parse requirements, run Layer 1, print gates. Exit 0/1/2 by worst gate."""
    try:
        requirements = parse_requirements(_read_input_arg(args.path), fmt=args.format)
    except ParseError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 3
    results = assess_dataset(requirements)
    metrics = aggregate_metrics(results)

    if args.json:
        _emit_json(
            {
                "results": [
                    {
                        "id": r.requirement_id,
                        "gate": r.gate_decision,
                        "overall": round(r.quality_scores.overall, 3),
                        "completeness": round(r.quality_scores.completeness, 3),
                        "consistency": round(r.quality_scores.consistency, 3),
                        "verifiability": round(r.quality_scores.verifiability, 3),
                        "smell_count": r.smell_report.smell_count,
                        "smells": _top_triggers(r, limit=100),
                    }
                    for r in results
                ],
                "aggregate": metrics,
            }
        )
    else:
        print(f"{'ID':<12} {'GATE':<5} {'OVERALL':<8} {'SMELLS':<7} TOP TRIGGERS")
        print("-" * 78)
        for r in results:
            triggers = ", ".join(_top_triggers(r)) or "-"
            print(
                f"{r.requirement_id:<12} {r.gate_decision:<5} "
                f"{r.quality_scores.overall:<8.3f} {r.smell_report.smell_count:<7} {triggers}"
            )
        print("-" * 78)
        print(
            f"{metrics['total_requirements']} requirements | "
            f"PASS {metrics['gate_pass']} / WARN {metrics['gate_warn']} / "
            f"FAIL {metrics['gate_fail']} | avg overall {metrics['avg_overall']:.3f}"
        )

    if metrics["gate_fail"] > 0:
        return 2
    if metrics["gate_warn"] > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


def cmd_import(args: argparse.Namespace) -> int:
    """Parse, build the graph, report counts; optionally MERGE into Neo4j."""
    tag = args.dataset_tag
    if not tag or not tag.strip():
        print("Error: --dataset-tag must be a non-empty, non-whitespace string.", file=sys.stderr)
        return 3
    tag = tag.strip()

    try:
        requirements = parse_requirements(_read_input_arg(args.path), fmt=args.format)
    except ParseError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 3

    from specguard.graph.builder import build_graph

    results = assess_dataset(requirements)
    graph = build_graph(requirements, results)
    stats = graph.stats()

    merge_summary: dict | None = None
    if args.to_neo4j:
        try:
            from specguard.graph.neo4j_io import merge_graph
        except ImportError as exc:  # pragma: no cover - only without [graph]
            print(f"Neo4j write requires the [graph] extra: {exc}", file=sys.stderr)
            return 2
        try:
            merge_summary = merge_graph(graph, dataset_tag=tag)
        except ImportError as exc:
            print(f"Neo4j driver not installed (install '.[graph]'): {exc}", file=sys.stderr)
            return 2

    if args.json:
        _emit_json(
            {
                "dataset_tag": tag,
                "stats": stats,
                "to_neo4j": bool(args.to_neo4j),
                "merge": merge_summary,
            }
        )
    else:
        print(f"Dataset tag: {tag}")
        print(f"Nodes: {stats['total_nodes']}  Relationships: {stats['total_relationships']}")
        nodes_line = ", ".join(f"{k}={v}" for k, v in stats["nodes_by_label"].items())
        edges_line = ", ".join(f"{k}={v}" for k, v in stats["relationships_by_type"].items())
        print("Nodes by label:    " + nodes_line)
        print("Edges by type:     " + edges_line)
        if merge_summary is not None:
            print(
                f"MERGED into Neo4j: {merge_summary['nodes_merged']} nodes, "
                f"{merge_summary['relationships_merged']} relationships "
                f"(dataset='{merge_summary['dataset']}', no clear)."
            )
        else:
            print("(dry run — pass --to-neo4j to MERGE into the live graph)")
    return 0


# ---------------------------------------------------------------------------
# comply
# ---------------------------------------------------------------------------


def cmd_comply(args: argparse.Namespace) -> int:
    """Run the 15 codified objectives, in-memory (default) or on Neo4j."""
    from specguard.compliance import (
        CROSS_DOMAIN_OBJECTIVES,
        DO_178C_OBJECTIVES,
        DO_254_OBJECTIVES,
        run_compliance_check,
    )

    objectives = DO_178C_OBJECTIVES + DO_254_OBJECTIVES + CROSS_DOMAIN_OBJECTIVES

    if args.neo4j:
        try:
            from specguard.compliance.neo4j_runner import Neo4jGraphRunner
        except ImportError as exc:  # pragma: no cover - only without [graph]
            print(f"Neo4j compliance requires the [graph] extra: {exc}", file=sys.stderr)
            return 2
        runner = Neo4jGraphRunner()
        try:
            runner.connect()
        except ImportError as exc:
            print(f"Neo4j driver not installed (install '.[graph]'): {exc}", file=sys.stderr)
            return 2
        try:
            report = run_compliance_check(runner, objectives, standard_name="ALL")
        finally:
            runner.close()
        backend = "neo4j"
    else:
        # In-memory fallback — the demo's pattern-recognition runner, re-homed
        # inside the package so it is importable from the installed console
        # script (scripts/ is not on sys.path there).
        from specguard.compliance.memory_runner import build_demo_graph, make_graph_runner

        graph = build_demo_graph()
        runner = make_graph_runner(graph)
        report = run_compliance_check(runner, objectives, standard_name="ALL")
        backend = "memory"

    passing = len(report.passing_objective_ids)
    total = report.total_objectives_checked

    if args.json:
        _emit_json(
            {
                "backend": backend,
                "dataset": args.dataset,
                "total_objectives": total,
                "passing": passing,
                "violations": report.violation_count,
                "passing_objective_ids": list(report.passing_objective_ids),
            }
        )
    else:
        print(f"Compliance check ({backend} backend, dataset={args.dataset})")
        print(f"Objectives checked: {total}")
        print(f"Passing:            {passing} ({passing / total:.1%})" if total else "Passing: 0")
        print(f"Violations:         {report.violation_count}")
    return 0


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------

# Named queries over the in-memory CVA6 graph (q6/q8/q14 + a few useful peers).
_NAMED_QUERIES = {
    "q6": ("q6_cross_cutting_requirements", "Requirements mentioning 2+ components"),
    "q8": ("q8_safety_critical_with_smells", "Safety-critical requirements with smells"),
    "q14": ("q14_potential_conflicts", "Requirement pairs sharing 2+ components (screening)"),
}


def cmd_graph(args: argparse.Namespace) -> int:
    """Named NetworkX queries on the CVA6 graph, or raw read-only Cypher."""
    if args.cypher is not None:
        try:
            from specguard.graph.neo4j_io import run_readonly_cypher
        except ImportError as exc:  # pragma: no cover - only without [graph]
            print(f"Raw Cypher requires the [graph] extra: {exc}", file=sys.stderr)
            return 2
        try:
            rows = run_readonly_cypher(args.cypher)
        except ValueError as exc:
            print(f"Refused: {exc}", file=sys.stderr)
            return 3
        except ImportError as exc:
            print(f"Neo4j driver not installed (install '.[graph]'): {exc}", file=sys.stderr)
            return 2
        if args.json:
            _emit_json(rows)
        else:
            if not rows:
                print("(no rows)")
            for row in rows:
                print(row)
        return 0

    if args.named is None:
        print("Provide a named query (q6/q8/q14) or --cypher QUERY.", file=sys.stderr)
        return 3
    if args.named not in _NAMED_QUERIES:
        print(
            f"Unknown named query {args.named!r}. Available: {', '.join(_NAMED_QUERIES)}.",
            file=sys.stderr,
        )
        return 3

    from specguard.core import assess_dataset as _assess
    from specguard.data.cva6_requirements import get_all_requirements
    from specguard.graph import queries as q
    from specguard.graph.builder import build_graph
    from specguard.graph.queries import graph_to_networkx

    reqs = get_all_requirements()
    rg = build_graph(reqs, _assess(reqs))
    g = graph_to_networkx(rg)

    func_name, description = _NAMED_QUERIES[args.named]
    rows = getattr(q, func_name)(g)

    if args.json:
        _emit_json({"query": args.named, "description": description, "rows": rows})
    else:
        print(f"{args.named}: {description}")
        print("-" * 60)
        if not rows:
            print("(no rows)")
        for row in rows:
            print(row)
    return 0


# ---------------------------------------------------------------------------
# extract (the only LLM-touching command; lazy import of the [llm] extra)
# ---------------------------------------------------------------------------


def cmd_extract(args: argparse.Namespace) -> int:
    """Propose edges via the BYOM extraction module into a review queue.

    LLM-originated proposals only — they enter the graph solely after
    ``specguard review accept`` + ``review merge-to-neo4j``.
    """
    try:
        from specguard.extraction import ReviewQueue, extract_edges
    except ImportError as exc:  # pragma: no cover
        print(f"Extraction requires the extraction module: {exc}", file=sys.stderr)
        return 2

    try:
        requirements = parse_requirements(_read_input_arg(args.path), fmt=args.format)
    except ParseError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 3

    # Provider selection (lazy; the [llm] extra is needed only for anthropic).
    if args.provider == "mock":
        from specguard.llm.mock_provider import MockProvider

        provider = MockProvider(default='{"edges": []}')
    else:
        try:
            from specguard.llm.anthropic_provider import AnthropicProvider
        except ImportError as exc:
            print(
                f"The anthropic provider requires the [llm] extra (pip install -e '.[llm]'): {exc}",
                file=sys.stderr,
            )
            return 2
        try:
            provider = AnthropicProvider(model=args.model) if args.model else AnthropicProvider()
        except ImportError as exc:
            print(
                f"The anthropic provider requires the [llm] extra (pip install -e '.[llm]'): {exc}",
                file=sys.stderr,
            )
            return 2

    # Allowed-target inventory from the deterministic builder's known entities.
    from specguard.graph.builder import KNOWN_COMPONENTS, KNOWN_STANDARDS

    inventory = {
        "components": list(KNOWN_COMPONENTS.keys()),
        "standards": list(KNOWN_STANDARDS.keys()),
        "requirements": [r.req_id for r in requirements],
    }

    results = extract_edges(provider, [(r.req_id, r.text) for r in requirements], inventory)

    # Extend an existing queue if present, else create a new one.
    from pathlib import Path

    queue_path = Path(args.queue)
    queue = ReviewQueue.load(queue_path) if queue_path.exists() else ReviewQueue()
    added = 0
    for result in results:
        for proposal in result.proposals:
            queue.add(proposal)
            added += 1
    queue.save(queue_path)

    print(f"Proposed {added} edge(s) from {len(requirements)} requirement(s).")
    print(f"Review queue: {queue_path} (total {len(queue.items)} items).")
    print("Next: specguard review <queue> list | accept <ids> | merge-to-neo4j")
    return 0


# ---------------------------------------------------------------------------
# review (delegates to the existing review CLI)
# ---------------------------------------------------------------------------


def cmd_review(args: argparse.Namespace, extra: list[str]) -> int:
    """Delegate to ``specguard.extraction.review.main`` (incl. merge-to-neo4j)."""
    from specguard.extraction.review import main as review_main

    return review_main([args.queue, args.action, *extra])


# ---------------------------------------------------------------------------
# taxonomy  (checkability taxonomy — stdlib-only, Contribution #2)
# ---------------------------------------------------------------------------


def _load_taxonomy_or_exit(args: argparse.Namespace):
    """Load the taxonomy, printing a clean error and signalling exit 2 on failure.

    Returns ``(rows, None)`` on success or ``(None, exit_code)`` on failure.
    """
    from specguard.taxonomy import load_taxonomy

    try:
        return load_taxonomy(args.path), None
    except (FileNotFoundError, ValueError) as exc:
        print(f"taxonomy: {exc}", file=sys.stderr)
        return None, 2


def cmd_taxonomy_validate(args: argparse.Namespace) -> int:
    """Validate the taxonomy CSV; exit 0 if clean, 1 if any error, 2 if unreadable."""
    from specguard.taxonomy import validate

    rows, exit_code = _load_taxonomy_or_exit(args)
    if rows is None:
        return exit_code

    errors = validate(rows)
    if args.json:
        _emit_json(
            {
                "ok": not errors,
                "rows": len(rows),
                "error_count": len(errors),
                "errors": [e.as_dict() for e in errors],
            }
        )
    else:
        if not errors:
            print(f"Taxonomy valid — {len(rows)} rows, 0 errors. ✓")
        else:
            print(f"Taxonomy INVALID — {len(errors)} error(s) across {len(rows)} rows:")
            for e in errors:
                print(f"  [{e.objective_id}] {e.field}: {e.message}")
    return 0 if not errors else 1


def cmd_taxonomy_stats(args: argparse.Namespace) -> int:
    """Report counts per standard / zone / class / template."""
    from specguard.taxonomy import compute_stats

    rows, exit_code = _load_taxonomy_or_exit(args)
    if rows is None:
        return exit_code

    stats = compute_stats(rows)
    if args.json:
        _emit_json(stats)
    else:
        print(f"Taxonomy statistics — {stats['total']} rows")
        print(f"  codified: {stats['codified']}   classified-only: {stats['classified_only']}")
        print(f"  distinct templates: {stats['distinct_templates']}")
        for label, key in (
            ("by standard", "by_standard"),
            ("by zone", "by_zone"),
            ("by semantic class", "by_semantic_class"),
            ("by template", "by_template"),
        ):
            print(f"  {label}:")
            for name, count in sorted(stats[key].items()):  # type: ignore[attr-defined]
                print(f"    {name}: {count}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="specguard",
        description="SpecGuard deterministic tool surface (Layer 1 + graph + compliance).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # assess
    p_assess = sub.add_parser("assess", help="Run the Layer 1 quality pipeline.")
    p_assess.add_argument("path", help="Requirements file, or '-' for stdin.")
    p_assess.add_argument("--format", default="auto", help="auto|text|md|csv (default auto).")
    p_assess.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_assess.set_defaults(func=cmd_assess)

    # import
    p_import = sub.add_parser("import", help="Parse + build graph; optionally MERGE to Neo4j.")
    p_import.add_argument("path", help="Requirements file, or '-' for stdin.")
    p_import.add_argument("--dataset-tag", required=True, help="Coexistence tag (non-empty).")
    p_import.add_argument("--format", default="auto", help="auto|text|md|csv (default auto).")
    p_import.add_argument("--to-neo4j", action="store_true", help="MERGE into the live graph.")
    p_import.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_import.set_defaults(func=cmd_import)

    # comply
    p_comply = sub.add_parser("comply", help="Run the 15 codified objectives.")
    p_comply.add_argument(
        "--dataset", default="cva6", choices=["cva6", "uav"], help="Dataset label (default cva6)."
    )
    backend = p_comply.add_mutually_exclusive_group()
    backend.add_argument("--memory", action="store_true", help="In-memory runner (default).")
    backend.add_argument("--neo4j", action="store_true", help="Run against live Neo4j.")
    p_comply.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_comply.set_defaults(func=cmd_comply)

    # graph
    p_graph = sub.add_parser("graph", help="Named graph queries or read-only Cypher.")
    p_graph.add_argument(
        "named", nargs="?", default=None, help="Named query: q6 | q8 | q14."
    )
    p_graph.add_argument("--cypher", default=None, help="Raw read-only Cypher (Neo4j).")
    p_graph.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_graph.set_defaults(func=cmd_graph)

    # extract
    p_extract = sub.add_parser("extract", help="LLM-propose edges to a review queue ([llm] extra).")
    p_extract.add_argument("path", help="Requirements file, or '-' for stdin.")
    p_extract.add_argument("--queue", required=True, help="Review-queue JSON (created/extended).")
    p_extract.add_argument(
        "--provider", default="anthropic", choices=["anthropic", "mock"], help="Model provider."
    )
    p_extract.add_argument("--model", default=None, help="Model id (anthropic provider).")
    p_extract.add_argument("--format", default="auto", help="auto|text|md|csv (default auto).")
    p_extract.set_defaults(func=cmd_extract)

    # review
    p_review = sub.add_parser("review", help="Review queued edges (accept/reject/export/merge).")
    p_review.add_argument("queue", help="Review-queue JSON file.")
    p_review.add_argument(
        "action",
        choices=["list", "accept", "reject", "export", "merge-to-neo4j"],
        help="Review action.",
    )
    p_review.set_defaults(func=None)  # handled specially (needs extra args)

    # taxonomy (validate | stats) — stdlib-only checkability taxonomy
    p_tax = sub.add_parser("taxonomy", help="Checkability taxonomy: validate | stats.")
    tax_sub = p_tax.add_subparsers(dest="tax_command", required=True)

    p_tax_validate = tax_sub.add_parser("validate", help="Validate the taxonomy CSV.")
    p_tax_validate.add_argument("--path", default=None, help="Taxonomy CSV path (default: auto).")
    p_tax_validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_tax_validate.set_defaults(func=cmd_taxonomy_validate)

    p_tax_stats = tax_sub.add_parser("stats", help="Counts per standard/zone/class/template.")
    p_tax_stats.add_argument("--path", default=None, help="Taxonomy CSV path (default: auto).")
    p_tax_stats.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_tax_stats.set_defaults(func=cmd_taxonomy_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    # ``review`` forwards trailing args (ids / out_file) to the existing CLI.
    args, extra = parser.parse_known_args(argv)

    if args.command == "review":
        return cmd_review(args, extra)

    if extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
