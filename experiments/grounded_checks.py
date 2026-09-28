"""Reproduce synthetic technical checks; never estimates general precision/recall.

Baseline executes the original commit from a temporary git archive, not current
code under an old label. --cases accepts a separately reviewed holdout JSON;
rules/weights are never adjusted by this script. All external effects are files.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from specguard.verification.analyzer import analyze_bundle, render_report
from specguard.verification.model import COLLECTIONS, Bundle, digest

BASELINE_COMMIT = "0f4a3057a1bf2800249558c484220ca5093ed091"


def reviewed(data: dict) -> dict:
    data = copy.deepcopy(data)
    data.update(schema_version=1, id="synthetic-flight-control", synthetic=True)
    data["scope"] = {
        "reviewed": True,
        "source": "synthetic:review-record-1",
        "complete": list(COLLECTIONS),
        "expected": {k: [r["id"] for r in data.get(k, [])] for k in COLLECTIONS},
    }
    return data


def example() -> dict:
    """Five illustrative failure scenarios, with deliberate gaps and a contract conflict."""
    requirements = [
        {
            "id": "R-ENABLE-1",
            "version": "1",
            "source": "synthetic:spec#1",
            "text": "While MODE is RUN, CTRL shall maintain ENABLE equal to 1.",
        },
        {
            "id": "R-ENABLE-0",
            "version": "1",
            "source": "synthetic:spec#2",
            "text": "While MODE is RUN, CTRL shall maintain ENABLE equal to 0.",
        },
        {
            "id": "R-SAMPLE",
            "version": "1",
            "source": "synthetic:spec#3",
            "text": "The controller shall sample the sensor every 10 ms.",
            "assumption_ids": ["A-SENSOR"],
            "scenario_ids": ["S-LOSS"],
        },
    ]
    contracts = [
        {
            "id": "C-" + r["id"],
            "version": "1",
            "source": "synthetic:formalization-review",
            "requirement_ids": [r["id"]],
            "requirement_hashes": {r["id"]: digest(r)},
            "review_status": "accepted",
            "bindings": {"MODE": "MODE", "ENABLE": "CTRL.ENABLE"},
            "when": [{"var": "MODE", "eq": "RUN"}],
            "guarantees": [{"var": "ENABLE", "eq": 1 - i}],
        }
        for i, r in enumerate(requirements[:2])
    ]
    events = [
        ("LOSS", "loss of sensor data"),
        ("STALE", "stale sensor data"),
        ("TIMEOUT", "timeout"),
        ("RESET", "reset during exchange"),
        ("RECOVERY", "recovery"),
    ]
    scenarios = [
        {
            "id": "S-" + name,
            "version": "1",
            "mode": "RUN",
            "event": event,
            "hazard_id": "H-ACTUATION",
            "response": "hold disabled until data is validated",
            "time_limit": {"value": 10, "unit": "ms"},
            "responsibility": {"SW": "controller", "HW": "input validity flag"},
            "requirement_ids": ["R-SAMPLE"],
            "evidence": [],
            "review_status": "accepted",
            "source": "synthetic:scenario-review#" + name,
            "applicable": True,
            "complete": True,
        }
        for name, event in events
    ]
    scenarios[0].pop("response")
    for scenario in scenarios[1:]:
        requirement_id = "R-" + scenario["id"][2:]
        scenario["requirement_ids"] = [requirement_id]
        requirements.append(
            {
                "id": requirement_id,
                "version": "1",
                "source": "synthetic:spec#" + requirement_id,
                "text": "On " + scenario["event"] + ", the controller shall hold "
                "the actuator disabled within 10 ms until data is validated.",
            }
        )
    assumption = {
        "id": "A-SENSOR",
        "version": "1",
        "source": "synthetic:environment",
        "statement": "Sensor supplies valid data every 10 ms",
        "scope": "MODE=RUN",
        "owner": "integration",
        "verification_method": "bench test",
        "review_status": "candidate",
        "evidence": [],
    }
    evidence = {
        "id": "E-SAMPLE",
        "version": "1",
        "review_status": "accepted",
        "outcome": "PASS",
        "source": "synthetic:test-run#1",
        "dependencies": {
            "R-SAMPLE": digest(requirements[2]),
            "A-SENSOR": digest(assumption),
            "S-LOSS": digest(scenarios[0]),
        },
    }
    requirements[2]["text"] = "The controller shall sample the sensor every 20 ms."
    timing = {
        "id": "T-CONTROL",
        "source": "synthetic:allocation-review",
        "review_status": "accepted",
        "composition": "additive",
        "components_complete": True,
        "budget": {"value": 2, "unit": "ms"},
        "components": [{"id": "SW", "budget": {"value": 1000, "unit": "us"}}, {"id": "HW"}],
    }
    return reviewed(
        {
            "requirements": requirements,
            "contracts": contracts,
            "scenarios": scenarios,
            "assumptions": [assumption],
            "evidence": [evidence],
            "timing": [timing],
            "hazards": [
                {
                    "id": "H-ACTUATION",
                    "description": "Uncommanded actuation",
                    "source": "synthetic:FHA",
                }
            ],
            "model": {
                "variables": {
                    "MODE": {"type": "enum", "values": ["RUN", "STOP"]},
                    "ENABLE": {"type": "number", "min": 0, "max": 1},
                },
                "reachability": {
                    "kind": "cartesian",
                    "reviewed": True,
                    "source": "synthetic:static-domain-review",
                },
            },
        }
    )


def cases() -> list[dict]:
    base = example()
    answer = []
    for case_id, defect_class in [
        ("combined", "mixed"),
        ("empty", "scope"),
        ("partial", "scope"),
        ("timing-missing", "timing"),
        ("timing-valid", "timing"),
        ("same-mode", "semantic"),
        ("different-mode", "semantic"),
        ("missing-reaction", "scenario"),
        ("no-scenario-model", "scenario"),
        ("stale-evidence", "freshness"),
    ]:
        data = copy.deepcopy(base)
        if case_id == "empty":
            data = {"id": "synthetic-empty", "schema_version": 1, "synthetic": True}
        elif case_id == "partial":
            data["requirements"] = data["requirements"][:1]
        elif case_id.startswith("timing-"):
            data = reviewed({"timing": data["timing"]})
            if case_id == "timing-valid":
                data["timing"][0]["components"][1]["budget"] = {"value": 1, "unit": "ms"}
        elif case_id in ("same-mode", "different-mode"):
            data = reviewed(
                {
                    "requirements": data["requirements"][:2],
                    "contracts": data["contracts"],
                    "model": data["model"],
                }
            )
            if case_id == "different-mode":
                data["contracts"][1]["when"][0]["eq"] = "STOP"
        elif case_id == "missing-reaction":
            data = reviewed(
                {
                    "scenarios": data["scenarios"][:1],
                    "hazards": data["hazards"],
                    "requirements": [{"id": "R-SAMPLE", "text": "Nominal sampling."}],
                }
            )
        elif case_id == "no-scenario-model":
            del data["scope"]["expected"]["scenarios"]
        elif case_id == "stale-evidence":
            data = reviewed({"requirements": data["requirements"], "evidence": data["evidence"]})
        answer.append({"case_id": case_id, "defect_class": defect_class, "bundle": data})
    return answer


BASELINE_DRIVER = """
import json, sys
from specguard.core.pipeline import assess_requirement
from specguard.compliance import run_compliance_check, CROSS_DOMAIN_OBJECTIVES
from specguard.compliance.memory_runner import MockGraph, make_graph_runner
cases = json.load(sys.stdin)
output=[]
for case in cases:
    bundle=case['bundle']
    assessed=[assess_requirement(r['id'],r.get('text','')) for r in bundle.get('requirements',[])]
    graph=MockGraph()
    for r in bundle.get('requirements', []):
        graph.add_requirement(id=r['id'], text=r.get('text',''))
    imported=run_compliance_check(make_graph_runner(graph),CROSS_DOMAIN_OBJECTIVES)
    report=run_compliance_check(make_graph_runner(MockGraph()),CROSS_DOMAIN_OBJECTIVES)
    output.append({'case_id':case['case_id'],'defect_class':case['defect_class'],
        'text_gates':[{'id':r.requirement_id,'gate':r.gate_decision,
                      'consistency_heuristic':r.quality_scores.consistency} for r in assessed],
        'legacy_empty_graph':{'passing':report.passing_objective_ids,'rate':report.compliance_rate},
        'legacy_partial_import':{'loaded_requirements':len(graph.requirements),
                                 'passing':imported.passing_objective_ids,
                                 'rate':imported.compliance_rate},
        'structured_checks':('UNSUPPORTED in baseline: no '
                             'bundle/scenario/evidence/contract analyzer'),
        'scope':('Text heuristics and original empty-graph runner only; '
                 'bundle fields not analyzed')})
print(json.dumps(output))
"""


def baseline(input_cases: list[dict]) -> list[dict]:
    archive = subprocess.check_output(["git", "archive", BASELINE_COMMIT, "src"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="specguard-baseline-") as directory:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(directory, filter="data")
        env = {**os.environ, "PYTHONPATH": str(Path(directory) / "src")}
        proc = subprocess.run(
            [sys.executable, "-c", BASELINE_DRIVER],
            env=env,
            input=json.dumps(input_cases),
            capture_output=True,
            text=True,
            check=True,
            cwd=directory,
        )
        return json.loads(proc.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, help="External reviewed cases/holdout (read only)")
    parser.add_argument("--output", type=Path, default=ROOT / "results/grounded_checks")
    parser.add_argument("--write-example", action="store_true")
    args = parser.parse_args()
    input_cases = json.loads(args.cases.read_text()) if args.cases else cases()
    args.output.mkdir(parents=True, exist_ok=True)
    code_hash = digest(
        {
            str(p.relative_to(ROOT)): p.read_text()
            for p in sorted((ROOT / "src/specguard").rglob("*.py"))
        }
    )
    common = {
        "technical_check_only": True,
        "independent_gold_standard": False,
        "case_set_hash": digest(input_cases),
        "implementation_hash": code_hash,
        "base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    versions = [("baseline", baseline(input_cases))]
    for phase in ("p1", "p2"):
        output = [
            {
                "case_id": c["case_id"],
                "defect_class": c["defect_class"],
                "bundle_hash": digest(c["bundle"]),
                "report": analyze_bundle(Bundle.from_dict(c["bundle"]), phase=phase),
            }
            for c in input_cases
        ]
        versions.append(("p0_p1" if phase == "p1" else "p0_p1_p2", output))
    for name, output in versions:
        meta = {**common, "configuration": name, "cases": output}
        if name == "baseline":
            meta["executed_commit"] = BASELINE_COMMIT
            meta.pop("implementation_hash")
        (args.output / f"comparison_{name}.json").write_text(json.dumps(meta, indent=2) + "\n")
    (args.output / "cases.json").write_text(json.dumps(input_cases, indent=2) + "\n")
    report = analyze_bundle(Bundle.from_dict(example()))
    (args.output / "example_report.txt").write_text(render_report(report) + "\n")
    if args.write_example:
        (ROOT / "examples/verification_bundle.json").write_text(
            json.dumps(example(), indent=2) + "\n"
        )
    print(f"Exported {len(input_cases)} synthetic/holdout cases, 3 configurations to {args.output}")


if __name__ == "__main__":
    main()
