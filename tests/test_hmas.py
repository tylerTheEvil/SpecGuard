"""Tests for the HMAS skeleton (dissertation novelty #1, Phase 4).

These validate the *interfaces*, not a runtime: deterministic dispatch order,
report merging, the augmentative-LLM determinism invariant, heterogeneous
providers per role, and import hygiene (no anthropic/neo4j needed).
"""

from __future__ import annotations

import importlib

import pytest

# The HMAS FormalizationAgent (Layer 2) needs networkx ([graph] extra); skip
# cleanly so plain ``pytest`` with no extras still passes (quarantine invariant).
pytest.importorskip("networkx")

from specguard.agents import (
    Agent,
    AgentReport,
    AgentRequest,
    AssessmentReport,
    Coordinator,
    QualityAgent,
    TraceabilityAgent,
)
from specguard.data.cva6_requirements import get_all_requirements
from specguard.llm.mock_provider import MockProvider


def _reqs():
    return get_all_requirements()


def test_agents_package_imports_without_extras():
    """Importing the agents package must not pull anthropic or neo4j."""
    import sys

    # Fresh-ish import of the package and submodules.
    for mod in [
        "specguard.agents",
        "specguard.agents.base",
        "specguard.agents.quality_agent",
        "specguard.agents.formalization_agent",
        "specguard.agents.traceability_agent",
        "specguard.agents.coordinator",
    ]:
        importlib.import_module(mod)
    # Neither optional extra should have been imported as a side effect.
    assert "anthropic" not in sys.modules
    # neo4j is only used by the Neo4jGraphRunner, never by the agents path.
    assert "neo4j" not in sys.modules


def test_dispatch_order_is_deterministic():
    coord = Coordinator()  # default Quality -> Formalization -> Traceability
    report = coord.dispatch(_reqs())
    assert report.dispatch_order == ["quality", "formalization", "traceability"]
    # Custom order is honoured exactly as registered.
    coord2 = Coordinator(
        agents=[
            TraceabilityAgent("traceability"),
            QualityAgent("quality"),
        ]
    )
    report2 = coord2.dispatch(_reqs())
    assert report2.dispatch_order == ["traceability", "quality"]


def test_report_merging_contains_all_agent_payloads():
    report = Coordinator().dispatch(_reqs())
    assert set(report.reports) == {"quality", "formalization", "traceability"}
    q = report.reports["quality"].payload
    assert q["aggregate"]["total_requirements"] == 64
    f = report.reports["formalization"].payload
    assert f["graph_stats"]["total_nodes"] > 0
    t = report.reports["traceability"].payload
    assert t["objectives_checked"] == 15
    # to_dict() is JSON-serialisable and drops the private _graph payload.
    import json

    d = report.to_dict()
    json.dumps(d)  # must not raise
    assert "_graph" not in d["agents"]["formalization"]["payload"]


def test_quality_agent_determinism_invariant():
    """Gate results must be identical with and without a MockProvider."""
    reqs = _reqs()
    without = QualityAgent("q").run(AgentRequest(requirements=reqs))
    provider = MockProvider(default="some plain-language explanation")
    agent_with = QualityAgent("q", provider=provider)
    with_llm = agent_with.run(AgentRequest(requirements=reqs))

    # Deterministic payload is byte-for-byte identical.
    assert without.payload == with_llm.payload
    # The LLM only annotates; it never appears in the no-provider case.
    assert without.llm_annotation is None
    assert with_llm.llm_annotation == "some plain-language explanation"
    # And the provider was actually consulted (augmentative call happened).
    assert any(c.method == "complete" for c in provider.calls)


def test_heterogeneous_providers_per_role_are_used():
    """Each role gets a distinct provider, and each is actually invoked."""
    p_quality = MockProvider(default="Q-MODEL note")
    p_formal = MockProvider(default="F-MODEL note")
    p_trace = MockProvider(default="T-MODEL note")
    coord = Coordinator.with_default_agents(
        providers={
            "quality": p_quality,
            "formalization": p_formal,
            "traceability": p_trace,
        }
    )
    report = coord.dispatch(_reqs())

    # Each agent recorded a provider, and the three are distinct objects.
    assert report.reports["quality"].llm_annotation == "Q-MODEL note"
    assert report.reports["formalization"].llm_annotation == "F-MODEL note"
    assert report.reports["traceability"].llm_annotation == "T-MODEL note"
    # Every provider was actually called exactly once.
    assert len(p_quality.calls) == 1
    assert len(p_formal.calls) == 1
    assert len(p_trace.calls) == 1
    # provider_usage reflects the heterogeneous wiring.
    assert set(report.provider_usage) == {"quality", "formalization", "traceability"}
    assert all(v == "MockProvider" for v in report.provider_usage.values())


def test_traceability_runner_is_injectable():
    """A supplied GraphRunner is used verbatim (the Neo4j substitution seam)."""
    calls: list[str] = []

    def fake_runner(query: str, params: dict) -> list[dict]:
        calls.append(query)
        return []  # no violations -> everything passes

    agent = TraceabilityAgent("traceability", runner=fake_runner)
    report = agent.run(AgentRequest(requirements=_reqs()))
    assert calls, "injected runner should have been invoked"
    # With zero rows every objective passes.
    assert report.payload["passing"] == report.payload["objectives_checked"]
    assert report.payload["violation_count"] == 0


def test_dispatch_results_are_reproducible():
    """Two dispatches of the same dataset yield identical serialisable output."""
    r1 = Coordinator().dispatch(_reqs()).to_dict()
    r2 = Coordinator().dispatch(_reqs()).to_dict()
    assert r1 == r2


def test_base_types_compose_for_a_custom_agent():
    """The Agent ABC + request/report types support a heterogeneous agent."""

    class _Echo(Agent):
        role = "echo"

        def run(self, request: AgentRequest) -> AgentReport:
            return AgentReport(
                agent_name=self.name,
                role=self.role,
                payload={"count": len(request.requirements)},
            )

    coord = Coordinator(agents=[_Echo("echo")])
    report = coord.dispatch(_reqs())
    assert isinstance(report, AssessmentReport)
    assert report.reports["echo"].payload["count"] == 64
