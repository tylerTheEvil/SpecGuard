"""Re-score committed MENTIONS pair-level logs under two target taxonomies.

Pure re-scoring — no LLM calls. Motivation: the extraction system prompt
tells the model MENTIONS covers components AND standards, but the builder
reference contains only Component-targeted MENTIONS edges (standards live in
REFERS_TO, ``builder.py`` — ``KNOWN_STANDARDS`` feeds ``extract_standards``).
Scoring against the component-only reference therefore penalises
instruction-compliant standard mentions as FPs. This script reports both
readings for every artifact that carries pair-level logs:

* ``component_only`` — reference = builder MENTIONS pairs (current scoring).
  Recomputed from the pair logs and ASSERTED equal to the stored aggregates,
  validating the re-scoring machinery.
* ``combined`` — reference = builder MENTIONS ∪ builder REFERS_TO pairs.
  A proposal targeting a standard is a TP iff the builder has a REFERS_TO
  edge for that (requirement, standard) pair. Recall is over the full union.

FP breakdown classifies each false positive's target via the builder's own
lexicons: component (``KNOWN_COMPONENTS``), standard (``KNOWN_STANDARDS``),
else out-of-inventory (the extractor's evidence guard checks spans, not
target membership, so out-of-inventory targets can and do occur).

Scope honesty: runs that predate pair-level logging (the six aggregate-only
entries in ``results/edge_extraction_variance.json``) cannot be re-scored —
their per-pair proposals were never recorded. They are listed as
``not_rescorable``. DERIVES_FROM is unaffected by this taxonomy question and
is not re-scored. The surrogate-ground-truth circularity caveat applies to
BOTH taxonomies: the reference is builder output either way.

Usage:
    python experiments/retaxonomy_rescore.py
"""

from __future__ import annotations

import json
from pathlib import Path

from specguard.data.cva6_requirements import get_all_requirements
from specguard.graph.builder import (
    KNOWN_COMPONENTS,
    KNOWN_STANDARDS,
    build_graph,
)

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

RESCORABLE = [
    RESULTS / "edge_extraction_eval.json",
    RESULTS / "edge_extraction_eval_anthropic_opus48.json",
    RESULTS / "edge_extraction_eval_ollama_gemma4.json",
    *sorted((RESULTS / "prompt_variants").glob("edge_extraction_eval_*.json")),
]

NOT_RESCORABLE_NOTE = (
    "The six runs aggregated in results/edge_extraction_variance.json "
    "(3 anthropic + 3 ollama, 2026-06/08) predate pair-level logging and "
    "carry aggregate counts only — combined-taxonomy re-scoring is "
    "impossible for them."
)


def _references() -> tuple[set, set]:
    graph = build_graph(get_all_requirements())
    mentions = {
        (r.from_id, r.to_id) for r in graph.relationships if r.rel_type == "MENTIONS"
    }
    refers = {
        (r.from_id, r.to_id) for r in graph.relationships if r.rel_type == "REFERS_TO"
    }
    return mentions, refers


def _classify(target: str) -> str:
    if target in KNOWN_COMPONENTS:
        return "component"
    if target in KNOWN_STANDARDS:
        return "standard"
    return "out_of_inventory"


def _score(proposals: set, reference: set) -> dict:
    tp = proposals & reference
    fp = proposals - reference
    fn = reference - proposals
    return {
        "true_positives": len(tp),
        "false_positives": len(fp),
        "false_negatives": len(fn),
        "precision": len(tp) / len(proposals) if proposals else None,
        "recall": len(tp) / len(reference) if reference else None,
        "fp_breakdown": {
            "component": sum(1 for _, t in fp if _classify(t) == "component"),
            "standard": sum(1 for _, t in fp if _classify(t) == "standard"),
            "out_of_inventory": sum(
                1 for _, t in fp if _classify(t) == "out_of_inventory"
            ),
        },
    }


def rescore(path: Path, mentions_ref: set, combined_ref: set) -> dict:
    data = json.loads(path.read_text())
    m = data["per_edge_type"]["MENTIONS"]
    if "edges" not in m:
        raise ValueError(f"{path.name} has no pair-level log")

    proposals = {
        (e["source_id"], e["target"])
        for e in m["edges"]
        if e["verdict"] in ("TP", "FP")
    }

    comp = _score(proposals, mentions_ref)
    # Validation: the recomputed component-only numbers must reproduce the
    # stored aggregates exactly, or the re-scoring machinery is wrong.
    for ours, theirs in (
        (comp["true_positives"], m["true_positives"]),
        (comp["false_positives"], m["false_positives"]),
        (comp["false_negatives"], m["false_negatives"]),
    ):
        if ours != theirs:
            raise AssertionError(
                f"{path.name}: recomputed component-only scores {comp} "
                f"do not reproduce stored aggregates — re-scoring is invalid"
            )

    return {
        "file": str(path.relative_to(ROOT)),
        "provider": data["provider"],
        "model": data["model"],
        "prompt_variant": data["config"].get("prompt_variant", "baseline"),
        "proposed": len(proposals),
        "component_only": comp,
        "combined": _score(proposals, combined_ref),
    }


def main() -> int:
    mentions_ref, refers_ref = _references()
    combined_ref = mentions_ref | refers_ref

    runs = [rescore(p, mentions_ref, combined_ref) for p in RESCORABLE]

    out = {
        "_note": (
            "MENTIONS re-scored under two target taxonomies from committed "
            "pair-level logs; no LLM runs. component_only: reference = "
            f"builder MENTIONS ({len(mentions_ref)} pairs, KNOWN_COMPONENTS "
            "dictionary). combined: reference = builder MENTIONS UNION "
            f"builder REFERS_TO ({len(combined_ref)} pairs; standards from "
            "KNOWN_STANDARDS, builder.py). FP targets classified by the same "
            "lexicons; neither taxonomy escapes the surrogate-ground-truth "
            "circularity (the reference is builder output in both). "
            "Component-only scores are validated against the stored "
            "aggregates of every artifact. " + NOT_RESCORABLE_NOTE
        ),
        "reference_sizes": {
            "mentions": len(mentions_ref),
            "refers_to": len(refers_ref),
            "combined": len(combined_ref),
        },
        "runs": runs,
        "not_rescorable": NOT_RESCORABLE_NOTE,
    }
    path = RESULTS / "retaxonomy_rescore.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {path}")
    print(f"reference sizes: {out['reference_sizes']}")
    hdr = f"{'run':52s} {'P(comp)':>8s} {'R(comp)':>8s} {'P(comb)':>8s} {'R(comb)':>8s}  FP comp/std/oov"
    print(hdr)
    for r in runs:
        c, k = r["component_only"], r["combined"]
        b = k["fp_breakdown"]
        name = f"{r['provider']}/{r['prompt_variant']}/{Path(r['file']).stem[-20:]}"
        print(
            f"{name:52s} {c['precision']:.3f}    {c['recall']:.3f}    "
            f"{k['precision']:.3f}    {k['recall']:.3f}    "
            f"{b['component']}/{b['standard']}/{b['out_of_inventory']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
