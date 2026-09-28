"""Regressions observed on 0f4a305 before production changes."""

from specguard.agents.base import AgentRequest
from specguard.agents.traceability_agent import TraceabilityAgent
from specguard.compliance import DO_178C_OBJECTIVES, run_compliance_check
from specguard.compliance.cross_domain import CROSS_TIMING_BUDGET
from specguard.data.cva6_requirements import Requirement


def test_empty_legacy_runner_is_not_pass():
    report = run_compliance_check(lambda query, params: [], DO_178C_OBJECTIVES)
    assert report.passing_objective_ids == []


def test_zero_evaluations_is_not_one_hundred_percent():
    assert run_compliance_check(lambda q, p: [], []).compliance_rate is None


def test_timing_query_does_not_replace_missing_budget_with_zero():
    assert "coalesce(b, 0)" not in CROSS_TIMING_BUDGET.cypher_query
    assert "timing_composition" in CROSS_TIMING_BUDGET.cypher_query


def test_user_requirements_get_no_synthetic_certification_metadata():
    report = TraceabilityAgent("trace").run(
        AgentRequest(
            requirements=[
                Requirement(
                    req_id="USER-1",
                    text="The controller shall sample every 10 ms.",
                    category="Test",
                )
            ]
        )
    )
    assert report.payload["passing"] == 0
    assert report.payload["violation_count"] == 0
