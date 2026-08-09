"""Independent human-annotated evaluation subset for edge extraction.

Why this module exists (the circularity it removes)
---------------------------------------------------
Extraction quality in ``experiments/edge_extraction_eval.py`` is scored against
the deterministic ``build_graph`` output. For ``MENTIONS`` / ``REFERS_TO`` that
reference is **dictionary matching over the requirement text** (``KNOWN_COMPONENTS``
/ ``KNOWN_STANDARDS``). Scoring an extractor against a dictionary reference is a
*surrogate*: it rewards reproducing the dictionary, not recovering the true
edges a human would annotate. This is the reviewer's circularity objection, and
it is the direct analogue of the seeded-fault issue already documented for the
smell detector (see ``experiments/independent_lexicon.py``).

This module builds the missing artifact: a **human-annotated gold subset**.

Honest boundary — what this code does and does NOT do
-----------------------------------------------------
The gold labels must be authored by a human reading each requirement. This code
does **not** fabricate them: :func:`build_template` emits an *empty* annotation
template (``edges: []`` per item, ``status: TEMPLATE_UNFILLED``) for a human to
fill. Anything this module could auto-generate as "gold" would just be another
machine-derived reference — the very thing under test. What it provides instead:

* a deterministic, stratified **subset sampler** (reproducible, no RNG);
* an empty **annotation template** and a written **protocol**
  (``experiments/human_eval/annotation_guidelines.md``);
* an assistive **candidate pool** with per-candidate provenance — kept in a
  *separate* file from the gold, explicitly "candidates for human triage, not
  labels", so the annotator triages rather than reads from scratch without the
  dictionary's answer being presented as truth;
* a **scorer** that computes P/R/F1 per edge type against the *human* reference;
* a **surrogate-gap** report quantifying how far the dictionary reference is from
  the human one (dictionary misses vs. dictionary false alarms), and an
  **independence check** that refuses a gold set byte-identical to builder output.

Stdlib-only, consistent with the experiment-module conventions.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from specguard.data.cva6_requirements import Requirement, get_all_requirements
from specguard.graph.builder import (
    KNOWN_COMPONENTS,
    KNOWN_STANDARDS,
    build_graph,
    extract_components,
    extract_standards,
)

ROOT = Path(__file__).resolve().parent.parent
HUMAN_EVAL_DIR = ROOT / "experiments" / "human_eval"
TEMPLATE_PATH = HUMAN_EVAL_DIR / "annotation_template.json"
CANDIDATE_POOL_PATH = HUMAN_EVAL_DIR / "candidate_pool.json"

# Edge types this eval covers. MITIGATES is excluded: the builder emits none, so
# there is no subset to sample and no surrogate to compare against.
EVAL_EDGE_TYPES = ("MENTIONS", "REFERS_TO", "DERIVES_FROM")

DEFAULT_SUBSET_SIZE = 20

# Acronym / identifier surface pattern for the independent candidate source: a
# capitalised token, optionally with internal ., _, - or digits (CVA6, L1WTD,
# FENCE.T, Sv39). Deliberately dictionary-agnostic so it can surface entities
# the KNOWN_* lexicons lack.
_IDENTIFIER_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[._-][A-Za-z0-9]+)*\b")

# A small, generic stoplist of function/determiner words that get capitalised at
# sentence start. Dropping them cuts obvious noise from the surface candidate
# source without a dictionary. Kept deliberately generic (not tuned to the CVA6
# text): the surface source still over-generates by design — it favours flagging
# possible missing entities over precision, and the human triages the rest.
_SURFACE_STOPWORDS = frozenset(
    {
        "the", "a", "an", "this", "that", "these", "those", "each", "all", "any",
        "some", "no", "not", "when", "while", "if", "where", "for", "in", "on",
        "at", "by", "to", "of", "as", "it", "its", "their", "both", "either",
        "neither", "such", "and", "or", "but", "however", "additionally", "note",
        "otherwise", "only", "shall", "should", "may", "must", "will", "can",
    }
)


# ---------------------------------------------------------------------------
# Deterministic stratified subset sampling
# ---------------------------------------------------------------------------


def _hamilton_allocation(counts: dict[str, int], size: int) -> dict[str, int]:
    """Largest-remainder (Hamilton) apportionment of ``size`` across categories.

    Deterministic and dependency-free. Ties on the fractional remainder are
    broken by category name so the result is stable across runs and machines.
    """
    total = sum(counts.values())
    if total == 0 or size <= 0:
        return dict.fromkeys(counts, 0)
    size = min(size, total)
    exact = {c: n * size / total for c, n in counts.items()}
    alloc = {c: int(v) for c, v in exact.items()}
    seats_left = size - sum(alloc.values())
    # Distribute remaining seats to the largest fractional remainders.
    order = sorted(
        counts, key=lambda c: (-(exact[c] - alloc[c]), c)
    )
    for c in order[:seats_left]:
        alloc[c] += 1
    return alloc


def _even_indices(count: int, k: int) -> list[int]:
    """``k`` evenly-spaced indices in ``range(count)`` (endpoints included)."""
    if k <= 0 or count <= 0:
        return []
    if k == 1:
        return [count // 2]
    k = min(k, count)
    return sorted({round(i * (count - 1) / (k - 1)) for i in range(k)})


def sample_subset(
    reqs: list[Requirement], size: int = DEFAULT_SUBSET_SIZE
) -> list[Requirement]:
    """Deterministically pick a category-stratified subset of requirements.

    Stratification uses Hamilton apportionment over categories; within each
    category the picks are evenly spaced by sorted ``req_id``. No randomness, so
    two runs (or two machines) yield the same subset — a property the tests pin.
    """
    by_cat: dict[str, list[Requirement]] = {}
    for req in reqs:
        by_cat.setdefault(req.category, []).append(req)
    counts = {c: len(v) for c, v in by_cat.items()}
    alloc = _hamilton_allocation(counts, size)

    picked: list[Requirement] = []
    for cat in sorted(by_cat):
        members = sorted(by_cat[cat], key=lambda r: r.req_id)
        for idx in _even_indices(len(members), alloc.get(cat, 0)):
            picked.append(members[idx])
    return sorted(picked, key=lambda r: r.req_id)


# ---------------------------------------------------------------------------
# Inventory and references
# ---------------------------------------------------------------------------


def build_inventory() -> dict[str, list[str]]:
    """Allowed target vocabulary (ids only — NOT reference edges)."""
    reqs = get_all_requirements()
    return {
        "components": sorted(KNOWN_COMPONENTS),
        "standards": sorted(KNOWN_STANDARDS),
        "requirements": [r.req_id for r in reqs],
    }


def builder_reference(subset_ids: set[str]) -> dict[str, set[tuple[str, str]]]:
    """The surrogate (dictionary) reference restricted to the subset.

    ``(source_id, target)`` pairs per evaluated edge type, taken from
    ``build_graph`` and filtered to edges whose source is in the subset.
    """
    graph = build_graph(get_all_requirements())
    ref: dict[str, set[tuple[str, str]]] = {t: set() for t in EVAL_EDGE_TYPES}
    for rel in graph.relationships:
        if rel.rel_type in ref and rel.from_id in subset_ids:
            ref[rel.rel_type].add((rel.from_id, rel.to_id))
    return ref


# ---------------------------------------------------------------------------
# Annotation template + assistive candidate pool
# ---------------------------------------------------------------------------


def build_template(subset: list[Requirement], inventory: dict[str, list[str]]) -> dict:
    """An empty, human-fillable annotation template for the subset."""
    return {
        "_meta": {
            "purpose": (
                "Independent human-annotated evaluation subset for edge "
                "extraction (MENTIONS/REFERS_TO/DERIVES_FROM)."
            ),
            "independence": (
                "Author each item's `edges` by reading its `text`, per "
                "annotation_guidelines.md. Do NOT paste build_graph output — the "
                "dictionary reference is the thing under test. The scorer refuses "
                "a gold set identical to the builder reference."
            ),
            "edge_types": list(EVAL_EDGE_TYPES),
            "subset_size": len(subset),
            "sampling": (
                "deterministic, Hamilton-stratified by category; see "
                "edge_extraction_human_eval.sample_subset"
            ),
            "inventory_note": (
                "`inventory` is the allowed target vocabulary (ids), not "
                "reference edges. Targets must come from it."
            ),
            "annotator": None,
            "annotated_utc": None,
            "status": "TEMPLATE_UNFILLED",
        },
        "inventory": inventory,
        "items": [
            {
                "req_id": r.req_id,
                "category": r.category,
                "text": r.text,
                # Human fills: list of
                # {"edge_type": "MENTIONS"|"REFERS_TO"|"DERIVES_FROM",
                #  "target": "<inventory id>", "evidence_span": "<verbatim>",
                #  "note": "<optional>"}
                "edges": [],
            }
            for r in subset
        ],
    }


def build_candidate_pool(
    subset: list[Requirement], inventory: dict[str, list[str]]
) -> dict:
    """Assistive candidates for human triage — NOT gold labels.

    Two independent sources per requirement so the annotator is not primed by
    the dictionary alone:

    * ``dict`` — builder dictionary matches (component -> MENTIONS, standard ->
      REFERS_TO). These are exactly the surrogate edges; the annotator must
      still confirm each is a real reference in context (and may reject it).
    * ``surface`` — capitalised/acronym identifiers found by a dictionary-
      agnostic regex that are NOT in the inventory. These flag possible entities
      the lexicons miss (candidate coverage gaps) for the annotator to judge.

    ``DERIVES_FROM`` has no automatable candidate source (it is a semantic
    refinement relation), so those edges are annotated from scratch.
    """
    known = set(inventory["components"]) | set(inventory["standards"]) | set(
        inventory["requirements"]
    )
    items = []
    for r in subset:
        candidates = []
        for comp in sorted(extract_components(r.text)):
            candidates.append(
                {
                    "source": "dict",
                    "edge_type_hint": "MENTIONS",
                    "target": comp,
                    "evidence_span": comp,
                }
            )
        for std in sorted(extract_standards(r.text)):
            candidates.append(
                {
                    "source": "dict",
                    "edge_type_hint": "REFERS_TO",
                    "target": std,
                    "evidence_span": std,
                }
            )
        surface_seen: set[str] = set()
        for m in _IDENTIFIER_RE.finditer(r.text):
            tok = m.group(0)
            if (
                tok in known
                or tok in surface_seen
                or len(tok) < 2
                or tok.lower() in _SURFACE_STOPWORDS
            ):
                continue
            surface_seen.add(tok)
            candidates.append(
                {
                    "source": "surface",
                    "edge_type_hint": None,
                    "target": None,
                    "surface_form": tok,
                    "evidence_span": tok,
                    "note": "identifier not in inventory — possible missing entity",
                }
            )
        items.append({"req_id": r.req_id, "candidates": candidates})
    return {
        "_meta": {
            "purpose": "Candidates for human triage. NOT gold labels.",
            "sources": {
                "dict": "builder KNOWN_COMPONENTS/KNOWN_STANDARDS matches (the surrogate)",
                "surface": "dictionary-agnostic acronym/identifier regex, inventory-absent tokens",
            },
        },
        "items": items,
    }


# ---------------------------------------------------------------------------
# Scoring against the human reference
# ---------------------------------------------------------------------------


def _prf(proposed: set[tuple[str, str]], gold: set[tuple[str, str]]) -> dict:
    tp = len(proposed & gold)
    fp = len(proposed - gold)
    fn = len(gold - proposed)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall
        else None
    )
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def load_gold(path: str | Path) -> dict:
    """Load a completed gold file, refusing an unfilled or empty template."""
    gold = json.loads(Path(path).read_text())
    meta = gold.get("_meta", {})
    if meta.get("status") == "TEMPLATE_UNFILLED":
        raise ValueError(
            f"{path}: status is TEMPLATE_UNFILLED — fill in `edges` and set "
            "_meta.status (e.g. 'ANNOTATED') and _meta.annotator before scoring."
        )
    if not any(item.get("edges") for item in gold.get("items", [])):
        raise ValueError(f"{path}: no annotated edges found — nothing to score against.")
    return gold


def gold_edges(gold: dict) -> tuple[dict[str, set[tuple[str, str]]], list[dict]]:
    """Split a gold file into scoreable pairs and coverage-gap observations.

    Returns ``(edges, out_of_inventory_observations)``. Entries with
    ``target: null`` mark entities the annotator saw in the text but could not
    map to any inventory id — the dictionary coverage gaps the guidelines
    promise to report. They must NOT become ``(req_id, None)`` gold pairs
    (which would corrupt P/R/F1 and dictionary-miss sets); each is kept as a
    distinct observation (a list, so multiple unknown entities on one
    requirement never collapse).
    """
    edges: dict[str, set[tuple[str, str]]] = {t: set() for t in EVAL_EDGE_TYPES}
    observations: list[dict] = []
    for item in gold.get("items", []):
        src = item["req_id"]
        for e in item.get("edges", []):
            et = e["edge_type"]
            if et not in edges:
                raise ValueError(f"{src}: unknown edge_type {et!r} in gold")
            if e.get("target") is None:
                observations.append(
                    {
                        "req_id": src,
                        "edge_type": et,
                        "note": e.get("note"),
                        "evidence_span": e.get("evidence_span"),
                    }
                )
                continue
            edges[et].add((src, e["target"]))
    return edges, observations


def subset_ids(gold: dict) -> set[str]:
    return {item["req_id"] for item in gold.get("items", [])}


def load_proposals(
    path: str | Path, keep_ids: set[str]
) -> dict[str, set[tuple[str, str]]]:
    """Load extractor proposals, filtered to the subset ids.

    Accepts either a flat list of ``{source_id|from_id, edge_type|rel_type,
    target|to_id}`` dicts (e.g. ``review.export_accepted_edges`` output) or a
    ``{"items": [...]}`` wrapper of the same. Only the evaluated edge types and
    the subset's source ids are kept.
    """
    raw = json.loads(Path(path).read_text())
    rows = raw["items"] if isinstance(raw, dict) and "items" in raw else raw
    props: dict[str, set[tuple[str, str]]] = {t: set() for t in EVAL_EDGE_TYPES}
    for row in rows:
        src = row.get("source_id") or row.get("from_id")
        et = row.get("edge_type") or row.get("rel_type")
        tgt = row.get("target") or row.get("target_entity") or row.get("to_id")
        if et in props and src in keep_ids and tgt is not None:
            props[et].add((src, tgt))
    return props


def independence_check(
    gold: dict[str, set[tuple[str, str]]],
    surrogate: dict[str, set[tuple[str, str]]],
    *,
    allow_identical: bool = False,
) -> dict:
    """Report gold/surrogate overlap; refuse identical sets unless overridden.

    An identical gold/surrogate set is *suspicious* — it is consistent with
    someone pasting builder output, but it does not prove copying (a careful
    annotator can legitimately agree with the dictionary everywhere on a small
    subset). Default behaviour still refuses to score, but the refusal names
    the suspicion honestly and the explicit ``allow_identical`` override
    (CLI: ``--allow-identical``) lets a user who vouches for the annotation
    proceed — with ``identical_to_surrogate: true`` recorded loudly in the
    report so the caveat travels with the numbers.
    """
    per_type = {}
    identical_all = True
    for t in EVAL_EDGE_TYPES:
        g, s = gold[t], surrogate[t]
        inter = len(g & s)
        union = len(g | s)
        per_type[t] = {
            "gold": len(g),
            "surrogate": len(s),
            "intersection": inter,
            "jaccard": (inter / union) if union else None,
            "identical": g == s,
        }
        if g != s:
            identical_all = False
    identical = identical_all and any(surrogate[t] for t in EVAL_EDGE_TYPES)
    if identical and not allow_identical:
        raise ValueError(
            "Gold edge set is identical to the builder (surrogate) reference "
            "for every edge type. Identity is SUSPICIOUS (consistent with "
            "pasted builder output) though not proof of copying — if the "
            "annotation was genuinely authored independently, re-run with "
            "--allow-identical to score anyway; the report will carry "
            "identical_to_surrogate=true as a loud caveat."
        )
    return {
        "per_type": per_type,
        "identical_to_surrogate": identical,
        "note": (
            "identical_to_surrogate=true means the gold set exactly matches "
            "the dictionary reference — suspicious but not proven copying; "
            "scored under explicit --allow-identical override."
        )
        if identical
        else None,
    }


def surrogate_gap(
    gold: dict[str, set[tuple[str, str]]],
    surrogate: dict[str, set[tuple[str, str]]],
) -> dict:
    """Quantify how far the dictionary reference is from the human one.

    Per edge type: ``dictionary_misses`` are edges the human found that the
    dictionary reference lacks (coverage gap); ``dictionary_false_alarms`` are
    dictionary edges the human rejected (context/false-match errors). This is
    the concrete, publishable measure of the circularity the surrogate hides.
    """
    gap = {}
    for t in EVAL_EDGE_TYPES:
        g, s = gold[t], surrogate[t]
        gap[t] = {
            "dictionary_misses": sorted(g - s),
            "dictionary_false_alarms": sorted(s - g),
            "n_dictionary_misses": len(g - s),
            "n_dictionary_false_alarms": len(s - g),
        }
    return gap


def score(
    gold_path: str | Path,
    proposals_path: str | Path,
    *,
    allow_identical: bool = False,
) -> dict:
    """Full scoring report: per-type P/R/F1 vs human + surrogate-gap + independence.

    ``target: null`` gold entries are excluded from all pair sets and reported
    under ``out_of_inventory_observations`` — the coverage-gap evidence the
    guidelines promise, never scoreable matches.
    """
    gold = load_gold(gold_path)
    ids = subset_ids(gold)
    g_edges, observations = gold_edges(gold)
    surrogate = builder_reference(ids)
    proposals = load_proposals(proposals_path, ids)

    independence = independence_check(
        g_edges, surrogate, allow_identical=allow_identical
    )
    return {
        "subset_size": len(ids),
        "annotator": gold.get("_meta", {}).get("annotator"),
        "per_edge_type_vs_human": {
            t: _prf(proposals[t], g_edges[t]) for t in EVAL_EDGE_TYPES
        },
        "surrogate_gap": surrogate_gap(g_edges, surrogate),
        "independence": independence,
        "out_of_inventory_observations": observations,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_sample(args: argparse.Namespace) -> int:
    reqs = get_all_requirements()
    subset = sample_subset(reqs, args.size)
    inventory = build_inventory()
    HUMAN_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(
        json.dumps(build_template(subset, inventory), indent=2, ensure_ascii=False)
        + "\n"
    )
    CANDIDATE_POOL_PATH.write_text(
        json.dumps(build_candidate_pool(subset, inventory), indent=2, ensure_ascii=False)
        + "\n"
    )
    print(f"Sampled {len(subset)} requirements (stratified, deterministic).")
    print(f"  template      -> {TEMPLATE_PATH.relative_to(ROOT)}")
    print(f"  candidate pool -> {CANDIDATE_POOL_PATH.relative_to(ROOT)}")
    print("Fill the template's `edges` per experiments/human_eval/annotation_guidelines.md.")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    report = score(args.gold, args.proposals, allow_identical=args.allow_identical)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote {args.out}")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python experiments/edge_extraction_human_eval.py",
        description="Independent human-annotated edge-extraction evaluation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sample = sub.add_parser("sample", help="Write the annotation template + candidate pool.")
    p_sample.add_argument(
        "--size", type=int, default=DEFAULT_SUBSET_SIZE, help="Subset size (default 20)."
    )
    p_sample.set_defaults(func=_cmd_sample)

    p_score = sub.add_parser(
        "score", help="Score extractor proposals against the filled human gold."
    )
    p_score.add_argument("gold", help="Path to the completed gold JSON.")
    p_score.add_argument("proposals", help="Path to extractor proposals JSON.")
    p_score.add_argument("--out", help="Optional path to write the JSON report.")
    p_score.add_argument(
        "--allow-identical",
        action="store_true",
        help=(
            "Proceed even if the gold set is identical to the builder "
            "reference (suspicious, not proven copying); the report records "
            "identical_to_surrogate=true."
        ),
    )
    p_score.set_defaults(func=_cmd_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
