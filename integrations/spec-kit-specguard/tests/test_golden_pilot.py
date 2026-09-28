"""Golden regression on the SpecGuard spec-kit pilot corpus (6 specs, 120 reqs).

The pilot specs were generated for the SpecGuard Phase-0 pilot
(results/speckit_pilot/pilot_report.md in the SpecGuard repo). The golden file
pins every requirement's gate and the spec verdicts; any behaviour change must
show up here and be explained. Regenerate deliberately with
``UPDATE_GOLDEN=1 pytest tests/test_golden_pilot.py``.

Expected shape (pilot report, "calibrated" column): 120 requirements, 0 FAIL,
and the only flagged ones are 001/FR-014 ("appropriate", genuine catch),
001/FR-009 ("larger", documented residual FP) and 003/SC-006 (unmeasured SC).
"""

from __future__ import annotations

import json
import os

from conftest import FIXTURES
from specguard_speckit.assess import assess_all
from specguard_speckit.model import verdict_from
from specguard_speckit.parse_spec import parse_spec
from specguard_speckit.structure import check_structure

PILOT = FIXTURES / "pilot"
GOLDEN = FIXTURES / "pilot_golden.json"


def snapshot() -> dict:
    out = {}
    for spec in sorted(PILOT.glob("*/spec.md")):
        doc = parse_spec(spec.read_text(encoding="utf-8"))
        results = assess_all(doc.requirements)
        findings = check_structure(doc, results)
        out[spec.parent.name] = {
            "verdict": verdict_from(findings, [r.gate for r in results]),
            "findings": sorted(f"{f.check_id}:{f.ref or ''}" for f in findings),
            "gates": {r.requirement.req_id: r.gate for r in results},
        }
    return out


def test_pilot_golden():
    current = snapshot()
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert current == json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_pilot_matches_calibrated_expectation():
    current = snapshot()
    gates = {f"{spec}/{rid}": g for spec, d in current.items() for rid, g in d["gates"].items()}
    assert len(gates) == 120
    flagged = {k: g for k, g in gates.items() if g != "PASS"}
    assert flagged == {
        "001-photo-albums/FR-009": "WARN",
        "001-photo-albums/FR-014": "WARN",
        "003-log-analyzer-cli/SC-006": "WARN",
    }
