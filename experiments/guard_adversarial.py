"""Adversarial stress tests and log replay for the deterministic proposal guards.

Deterministic, offline, no LLM calls. Two parts:

1. **Adversarial cases** — hand-constructed proposals over real CVA6
   requirements, fed through the production guard function
   :func:`specguard.extraction.extractor._validate_proposals` unchanged. Each
   case records the verdict *by design* (what the guard is specified to do) and
   the observed verdict, plus the verdict of an illustrative *normalised*
   provenance variant (NFC + case folding + whitespace canonicalisation, with
   source character offsets retained for audit). The variant lives only in this
   script; the production guard is not modified.

2. **Log replay** — every logged post-parse proposal from the six live runs
   (3x claude-opus-4-8, 3x gemma4) is re-fed through the same guard function to
   check that each logged verdict is reproduced exactly, and through the
   normalised variant to count verdict changes.

Output: ``results/guard_adversarial.json``.
"""

from __future__ import annotations

import json
import os
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from specguard.data.cva6_requirements import get_all_requirements
from specguard.extraction.extractor import _validate_proposals
from specguard.graph.builder import KNOWN_COMPONENTS, KNOWN_STANDARDS

ROOT = Path(__file__).resolve().parents[1]
RUN_FILES = [
    "results/edge_extraction_eval_anthropic_opus48.json",
    "results/variance_runs/anthropic_opus48_run2.json",
    "results/variance_runs/anthropic_opus48_run3.json",
    "results/edge_extraction_eval_ollama_gemma4.json",
    "results/variance_runs/ollama_gemma4_run2.json",
    "results/variance_runs/ollama_gemma4_run3.json",
]

REQS = {r.req_id: r.text for r in get_all_requirements()}
INVENTORY = {
    "components": list(KNOWN_COMPONENTS.keys()),
    "standards": list(KNOWN_STANDARDS.keys()),
    "requirements": list(REQS.keys()),
}


# --------------------------------------------------------------------------
# Illustrative normalised provenance check (NOT the production guard)
# --------------------------------------------------------------------------
def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """NFC + casefold + collapse whitespace; map each output char to a source offset."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFC", ch).casefold():
            if c.isspace():
                if prev_space:
                    continue
                c, prev_space = " ", True
            else:
                prev_space = False
            out.append(c)
            idx.append(i)
    return "".join(out).strip(), idx


def normalised_span_offsets(span: str, text: str) -> tuple[int, int] | None:
    """Return (start, end) source offsets of ``span`` under normalisation, else None."""
    nspan, _ = _normalise_with_map(span)
    ntext, idx = _normalise_with_map(text)
    # account for a leading space stripped from ntext
    lead = len(_normalise_with_map(text)[0]) - len(ntext)
    pos = ntext.find(nspan) if nspan else -1
    if pos < 0:
        return None
    start = idx[pos + lead] if pos + lead < len(idx) else idx[-1]
    end = idx[min(pos + lead + len(nspan) - 1, len(idx) - 1)] + 1
    return start, end


def _verdict(req_id: str, raw: dict) -> dict:
    res = _validate_proposals(req_id, REQS[req_id], [raw], INVENTORY)
    if res.proposals:
        p = res.proposals[0]
        flag = p.evidence_names_target
        return {"verdict": "admit", "names_target": flag}
    return {"verdict": "reject", "reason": res.rejected[0]["reason"]}


def P(edge_type, target, span, confidence=0.9):
    return {"edge_type": edge_type, "target_entity": target,
            "confidence": confidence, "evidence_span": span}


# (id, category, source req, raw proposal, verdict by design, note)
CASES = [
    ("C01", "control", "HPM-10", P("MENTIONS", "CVA6", "CVA6 shall implement"), "admit", "genuine span naming its target"),
    ("PR1", "provenance", "HPM-10", P("MENTIONS", "CVA6", "CVA6 shall implement a lockstep core"), "reject", "fabricated span"),
    ("PR2", "provenance", "HPM-10", P("MENTIONS", "L1I", "L1 I-Cache misses"), "reject", "genuine span copied from another requirement (HPM-30)"),
    ("PR3", "provenance", "HPM-10", P("MENTIONS", "CVA6", "cva6 shall implement"), "admit", "case variant of a genuine span"),
    ("PR4", "provenance", "HPM-10", P("MENTIONS", "CVA6", "CVA6  shall implement"), "admit", "whitespace variant (double space)"),
    ("PR5", "provenance", "HPM-10", P("MENTIONS", "CVA6", "CVA6 shall\nimplement"), "admit", "line-break variant"),
    ("PR6", "provenance", "HPM-10", P("MENTIONS", "CVA6", "CVA6 shall implement the 64‑bit"), "admit", "Unicode non-breaking hyphen instead of '-'"),
    ("PR7", "provenance", "HPM-10", P("MENTIONS", "CSR", "the"), "admit+flag", "short generic fragment (named-entity edge)"),
    ("PR8", "provenance", "HPM-10", P("REFERS_TO", "RVpriv", "a"), "admit+flag", "single-character span"),
    ("PR9", "provenance", "HPM-30", P("DERIVES_FROM", "HPM-20", "the"), "admit (unflagged)", "short generic fragment on DERIVES_FROM"),
    ("PR10", "provenance", "HPM-10", P("MENTIONS", "FPU", "standard performance counters"), "admit+flag", "genuine but irrelevant span"),
    ("BD1", "binding", "ISA-90", P("MENTIONS", "CSR", "Zicsr extension"), "admit+flag", "target id occurs only inside another word"),
    ("BD2", "binding", "MEM-10", P("REFERS_TO", "AXI", "AXI5 specification"), "admit+flag", "span names a different standard (AXI5) containing the id"),
    ("IN1", "inventory", "HPM-10", P("MENTIONS", "NOT_IN_INVENTORY", "CVA6 shall implement"), "reject", "sentinel target"),
    ("IN2", "inventory", "HPM-30", P("MENTIONS", "L1D", "L1 D-Cache misses"), "reject", "plausible entity absent from inventory"),
    ("IN3", "inventory", "HPM-10", P("MENTIONS", "cva6", "CVA6 shall implement"), "reject", "case variant of a valid target id"),
    ("TY1", "type", "HPM-10", P("MENTIONS", "RVpriv", "[RVpriv]"), "reject", "standard under MENTIONS"),
    ("TY2", "type", "HPM-10", P("REFERS_TO", "CVA6", "CVA6 shall implement"), "reject", "component under REFERS_TO"),
    ("TY3", "type", "HPM-30", P("DERIVES_FROM", "CSR", "Each of the six generic performance counters"), "reject", "component under DERIVES_FROM"),
    ("DR1", "derivation", "HPM-30", P("DERIVES_FROM", "HPM-30", "Each of the six generic performance counters"), "reject", "self-derivation"),
    ("DR2", "derivation", "HPM-20", P("DERIVES_FROM", "HPM-30", "six generic 64-bit performance counters"), "human", "reversed direction (parent -> child)"),
    ("DR3", "derivation", "ISA-80", P("DERIVES_FROM", "ISA-10", "CVA6 shall support"), "human", "topical similarity only (annotation-rejected kind)"),
    ("MI1", "mitigates", "FET-20", P("MITIGATES", "FET-10", "FENCE.T should be available"), "per Table I: reject", "MITIGATES targeting a requirement"),
    ("SC1", "schema", "HPM-10", P("IMPLEMENTS", "CVA6", "CVA6 shall implement"), "reject", "unknown edge type"),
    ("SC2", "schema", "HPM-10", P("MENTIONS", "CVA6", "   "), "reject", "whitespace-only span"),
]


def run_cases() -> list[dict]:
    rows = []
    for cid, cat, req, raw, by_design, note in CASES:
        obs = _verdict(req, raw)
        norm = normalised_span_offsets(raw["evidence_span"], REQS[req]) if raw["evidence_span"].strip() else None
        rows.append({
            "id": cid, "category": cat, "source": req, "proposal": raw,
            "desired": by_design, "observed": obs, "note": note,
            "strict_span_found": raw["evidence_span"] in REQS[req],
            "normalised_span_offsets": list(norm) if norm else None,
        })
    return rows


# --------------------------------------------------------------------------
# Log replay
# --------------------------------------------------------------------------
def replay_logs() -> dict:
    out = {"runs": [], "totals": {}}
    tot = {"proposals": 0, "reproduced": 0, "mismatch": 0, "normalised_changes": 0}
    shortest: list[tuple[int, str, str, str]] = []
    for f in RUN_FILES:
        d = json.loads((ROOT / f).read_text())
        items = []
        for et, block in d["per_edge_type"].items():
            for e in block.get("edges", []):
                if e.get("verdict") in ("TP", "FP") and e.get("evidence_span") is not None:
                    raw = P(e["edge_type"], e["target"], e["evidence_span"], e.get("confidence") or 0.0)
                    items.append((e["source_id"], raw, {"verdict": "admit", "names_target": e.get("evidence_names_target")}))
        for r in d.get("rejected_proposals", []):
            items.append((r["requirement_id"], r["proposal"], {"verdict": "reject", "reason": r["reason"]}))
        n_ok = n_bad = n_norm = 0
        for req, raw, logged in items:
            obs = _verdict(req, raw)
            same = obs["verdict"] == logged["verdict"] and (
                obs.get("names_target") == logged.get("names_target") if obs["verdict"] == "admit"
                else obs.get("reason") == logged.get("reason"))
            n_ok += same
            n_bad += not same
            strict = raw["evidence_span"] in REQS[req]
            norm = normalised_span_offsets(raw["evidence_span"], REQS[req]) is not None
            n_norm += strict != norm
            if obs["verdict"] == "admit":
                shortest.append((len(raw["evidence_span"]), raw["evidence_span"], raw["edge_type"], req))
        out["runs"].append({"file": f, "provider": d["provider"], "proposals": len(items),
                            "reproduced": n_ok, "mismatch": n_bad, "normalised_changes": n_norm})
        tot["proposals"] += len(items); tot["reproduced"] += n_ok
        tot["mismatch"] += n_bad; tot["normalised_changes"] += n_norm
    shortest.sort()
    out["totals"] = tot
    out["shortest_admitted_spans"] = [
        {"len": n, "span": s, "edge_type": et, "source": req} for n, s, et, req in shortest[:8]]
    return out


def main() -> int:
    result = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "guard_function": "specguard.extraction.extractor._validate_proposals",
        "guard_code_ref": os.environ.get("GUARD_CODE_REF", "working tree"),
        "cases": run_cases(),
        "log_replay": replay_logs(),
    }
    path = ROOT / "results" / "guard_adversarial.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for r in result["cases"]:
        o = r["observed"]
        obs = o["verdict"] + (f" ({o['reason']})" if o["verdict"] == "reject" else f" names_target={o['names_target']}")
        print(f"{r['id']:5} {r['category']:11} desired={r['desired']:20} observed={obs:55} norm={'found' if r['normalised_span_offsets'] else '-'}  | {r['note']}")
    print(json.dumps(result["log_replay"]["totals"]), result["log_replay"]["shortest_admitted_spans"][:5])
    for run in result["log_replay"]["runs"]:
        print(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
