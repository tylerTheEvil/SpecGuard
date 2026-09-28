"""Behavioral checks of reviewed scope, freshness and the static contract fragment."""

from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from specguard.cli import main
from specguard.compliance import DO_178C_OBJECTIVES, run_compliance_check
from specguard.compliance.constraint_engine import RuleScope
from specguard.verification.analyzer import analyze_bundle
from specguard.verification.graph_io import bundle_graph, read_bundle
from specguard.verification.model import COLLECTIONS, Bundle, digest
from specguard.verification.results import CheckResult, summarize
from specguard.verification.results import CheckStatus as S


def reviewed(data=None):
    data = copy.deepcopy(data or {})
    data.update(schema_version=1, id="synthetic", synthetic=True)
    data["scope"] = {
        "reviewed": True,
        "source": "synthetic-review",
        "complete": list(COLLECTIONS),
        "expected": {k: [r["id"] for r in data.get(k, [])] for k in COLLECTIONS},
    }
    return data


def run(data, **kwargs):
    return analyze_bundle(Bundle.from_dict(data), **kwargs)


def results(data, rule, **kwargs):
    return [r for r in run(data, **kwargs)["results"] if r["rule_id"] == rule]


def contracts(count=2):
    data = {
        "requirements": [],
        "contracts": [],
        "model": {
            "variables": {
                "MODE": {"type": "enum", "values": ["RUN", "STOP"]},
                "CONFIG": {"type": "enum", "values": ["A", "B"]},
                "ENABLE": {"type": "number", "min": 0, "max": 1},
                "LATENCY": {"type": "number", "unit": "ms", "min": 0, "max": 10},
                "READY": {"type": "boolean"},
            },
            "reachability": {"kind": "cartesian", "reviewed": True, "source": "review:model"},
        },
    }
    for i in range(count):
        req = {
            "id": f"R{i}",
            "text": f"While MODE is RUN, CTRL shall maintain ENABLE equal to {i % 2}.",
            "source": f"synthetic:R{i}",
            "version": "1",
        }
        data["requirements"].append(req)
        data["contracts"].append(
            {
                "id": f"C{i}",
                "requirement_ids": [req["id"]],
                "requirement_hashes": {req["id"]: digest(req)},
                "review_status": "accepted",
                "source": f"review:C{i}",
                "bindings": {"MODE": "MODE", "ENABLE": "CTRL.ENABLE"},
                "when": [{"var": "MODE", "eq": "RUN"}],
                "guarantees": [{"var": "ENABLE", "eq": i % 2}],
            }
        )
    return reviewed(data)


def timing(**overrides):
    item = {
        "id": "T",
        "budget": {"value": 2, "unit": "ms"},
        "composition": "additive",
        "components_complete": True,
        "review_status": "accepted",
        "source": "review:T",
        "components": [
            {"id": "SW", "budget": {"value": 1000, "unit": "us"}},
            {"id": "HW", "budget": {"value": 1000000, "unit": "ns"}},
        ],
    }
    item.update(overrides)
    return reviewed({"timing": [item]})


def scenario(**overrides):
    item = {
        "id": "S",
        "event": "loss of sensor data",
        "mode": "RUN",
        "hazard_id": "H",
        "requirement_ids": ["R"],
        "response": "disable actuator",
        "time_limit": {"value": 10, "unit": "ms"},
        "responsibility": {"SW": "controller"},
        "source": "review:S",
        "review_status": "accepted",
        "applicable": True,
        "complete": True,
    }
    item.update(overrides)
    return reviewed(
        {
            "scenarios": [item],
            "requirements": [{"id": "R", "text": "nominal"}],
            "hazards": [{"id": "H", "description": "uncommanded actuation"}],
        }
    )


def test_complete_scope_pass_fail_na_error_and_partial():
    c = DO_178C_OBJECTIVES[0]
    scopes = {c.objective_id: RuleScope(["R"], "review:1", complete=True)}
    r = run_compliance_check(lambda q, p: [], [c], scopes=scopes)
    assert r.results[0].status == S.PASS
    assert r.compliance_rate == 1
    scopes[c.objective_id].complete = False
    r = run_compliance_check(lambda q, p: [{"violating_requirement": "R"}], [c], scopes=scopes)
    assert r.results[0].status == S.UNKNOWN
    scopes[c.objective_id].complete = True
    r = run_compliance_check(lambda q, p: [{"violating_requirement": "R"}], [c], scopes=scopes)
    assert r.results[0].status == S.FAIL
    scopes[c.objective_id] = RuleScope(
        [], "review:zero", complete=True, not_applicable_reason="No HLR allocated in this subsystem"
    )
    assert (
        run_compliance_check(lambda q, p: [], [c], scopes=scopes).results[0].status
        == S.NOT_APPLICABLE
    )

    def broken(q, p):
        raise RuntimeError("runner failed")

    assert run_compliance_check(broken, [c]).results[0].status == S.ERROR


def test_fail_does_not_hide_incomplete_or_stale():
    rs = [
        CheckResult("a", ["R"], S.FAIL, "violation", freshness="STALE"),
        CheckResult("b", [], S.UNKNOWN, "missing"),
        CheckResult("c", [], S.ERROR, "connection"),
    ]
    stats = summarize(rs)
    assert stats["status"] == S.FAIL
    assert stats["stale"] == 1 and stats["incomplete"]
    assert stats["counts"]["ERROR"] == 1
    assert stats["pass_fraction_completed"] is None


def test_empty_scope_is_unknown_unless_explicitly_reviewed():
    assert run({"schema_version": 1, "id": "empty"})["summary"]["status"] == S.UNKNOWN
    assert run(reviewed())["summary"]["status"] == S.NOT_APPLICABLE


def test_mixed_units_timing_pass():
    r = results(timing(), "P0-TIMING")[0]
    assert r["status"] == S.PASS
    assert r["details"]["known_sum_s"] == "0.002000000"


@pytest.mark.parametrize("composition", [None, "parallel", "unknown"])
def test_timing_requires_additive_model(composition):
    assert results(timing(composition=composition), "P0-TIMING")[0]["status"] == S.UNKNOWN


def test_missing_timing_budget_is_unknown_but_known_overrun_is_fail():
    data = timing()
    data["timing"][0]["components"][1].pop("budget")
    assert results(data, "P0-TIMING")[0]["status"] == S.UNKNOWN
    data["timing"][0]["components"][0]["budget"] = {"value": 3, "unit": "ms"}
    r = results(data, "P0-TIMING")[0]
    assert r["status"] == S.FAIL and r["missing_prerequisites"]


def test_invalid_timing_values_do_not_establish_fail():
    data = timing()
    data["timing"][0]["components"][0]["budget"]["value"] = -2
    assert results(data, "P0-TIMING")[0]["status"] == S.UNKNOWN


def test_same_mode_conflict_and_different_mode_no_conflict():
    data = contracts()
    r = results(data, "P2-PAIR")[0]
    assert r["status"] == S.FAIL and "R0" in r["objects"] and "R1" in r["objects"]
    data["contracts"][1]["when"][0]["eq"] = "STOP"
    assert results(data, "P2-PAIR")[0]["status"] == S.NOT_APPLICABLE


def test_distinct_configurations_are_not_conflicting():
    data = contracts()
    for i, contract in enumerate(data["contracts"]):
        contract["when"].append({"var": "CONFIG", "eq": ["A", "B"][i]})
        contract["bindings"]["CONFIG"] = "build variant"
    assert results(data, "P2-PAIR")[0]["status"] == S.NOT_APPLICABLE


def test_numeric_intervals_and_unit_normalization():
    data = contracts()
    for c in data["contracts"]:
        c["bindings"]["LATENCY"] = "interface latency"
    a, b = data["contracts"]
    a["guarantees"] = [{"var": "LATENCY", "min": 1, "max": 2, "unit": "ms"}]
    b["guarantees"] = [{"var": "LATENCY", "eq": 2000, "unit": "us"}]
    assert results(data, "P2-PAIR")[0]["status"] == S.PASS
    b["guarantees"][0]["eq"] = 2001
    assert results(data, "P2-PAIR")[0]["status"] == S.FAIL
    b["guarantees"][0]["unit"] = "V"
    assert results(data, "P2-PAIR")[0]["status"] == S.UNKNOWN


def test_boolean_guarantees_and_wrong_type():
    data = contracts()
    for i, c in enumerate(data["contracts"]):
        c["bindings"]["READY"] = "ready output"
        c["guarantees"] = [{"var": "READY", "eq": bool(i)}]
    assert results(data, "P2-PAIR")[0]["status"] == S.FAIL
    data["contracts"][0]["guarantees"][0]["eq"] = 1
    assert results(data, "P2-PAIR")[0]["status"] == S.UNKNOWN


def test_impossible_antecedent_is_reported_and_not_vacuous_pass():
    data = contracts()
    data["contracts"][0]["when"].append({"var": "MODE", "eq": "STOP"})
    assert results(data, "P2-CONDITION")[0]["status"] == S.NOT_APPLICABLE
    assert results(data, "P2-PAIR")[0]["status"] == S.NOT_APPLICABLE


@pytest.mark.parametrize("change", ["reachability", "syntax", "mapping", "review"])
def test_unsupported_or_unreviewed_contract_is_unknown(change):
    data = contracts()
    if change == "reachability":
        del data["model"]["reachability"]
    elif change == "syntax":
        data["contracts"][0]["when"] = [{"not": {"var": "MODE", "eq": "RUN"}}]
    elif change == "mapping":
        data["contracts"][0]["bindings"] = {}
    else:
        data["contracts"][0]["review_status"] = "candidate"
    assert results(data, "P2-PAIR")[0]["status"] == S.UNKNOWN


def test_finite_reachable_states_are_used():
    data = contracts()
    data["model"]["reachability"] = {
        "kind": "states",
        "reviewed": True,
        "source": "model",
        "states": [{"MODE": "STOP", "CONFIG": "A", "ENABLE": 0, "LATENCY": 1, "READY": False}],
    }
    assert results(data, "P2-PAIR")[0]["status"] == S.NOT_APPLICABLE
    data["model"]["reachability"]["states"][0]["MODE"] = "RUN"
    assert results(data, "P2-PAIR")[0]["status"] == S.FAIL


def test_conflict_beyond_first_15_pairs_and_resource_limit():
    data = contracts(18)
    for c in data["contracts"][:-1]:
        c["guarantees"][0]["eq"] = 0
    rs = results(data, "P2-PAIR")
    assert len(rs) == 153 and any(r["status"] == S.FAIL and "C17" in r["objects"] for r in rs)
    limited = run(data, max_pairs=15)
    assert limited["summary"]["status"] == S.UNKNOWN
    r = next(r for r in limited["results"] if r["rule_id"] == "P2-PAIR-SCOPE")
    assert r["details"]["expected_pairs"] == 153


def test_scenario_pass_missing_reaction_fail_partial_unknown():
    data = scenario()
    assert results(data, "P1-SCENARIO")[0]["status"] == S.PASS
    assert run(data)["scenario_coverage"]["fraction"] == 1
    del data["scenarios"][0]["response"]
    assert results(data, "P1-SCENARIO")[0]["status"] == S.FAIL
    data["scenarios"][0]["complete"] = False
    assert results(data, "P1-SCENARIO")[0]["status"] == S.UNKNOWN


def test_no_scenario_model_candidate_and_justified_na():
    data = contracts()
    del data["scope"]["expected"]["scenarios"]
    assert results(data, "P1-SCENARIO-SCOPE")[0]["status"] == S.UNKNOWN
    data = scenario(review_status="candidate")
    assert results(data, "P1-SCENARIO")[0]["status"] == S.UNKNOWN
    assert run(data)["scenario_coverage"]["fraction"] is None
    data = scenario(applicable=False, not_applicable_reason="Sensor not fitted to this variant")
    assert results(data, "P1-SCENARIO")[0]["status"] == S.NOT_APPLICABLE


def test_scenario_missing_required_inventory_not_proven_defect():
    data = scenario()
    data["requirements"] = []  # manifest still expects R
    assert results(data, "P1-SCENARIO")[0]["status"] == S.UNKNOWN


def test_field_na_requires_reason_and_cannot_exempt_response():
    data = scenario(time_limit=None, not_applicable_fields={"time_limit": "non-timed recovery"})
    assert results(data, "P1-SCENARIO")[0]["status"] == S.PASS
    data["scenarios"][0]["response"] = None
    data["scenarios"][0]["not_applicable_fields"]["response"] = "not needed"
    assert results(data, "P1-SCENARIO")[0]["status"] == S.FAIL


def test_changed_requirement_invalidates_evidence_and_formalization():
    data = contracts()
    data["evidence"] = [
        {
            "id": "E",
            "source": "test:1",
            "review_status": "accepted",
            "outcome": "FAIL",
            "dependencies": {"R0": digest(data["requirements"][0])},
        }
    ]
    data = reviewed(data)
    data["requirements"][0]["text"] += " Changed."
    r = results(data, "P0-EVIDENCE")[0]
    assert r["status"] == S.FAIL and r["freshness"] == "STALE"
    assert results(data, "P2-CONTRACT")[0]["freshness"] == "STALE"
    assert run(data)["summary"]["status"] == S.FAIL


def assumption_data():
    a = {
        "id": "A",
        "statement": "Sensor data arrives within 2 ms",
        "source": "spec:1",
        "scope": "RUN@A",
        "owner": "integration",
        "verification_method": "bench test",
        "review_status": "accepted",
        "evidence": ["E"],
        "version": "1",
    }
    e = {
        "id": "E",
        "source": "bench:1",
        "review_status": "accepted",
        "outcome": "PASS",
        "dependencies": {"A": digest(a)},
    }
    return reviewed(
        {
            "assumptions": [a],
            "evidence": [e],
            "requirements": [{"id": "R", "assumption_ids": ["A"]}],
        }
    )


def test_assumption_confirmation_and_stale_dependency():
    data = assumption_data()
    assert results(data, "P1-ASSUMPTION-DEPENDENCY")[0]["status"] == S.PASS
    data["assumptions"][0]["statement"] = "Data arrives within 1 ms"
    r = results(data, "P1-ASSUMPTION-DEPENDENCY")[0]
    assert r["status"] == S.UNKNOWN and r["freshness"] == "STALE"


def test_candidate_assumption_is_not_promoted_by_literal_evidence():
    data = assumption_data()
    data["assumptions"][0]["review_status"] = "candidate"
    data["evidence"][0]["dependencies"]["A"] = digest(data["assumptions"][0])
    assert results(data, "P1-ASSUMPTION")[0]["status"] == S.UNKNOWN


def test_cross_domain_assumptions_conflict():
    data = contracts()
    data["assumptions"] = [
        {
            "id": "ASW",
            "domain": "SW",
            "scope": "sensor",
            "review_status": "accepted",
            "when": [{"var": "MODE", "eq": "RUN"}],
            "claim": [{"var": "ENABLE", "eq": 1}],
        },
        {
            "id": "AHW",
            "domain": "HW",
            "scope": "sensor",
            "review_status": "accepted",
            "when": [{"var": "MODE", "eq": "RUN"}],
            "claim": [{"var": "ENABLE", "eq": 0}],
        },
    ]
    data = reviewed(data)
    assert results(data, "P1-ASSUMPTION-COMPATIBILITY")[0]["status"] == S.FAIL


def test_structural_missing_link_requires_complete_inventory():
    data = reviewed(
        {
            "requirements": [
                {
                    "id": "R",
                    "links_complete": True,
                    "required_links": [
                        {
                            "relation": "MITIGATES",
                            "targets": ["H"],
                            "reason": "allocated hazard",
                            "reviewed": True,
                        }
                    ],
                }
            ],
            "hazards": [{"id": "H"}],
        }
    )
    assert results(data, "P0-STRUCTURE")[0]["status"] == S.FAIL
    data["scope"]["complete"].remove("hazards")
    assert results(data, "P0-STRUCTURE")[0]["status"] == S.UNKNOWN
    data["requirements"][0]["mitigates"] = ["H"]
    r = results(data, "P0-STRUCTURE")[0]
    assert r["status"] == S.PASS and "sufficiency" in r["reason"]


def test_cli_json_import_verify_and_human_output(tmp_path, capsys):
    path = tmp_path / "case.json"
    path.write_text(json.dumps(contracts()))
    assert (
        main(["import", str(path), "--format", "bundle", "--dataset-tag", "synthetic", "--json"])
        == 0
    )
    imported = json.loads(capsys.readouterr().out)
    assert imported["nodes"] == 4 and imported["edges"] == 2 and imported["dry_run"]
    assert main(["verify", str(path), "--json"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["counts"]["FAIL"] == 1
    assert main(["verify", str(path)]) == 2
    assert "P2-PAIR" in capsys.readouterr().out
    # Real entry point, not only direct handler calls.
    proc = subprocess.run(
        [sys.executable, "-m", "specguard.cli", "verify", str(path), "--json"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2 and json.loads(proc.stdout)["summary"]["counts"]["FAIL"] == 1


def test_cli_error_is_explicit(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{")
    assert main(["verify", str(path), "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "ERROR"


def test_neo4j_snapshot_reader_equivalence_and_integrity():
    data = contracts()
    calls = []

    def fake(query, params):
        calls.append((query, params))
        return [{"payload": json.dumps(data)}]

    bundle = read_bundle("synthetic", digest(data), runner=fake)
    assert analyze_bundle(bundle) == run(data)
    assert calls[0][1]["revision"] == digest(data)
    with pytest.raises(ValueError, match="hash mismatch"):
        read_bundle("synthetic", "wrong", runner=fake)
    with pytest.raises(ValueError, match="exactly one"):
        read_bundle("missing", "none", runner=lambda q, p: [])


def test_hazard_projection_uses_canonical_label():
    data = reviewed({"requirements": [{"id": "R", "mitigates": ["H"]}], "hazards": [{"id": "H"}]})
    g = bundle_graph(Bundle.from_dict(data))
    assert g["nodes"][1]["label"] == "SafetyHazard"
    assert g["edges"] == [{"source": "R", "target": "H", "type": "MITIGATES"}]


def test_unknown_contract_does_not_mask_known_pair_failure():
    data = contracts(3)
    data["contracts"][2]["review_status"] = "candidate"
    stats = run(data)["summary"]
    assert stats["status"] == S.FAIL and stats["counts"]["UNKNOWN"] > 0


def test_stdlib_only_core_subprocess():
    proc = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import sys; sys.path.insert(0, 'src'); "
            "from specguard.verification.analyzer import analyze_bundle; "
            "from specguard.verification.model import Bundle; "
            "assert analyze_bundle(Bundle.from_dict({'id':'x','schema_version':1}))"
            "['summary']['status'] == 'UNKNOWN'; import specguard.cli",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_scenario_proven_omission_survives_other_missing_data():
    data = scenario(response=None)
    data["requirements"] = []
    r = results(data, "P1-SCENARIO")[0]
    assert r["status"] == S.FAIL
    assert "requirement R" in r["missing_prerequisites"]


def test_evidence_failure_survives_inaccessible_dependency():
    data = reviewed(
        {
            "evidence": [
                {
                    "id": "E",
                    "source": "test:1",
                    "review_status": "accepted",
                    "outcome": "FAIL",
                    "dependencies": {"missing": "oldhash"},
                }
            ]
        }
    )
    r = results(data, "P0-EVIDENCE")[0]
    assert r["status"] == S.FAIL and r["freshness"] == "UNKNOWN"
    assert r["missing_prerequisites"] == ["dependency missing"]


def test_transitive_dependencies_must_be_bound():
    data = assumption_data()
    data["evidence"].append(
        {
            "id": "E2",
            "source": "test:2",
            "review_status": "accepted",
            "outcome": "PASS",
            "dependencies": {"R": digest(data["requirements"][0])},
        }
    )
    data = reviewed(data)
    r = next(r for r in results(data, "P0-EVIDENCE") if "E2" in r["objects"])
    assert r["status"] == S.UNKNOWN
    assert "unrecorded dependency A" in r["missing_prerequisites"]


def test_incompatible_variable_mapping_is_unknown():
    data = contracts()
    data["contracts"][1]["bindings"]["ENABLE"] = "DIFFERENT_CTRL.ENABLE"
    assert results(data, "P2-PAIR")[0]["status"] == S.UNKNOWN


def test_scoped_memory_mock_cannot_gain_false_pass_authority():
    from specguard.compliance.memory_runner import MockGraph, make_graph_runner

    c = DO_178C_OBJECTIVES[0]
    report = run_compliance_check(
        make_graph_runner(MockGraph()),
        [c],
        scopes={c.objective_id: RuleScope(["R"], "caller", complete=True)},
    )
    assert report.results[0].status == S.UNKNOWN


def test_numeric_witness_survives_unknown_scope():
    from specguard.compliance.cross_domain import CROSS_TIMING_BUDGET

    def runner(q, p):
        return [
            {
                "violating_requirement": "SYS",
                "budget": 10,
                "allocated": 12,
                "_status": "FAIL",
                "missing_budgets": 1,
            }
        ]

    report = run_compliance_check(runner, [CROSS_TIMING_BUDGET])
    assert report.violation_count == 1
    assert {r.status for r in report.results} == {S.FAIL, S.UNKNOWN}


def test_report_pair_limit_denominator_includes_unexamined_pairs():
    data = contracts(18)
    report = run(data, max_pairs=15)
    assert report["summary"]["expected_checks"] >= 153


def test_agent_bundle_path_is_identical_to_cli_analyzer():
    from specguard.agents.base import AgentRequest
    from specguard.agents.traceability_agent import TraceabilityAgent

    data = contracts()
    report = TraceabilityAgent("trace").run(AgentRequest([], {"verification_bundle": data}))
    assert report.payload == run(data)


def test_destructive_load_guard_rejects_default_configuration(monkeypatch):
    from specguard.compliance.neo4j_runner import Neo4jConfig, require_isolated_test_database

    monkeypatch.delenv("SPECGUARD_ISOLATED_TEST_TARGET", raising=False)
    with pytest.raises(RuntimeError, match="disposable"):
        require_isolated_test_database(Neo4jConfig())


def test_invalid_mitigates_target_rejected_before_database_connection():
    from specguard.graph.neo4j_io import merge_accepted_edges

    with pytest.raises(ValueError, match="MITIGATES requires"):
        merge_accepted_edges(
            [
                {
                    "from_label": "Requirement",
                    "from_id": "R",
                    "to_label": "Component",
                    "to_id": "X",
                    "rel_type": "MITIGATES",
                    "properties": {"human_confirmed": True, "review_status": "ACCEPTED"},
                }
            ]
        )


def test_legacy_hazard_review_export_is_canonical():
    from specguard.extraction.extractor import EdgeProposal, EdgeType
    from specguard.extraction.review import ReviewQueue, export_accepted_edges

    queue = ReviewQueue()
    item = queue.add(
        EdgeProposal(
            edge_type=EdgeType.MITIGATES,
            source_id="R",
            target_entity="H",
            confidence=0.9,
            evidence_span="hazard H",
            target_label="Hazard",
        )
    )
    queue.accept(item.item_id)
    assert export_accepted_edges(queue)[0]["to_label"] == "SafetyHazard"


def test_synthetic_comparison_replays_original_commit(tmp_path):
    available = subprocess.run(
        ["git", "cat-file", "-e", "0f4a3057a1bf2800249558c484220ca5093ed091:src/specguard"],
        capture_output=True,
    )
    if available.returncode:
        pytest.skip("Original baseline commit unavailable in this checkout/export")
    proc = subprocess.run(
        [sys.executable, "experiments/grounded_checks.py", "--output", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    original = json.loads((tmp_path / "comparison_baseline.json").read_text())
    assert original["executed_commit"] == "0f4a3057a1bf2800249558c484220ca5093ed091"
    old_case = next(c for c in original["cases"] if c["case_id"] == "empty")
    assert old_case["legacy_empty_graph"]["rate"] == 1
    new = json.loads((tmp_path / "comparison_p0_p1_p2.json").read_text())
    new_case = next(c for c in new["cases"] if c["case_id"] == "empty")
    assert new_case["report"]["summary"]["status"] == S.UNKNOWN


def test_scope_execution_failure_is_error():
    class BrokenScope:
        def __call__(self, q, p):
            return []

        def scope_for(self, constraint):
            raise RuntimeError("inventory read failed")

    report = run_compliance_check(BrokenScope(), DO_178C_OBJECTIVES[:1])
    assert report.results[0].status == S.ERROR
    assert report.passing_objective_ids == []


def test_injected_demo_runner_preserves_synthetic_label():
    from specguard.agents.base import AgentRequest
    from specguard.agents.traceability_agent import TraceabilityAgent
    from specguard.compliance.memory_runner import build_demo_graph, make_graph_runner

    report = TraceabilityAgent("demo", runner=make_graph_runner(build_demo_graph())).run(
        AgentRequest([])
    )
    assert report.payload["synthetic"] is True
