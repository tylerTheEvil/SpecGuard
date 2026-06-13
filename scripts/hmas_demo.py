"""Demo: HMAS Coordinator dispatching CVA6 through all three agents.

Demonstrates dissertation novelty #1 (Hierarchical Multi-Agent System) at the
*skeleton* level: a deterministic Coordinator registers the Quality,
Formalization, and Traceability agents, dispatches the 64 CVA6 requirements
through them in sequence (Layer 1 -> 2 -> 3), and merges their uniform reports
into one combined ``AssessmentReport``.

Run modes:

    python scripts/hmas_demo.py             # no LLM (fully deterministic)
    python scripts/hmas_demo.py --mock-llm  # attach a heterogeneous MockProvider
                                            # per agent role to exercise the
                                            # augmentative LLM-annotation path

This is interface validation, not a multi-agent runtime. Polyglot persistence
and async orchestration remain future work. The ``--mock-llm`` path uses
``specguard.llm.MockProvider`` so it needs no API key and no ``anthropic``
package; the deterministic payload is identical with or without it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from specguard.agents import Coordinator
from specguard.data.cva6_requirements import get_all_requirements

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "hmas_demo_run.json"


def build_mock_providers() -> dict:
    """One distinct MockProvider per agent role (heterogeneous-models evidence).

    Each carries a different canned annotation, so the merged report shows three
    different providers actually being used — the "heterogeneous models per
    agent role with BYOM" claim from architecture.md, made observable.
    """
    from specguard.llm.mock_provider import MockProvider

    return {
        "quality": MockProvider(default="[mock-quality-model] Most requirements "
                                "pass; a few placeholders/vague terms drive the "
                                "WARN/FAIL cases."),
        "formalization": MockProvider(default="[mock-graph-model] The graph is "
                                      "dominated by Requirement->Component "
                                      "mentions; a handful of cross-cutting reqs."),
        "traceability": MockProvider(default="[mock-compliance-model] Majority of "
                                     "objectives pass; violations concentrate in "
                                     "traceability and verification objectives."),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="attach a heterogeneous MockProvider per agent role",
    )
    args = parser.parse_args()

    requirements = get_all_requirements()

    if args.mock_llm:
        coord = Coordinator.with_default_agents(providers=build_mock_providers())
    else:
        coord = Coordinator.with_default_agents()

    report = coord.dispatch(requirements)

    print("=" * 70)
    print("SpecGuard HMAS Skeleton Demo")
    print("Coordinator over Quality / Formalization / Traceability agents")
    print("(interface validation for novelty #1 — not a multi-agent runtime)")
    print("=" * 70)
    print()
    print(report.summary())

    if args.mock_llm:
        print("LLM annotations (augmentative — did NOT change any result):")
        for name in report.dispatch_order:
            note = report.reports[name].llm_annotation
            if note:
                print(f"  [{name}] {note}")
        print()

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = report.to_dict()
    out["_meta"] = {
        "demo": "hmas_demo",
        "mock_llm": args.mock_llm,
        "requirements_count": len(requirements),
        "note": "HMAS skeleton (interface validation). Deterministic; "
        "polyglot persistence and async orchestration are future work.",
    }
    RESULTS_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote combined report to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
