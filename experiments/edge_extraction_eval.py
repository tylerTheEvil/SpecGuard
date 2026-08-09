"""Edge-extraction validation experiment (Phase 3b).

Runs LLM-assisted edge extraction *blind* over the 64 CVA6 requirements and
compares the proposals — **pre-review**, since this measures the model, not the
human gate — against the hand-built CVA6 graph relationships from
``specguard.graph.builder``. Reports precision/recall per edge type and writes
``results/edge_extraction_eval.json``.

Ground truth: the deterministic builder produces ``MENTIONS`` edges
(requirement -> component, 75) and ``REFERS_TO`` edges (requirement -> standard,
21) via dictionary matching against ``KNOWN_COMPONENTS`` / ``KNOWN_STANDARDS``,
and carries a hand-built ``DERIVES_FROM`` set (3 pairs — see
``HAND_BUILT_DERIVES_FROM`` in ``specguard.graph.builder`` for the annotation
decision record; illustrative, not statistically meaningful, since CVA6 is
structurally flat). All three are scored per type; MENTIONS and REFERS_TO share
the dictionary-surrogate circularity caveat. ``MITIGATES`` has no hand-built
ground truth, so we report proposal counts only and a null recall — honestly
labelled, never silently scored against an empty set.

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
from specguard.extraction.extractor import (
    _RESPONSE_SCHEMA,
    _SYSTEM_PROMPT,
    EdgeType,
    _build_prompt,
    _validate_proposals,
    extract_edges,
)
from specguard.graph.builder import (
    KNOWN_COMPONENTS,
    KNOWN_STANDARDS,
    build_graph,
)
from specguard.llm.provider import complete_structured

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "edge_extraction_eval.json"

# Canonical guard-rejection reasons, mirroring the strings emitted by
# ``extractor._validate_proposals`` (the single place proposals are rejected).
# Used to zero-fill the per-reason breakdown so "this guard fired zero times"
# is a measured statement, not an absence of data. A regression test pushes a
# bad proposal through each rejection path and asserts the emitted reason is
# in this tuple, so a renamed/added reason fails loudly instead of silently
# landing outside the breakdown.
GUARD_REJECTION_REASONS = (
    "non-object edge",
    "unknown edge_type",
    "missing target_entity",
    "empty evidence_span",
    "fabricated evidence_span",
    "target not in inventory",
    "evidence does not name target",
)


def _rejection_summary(results) -> tuple[dict, list[dict]]:
    """Aggregate per-reason rejection counts + a stable, auditable log.

    Returns ``(guard_rejections, rejected_log)`` where ``guard_rejections``
    is ``{"total": N, "by_reason": {reason: count, ...}}`` (every canonical
    reason present, zero-filled) and ``rejected_log`` serializes each
    rejected proposal with its reason — sorted for stable artifact diffs,
    mirroring the pair-level ``_edge_log`` philosophy. Reasons outside the
    canonical tuple are still counted (never dropped) so the total always
    equals the sum of ``by_reason``.
    """
    by_reason: dict[str, int] = dict.fromkeys(GUARD_REJECTION_REASONS, 0)
    log: list[dict] = []
    for res in results:
        for entry in res.rejected:
            reason = entry.get("reason", "unknown")
            by_reason[reason] = by_reason.get(reason, 0) + 1
            raw = entry.get("raw")
            log.append(
                {
                    "requirement_id": res.requirement_id,
                    "reason": reason,
                    "proposal": raw if isinstance(raw, dict) else {"raw": repr(raw)},
                }
            )
    log.sort(
        key=lambda e: (
            e["reason"],
            e["requirement_id"],
            str(e["proposal"].get("target_entity", "")),
        )
    )
    return {"total": sum(by_reason.values()), "by_reason": by_reason}, log

# ---------------------------------------------------------------------------
# Prompt variants (precision/recall trade-off experiment). The evidence guard,
# scoring logic and ground truth are IDENTICAL across variants — only the
# system prompt (and, for "critique", a second same-provider pass) differ.
# ---------------------------------------------------------------------------

# The three few-shot negative examples baked into the STRICT prompt. These are
# real false positives from the committed baseline artifact
# (results/edge_extraction_eval_anthropic_opus48.json). METHODOLOGICAL GUARD:
# because they are shown verbatim in the prompt, their suppression is
# memorisation, not generalisation — the summary reports them separately
# ("in-prompt") from the remaining held-out FPs.
IN_PROMPT_FP_PAIRS: list[tuple[str, str, str]] = [
    ("MENTIONS", "GEN-10", "RVpriv"),   # cited standard/document
    ("MENTIONS", "PPA-30", "Sv32"),     # parenthetical configuration name
    ("MENTIONS", "HPM-30", "L1I"),      # context for another component
]

STRICT_SYSTEM_PROMPT = _SYSTEM_PROMPT + (
    "\n\nSTRICT CRITERIA — apply these before proposing any edge:\n"
    "MENTIONS: an entity counts as mentioned ONLY if it is a direct subject or "
    "object of the requirement's normative clause (the 'shall'/'should' "
    "statement). Do NOT propose MENTIONS edges for: parenthetical asides; "
    "cited standards or documents ([AXI], [RVpriv], [RVdbg] and similar "
    "bracketed references); or entities mentioned only as context for another "
    "component.\n"
    "Examples:\n"
    "- NOT a valid edge: GEN-10 -MENTIONS-> RVpriv, because '[RVpriv]' is a "
    "cited document reference, not a subject or object of the normative "
    "clause.\n"
    "- NOT a valid edge: PPA-30 -MENTIONS-> Sv32, because Sv32 appears only "
    "inside the configuration name 'cv32a6_imac_sv32', a parenthetical "
    "qualifier, not as the subject or object of the requirement.\n"
    "- NOT a valid edge: HPM-30 -MENTIONS-> L1I, because 'L1 I-Cache misses' "
    "names an event source listed as context for the performance counters; "
    "the requirement's normative clause is about the counters, not the "
    "cache.\n"
    "- VALID edge: L1W-100 -MENTIONS-> L1WTD, because L1WTD is the direct "
    "object of the normative clause 'A custom CSR shall allow to disable or "
    "enable L1WTD'.\n"
    "DERIVES_FROM: propose only if the child requirement textually refers to "
    "an entity the parent introduces. Shared topic or category is NOT "
    "derivation.\n"
    "- NOT a valid edge: ISA-80 -DERIVES_FROM-> ISA-10, because both concern "
    "ISA extensions (shared topic) but ISA-80's text does not refer to any "
    "entity ISA-10 introduces."
)

CRITIQUE_INSTRUCTION = (
    "Re-examine each proposal. Remove any that rest only on topical "
    "similarity, parenthetical mention, or document citation rather than a "
    "direct normative relationship. Return the filtered list in the same "
    "JSON schema."
)

PROMPT_VARIANTS = ("baseline", "strict", "critique")


def _extract_with_critique(provider, pairs, inventory):
    """Two-pass extraction: propose (baseline prompt), then self-critique.

    The evidence guard runs on the FINAL filtered list only. Returns the
    per-requirement results plus a critique log with pre/post raw proposal
    counts and the pairs the second pass removed (or, protocol-violating,
    added — a 'filtered list' should never grow, so additions are counted).
    """
    log = {
        "pre_critique_proposed": 0,
        "post_critique_proposed": 0,
        "added_by_critique": 0,
        "removed": [],
    }
    results = []
    for req_id, text in pairs:
        prompt = _build_prompt(req_id, text, inventory)
        resp1 = complete_structured(provider, prompt, _RESPONSE_SCHEMA, system=_SYSTEM_PROMPT)
        raw1 = resp1.get("edges", [])
        raw1 = [e for e in raw1 if isinstance(e, dict)] if isinstance(raw1, list) else []

        critique_prompt = (
            f"{prompt}\n\nYour previous proposals were:\n"
            f"{json.dumps({'edges': raw1}, ensure_ascii=False)}\n\n"
            f"{CRITIQUE_INSTRUCTION}"
        )
        resp2 = complete_structured(
            provider, critique_prompt, _RESPONSE_SCHEMA, system=_SYSTEM_PROMPT
        )
        raw2 = resp2.get("edges", [])
        raw2 = [e for e in raw2 if isinstance(e, dict)] if isinstance(raw2, list) else []

        log["pre_critique_proposed"] += len(raw1)
        log["post_critique_proposed"] += len(raw2)
        pre_keys = {(e.get("edge_type"), req_id, e.get("target_entity")) for e in raw1}
        post_keys = {(e.get("edge_type"), req_id, e.get("target_entity")) for e in raw2}
        for et, src, tgt in sorted(pre_keys - post_keys):
            log["removed"].append({"edge_type": et, "source_id": src, "target": tgt})
        log["added_by_critique"] += len(post_keys - pre_keys)

        results.append(_validate_proposals(req_id, text, raw2, inventory))
    return results, log


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

    For each requirement it proposes a MENTIONS edge to every known component,
    and a REFERS_TO edge to every known standard, whose token literally occurs
    in the text, quoting that token as the evidence span. This produces a
    realistic, deterministic offline run that overlaps heavily (but not
    perfectly) with ground truth for both surface edge types, so the eval
    machinery and metrics — including the first-class REFERS_TO scoring — are
    exercised end-to-end without a network call.
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
        for std in KNOWN_STANDARDS:
            if std in req.text:
                edges.append(
                    {
                        "edge_type": "REFERS_TO",
                        "target_entity": std,
                        "confidence": 0.9,
                        "evidence_span": std,
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
        return (
            f"Ollama server unreachable at {base_url} ({exc.reason}). "
            "Start it with `ollama serve`."
        )


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


def run(provider, *, provider_name: str, variant: str = "baseline") -> dict:
    reqs = get_all_requirements()
    inventory = _build_inventory()
    pairs = [(r.req_id, r.text) for r in reqs]

    critique_log = None
    if variant == "critique":
        results, critique_log = _extract_with_critique(provider, pairs, inventory)
    else:
        sp = STRICT_SYSTEM_PROMPT if variant == "strict" else None
        results = extract_edges(provider, pairs, inventory, system_prompt=sp)

    # First proposal per unique (source, target) pair; duplicates collapse so
    # the aggregate counts keep their original set semantics.
    proposals_by_type: dict[str, dict[tuple[str, str], object]] = {
        e.value: {} for e in EdgeType
    }
    guard_rejections, rejected_log = _rejection_summary(results)
    for res in results:
        for p in res.proposals:
            proposals_by_type[p.edge_type.value].setdefault(
                (p.source_id, p.target_entity), p
            )

    per_type: dict[str, dict] = {}
    # MENTIONS (components, 75) and REFERS_TO (standards, 21) are both
    # dictionary-matched surrogate references (KNOWN_COMPONENTS / KNOWN_STANDARDS
    # — the circularity disclosed for MENTIONS applies equally to REFERS_TO);
    # DERIVES_FROM (3) is hand-annotated (illustrative only, see
    # HAND_BUILT_DERIVES_FROM). All three carry a ground-truth set and are scored
    # per type — REFERS_TO as a first-class typed edge (P0.1), so standard
    # citations are scored directly instead of via the combined-taxonomy rescore.
    for et in ("MENTIONS", "REFERS_TO", "DERIVES_FROM"):
        truth = _ground_truth(et)
        per_type[et] = {
            "proposed": len(proposals_by_type[et]),
            "ground_truth": len(truth),
            **_score(set(proposals_by_type[et]), truth),
            "edges": _edge_log(et, proposals_by_type[et], truth),
        }
    per_type["REFERS_TO"]["note"] = (
        "standards reference (KNOWN_STANDARDS dictionary matcher, 21 edges); "
        "dictionary-matched surrogate — same circularity caveat as MENTIONS"
    )
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

    config = _run_config(provider, provider_name)
    config["prompt_variant"] = variant
    report = {
        "provider": provider_name,
        # The model the provider will actually call, never the raw CLI arg
        # (which is null on the Anthropic default path).
        "model": getattr(provider, "model", None),
        "config": config,
        "requirements_evaluated": len(reqs),
        # Structured per-reason breakdown (Section V.D). The old scalar is
        # kept as a back-compat alias for downstream readers of prior
        # artifacts; both always agree.
        "guard_rejections": guard_rejections,
        "evidence_guard_rejections": guard_rejections["total"],
        "rejected_proposals": rejected_log,
        "per_edge_type": per_type,
    }
    if critique_log is not None:
        # Annotate removals with ground-truth membership so recall damage
        # attributable to the critique pass is visible without re-deriving.
        for entry in critique_log["removed"]:
            et = entry["edge_type"]
            if et in ("MENTIONS", "REFERS_TO", "DERIVES_FROM"):
                entry["in_ground_truth"] = (
                    entry["source_id"],
                    entry["target"],
                ) in _ground_truth(et)
            else:
                entry["in_ground_truth"] = None
        report["critique"] = critique_log
    return report


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
    parser.add_argument(
        "--prompt-variant",
        choices=PROMPT_VARIANTS,
        default="baseline",
        help="System-prompt variant: baseline (control), strict (tightened "
        "definitions + few-shot negatives), critique (two-pass self-filter). "
        "Guard, scoring and ground truth are identical across variants.",
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

    report = run(provider, provider_name=args.provider, variant=args.prompt_variant)

    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print("=" * 70)
    print(
        f"EDGE-EXTRACTION EVAL  (provider={report['provider']} "
        f"model={report['model']} variant={args.prompt_variant})"
    )
    print("=" * 70)
    if "critique" in report:
        c = report["critique"]
        print(
            f"Critique pass: {c['pre_critique_proposed']} -> "
            f"{c['post_critique_proposed']} proposals "
            f"({len(c['removed'])} unique pairs removed, "
            f"{c['added_by_critique']} added)"
        )
    print(f"Requirements evaluated : {report['requirements_evaluated']}")
    print(f"Guard rejections       : {report['guard_rejections']['total']}")
    for reason, count in report["guard_rejections"]["by_reason"].items():
        if count:
            print(f"  {reason}: {count}")
    for et in ("MENTIONS", "REFERS_TO", "DERIVES_FROM"):
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
