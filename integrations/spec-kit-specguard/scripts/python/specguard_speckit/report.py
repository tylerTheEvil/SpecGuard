"""Report rendering: Markdown (agent / human) and JSON (CI / tools).

Output is deterministic — no timestamps, stable ordering — so the same input
yields a byte-identical report, which the tests and any audit trail rely on.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from . import __version__
from .model import Finding

VENDOR_LOCK = Path(__file__).parent / "_vendor" / "specguard_core" / "VENDOR.json"
CHECKS_DOC = Path(__file__).resolve().parents[3] / "docs" / "checks.md"


def checks_doc_hint(target) -> str:
    """Where the rule catalog lives for this install (shipped with the extension)."""
    return target.display(CHECKS_DOC) if CHECKS_DOC.is_file() else "docs/checks.md"
DISCLAIMER = (
    "Deterministic: the same input always yields this report; no model is involved in the "
    "verdict. Scores are local text heuristics, not proofs of completeness, consistency or "
    "verifiability — PASS means no deterministic finding, not a good spec."
)


def core_provenance() -> dict:
    try:
        lock = json.loads(VENDOR_LOCK.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"source_commit": None}
    return {
        "source_repository": lock.get("source_repository"),
        "source_commit": lock.get("source_commit"),
        "source_dirty": lock.get("source_dirty"),
        "files": lock.get("files", {}),
    }


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _where(f: Finding) -> str:
    parts = []
    if f.line:
        parts.append(f"L{f.line}")
    if f.ref:
        parts.append(f.ref)
    return " ".join(parts) or "—"


def _footer() -> str:
    core = core_provenance()
    commit = (core.get("source_commit") or "unknown")[:7]
    dirty = "+dirty" if core.get("source_dirty") else ""
    return (f"<sub>spec-kit-specguard {__version__} · SpecGuard core {commit}{dirty} "
            f"(vendored) · {DISCLAIMER}</sub>")


def _findings_table(findings: list[Finding]) -> list[str]:
    if not findings:
        return ["No structural findings."]
    rows = ["| Severity | Check | Where | Detail |", "|---|---|---|---|"]
    rows += [f"| {f.severity} | {f.check_id} | {_where(f)} | {_cell(f.message)} |"
             for f in findings]
    return rows


# --------------------------------------------------------------------- gate --

def gate_payload(target, doc, results, findings, verdict, cfg, blocking, not_checked) -> dict:
    gates = Counter(r.gate for r in results)
    kinds = Counter(r.requirement.kind for r in results)
    return {
        "tool": "spec-kit-specguard",
        "version": __version__,
        "core": core_provenance(),
        "command": "gate",
        "spec": target.display(target.spec_path),
        "profile": cfg["profile"],
        "fail_on": cfg["fail_on"],
        "verdict": verdict,
        "blocking": blocking,
        "counts": {
            "requirements": dict(sorted(kinds.items())),
            "user_stories": len(doc.stories),
            "gates": {g: gates.get(g, 0) for g in ("PASS", "WARN", "FAIL")},
            "findings": {s: sum(f.severity == s for f in findings)
                         for s in ("error", "warn", "info")},
        },
        "findings": [
            {"check": f.check_id, "severity": f.severity, "line": f.line, "ref": f.ref,
             "message": f.message}
            for f in findings
        ],
        "requirements": [
            {
                "id": r.requirement.req_id,
                "kind": r.requirement.kind,
                "line": r.requirement.line,
                "gate": r.gate,
                "overall": r.scores.overall,
                "completeness": r.scores.completeness,
                "consistency": r.scores.consistency,
                "verifiability": r.scores.verifiability,
                "sc_class": r.sc_class,
                "smells": [
                    {"type": h.smell_type.value, "trigger": h.trigger, "severity": h.severity,
                     "explanation": h.explanation}
                    for h in r.hits
                ],
                "suppressed": [
                    {"type": s.hit.smell_type.value, "trigger": s.hit.trigger, "rule": s.rule}
                    for s in r.suppressed
                ],
            }
            for r in results
        ],
        "not_checked": list(not_checked),
        "checks_doc": checks_doc_hint(target),
    }


def gate_markdown(payload: dict) -> str:
    c = payload["counts"]
    kinds = " · ".join(f"{n} {k}" for k, n in c["requirements"].items()) or "0 requirements"
    g, fc = c["gates"], c["findings"]
    out = [
        f"## SpecGuard gate: {payload['verdict']}",
        "",
        f"`{payload['spec']}` · profile `{payload['profile']}` · {kinds} · "
        f"{c['user_stories']} user {'story' if c['user_stories'] == 1 else 'stories'}",
        "",
        f"Requirements: {g['PASS']} PASS · {g['WARN']} WARN · {g['FAIL']} FAIL — "
        f"Findings: {fc['error']} error · {fc['warn']} warn · {fc['info']} info — "
        f"**Blocking: {'yes' if payload['blocking'] else 'no'}** (fail_on={payload['fail_on']})",
        "",
        "### Findings",
        "",
    ]
    findings = [_as_finding(f) for f in payload["findings"]]
    out += _findings_table(findings)

    flagged = [r for r in payload["requirements"] if r["gate"] != "PASS"]
    out += ["", "### Requirements flagged (WARN/FAIL)", ""]
    if not flagged:
        out.append(f"None — all {len(payload['requirements'])} assessed requirements PASS.")
    else:
        out += ["| ID | Line | Gate | Overall | C / S / V | SC class | Smells |",
                "|---|---|---|---|---|---|---|"]
        for r in flagged:
            smells = "; ".join(f"{s['type']} \"{s['trigger']}\" ({s['severity']})"
                               for s in r["smells"]) or "none (score: missing modal / metric)"
            out.append(
                f"| {r['id']} | L{r['line']} | {r['gate']} | {r['overall']:.2f} | "
                f"{r['completeness']:.2f} / {r['consistency']:.2f} / {r['verifiability']:.2f} | "
                f"{r['sc_class'] or '—'} | {_cell(smells)} |"
            )

    suppressed = [(r["id"], s) for r in payload["requirements"] for s in r["suppressed"]]
    if suppressed:
        by_rule = Counter(s["rule"] for _, s in suppressed)
        summary = ", ".join(f"{rule} ×{n}" for rule, n in sorted(by_rule.items()))
        out += ["", f"Profile `{payload['profile']}` suppressed {len(suppressed)} core hit(s) "
                f"as register idiom: {summary} (rules: `{payload['checks_doc']}`)."]

    if payload["not_checked"]:
        out += ["", "### Not checked deterministically", ""]
        out += [f"- {item}" for item in payload["not_checked"]]
        out += ["", "These need judgment: use `/speckit.checklist`, `/speckit.analyze` "
                "or human review."]
    out += ["", _footer(), ""]
    return "\n".join(out)


# -------------------------------------------------------------------- trace --

def trace_payload(target, findings, summary, verdict, cfg, blocking) -> dict:
    return {
        "tool": "spec-kit-specguard",
        "version": __version__,
        "core": core_provenance(),
        "command": "trace",
        "spec": target.display(target.spec_path),
        "tasks": target.display(target.tasks_path),
        "fail_on": cfg["fail_on"],
        "verdict": verdict,
        "blocking": blocking,
        "coverage": summary,
        "findings": [
            {"check": f.check_id, "severity": f.severity, "line": f.line, "ref": f.ref,
             "message": f.message}
            for f in findings
        ],
    }


def trace_markdown(payload: dict) -> str:
    s = payload["coverage"]
    out = [
        f"## SpecGuard trace: {payload['verdict']}",
        "",
        f"`{payload['spec']}` ↔ `{payload['tasks']}`",
        "",
        f"Tasks: {s['tasks_done']}/{s['tasks']} done · user stories with tasks: "
        f"{s['stories_with_tasks']}/{s['stories']} · FRs referenced by tasks: "
        f"{s['functional_requirements_referenced']}/{s['functional_requirements']} — "
        f"**Blocking: {'yes' if payload['blocking'] else 'no'}** (fail_on={payload['fail_on']})",
        "",
        "Findings use only links written in the artifacts ([US#] tags, FR/SC IDs in task "
        "text); nothing is inferred from wording.",
        "",
    ]
    out += _findings_table([_as_finding(f) for f in payload["findings"]])
    out += ["", _footer(), ""]
    return "\n".join(out)


def _as_finding(d: dict) -> Finding:
    return Finding(check_id=d["check"], severity=d["severity"], message=d["message"],
                   line=d["line"], ref=d["ref"])


def to_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
