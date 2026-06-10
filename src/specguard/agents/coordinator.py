"""Coordinator — the hierarchical root of the HMAS skeleton (novelty #1).

Scope honesty (per CLAUDE.md)
-----------------------------
This is a **deterministic, synchronous orchestrator**, not a multi-agent
runtime. It registers the three layer-wrapping agents, dispatches a
requirements dataset through them **in a fixed order**, and merges their
uniform :class:`~specguard.agents.base.AgentReport` envelopes into one
:class:`AssessmentReport`. There is no concurrency, no negotiation, no message
passing — those, together with polyglot persistence, are explicit future work.
The artifact validates that the hierarchy (Coordinator over Quality /
Formalization / Traceability) composes behind one interface and that
heterogeneous BYOM models can be wired per agent role.

Heterogeneous models per role
-----------------------------
The Coordinator accepts a ``providers`` mapping (agent name -> ``ModelProvider``)
so each role can run a *different* model — the "heterogeneous models per agent
role with BYOM" claim from architecture.md. A provider is attached to an agent
only if that agent does not already carry one, so explicitly constructed agents
keep their own provider. The merged report records which provider each agent
used, making the heterogeneity observable (and testable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from specguard.llm import ModelProvider

from .base import Agent, AgentReport, AgentRequest
from .formalization_agent import FormalizationAgent
from .quality_agent import QualityAgent
from .traceability_agent import TraceabilityAgent


@dataclass
class AssessmentReport:
    """Combined result of a Coordinator dispatch across all agents.

    Attributes:
        dispatch_order: agent names in the exact order they ran (deterministic).
        reports: per-agent :class:`AgentReport`, keyed by agent name.
        provider_usage: agent name -> provider label (or ``None``), the
            heterogeneous-models-per-role evidence.
    """

    dispatch_order: list[str] = field(default_factory=list)
    reports: dict[str, AgentReport] = field(default_factory=dict)
    provider_usage: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-friendly primitives (drops non-serialisable state).

        The Formalization agent stashes the built ``RequirementGraph`` under the
        private ``_graph`` payload key for in-process reuse; it is excluded here.
        """
        out: dict[str, Any] = {
            "dispatch_order": self.dispatch_order,
            "provider_usage": self.provider_usage,
            "agents": {},
        }
        for name, rep in self.reports.items():
            payload = {k: v for k, v in rep.payload.items() if not k.startswith("_")}
            out["agents"][name] = {
                "role": rep.role,
                "payload": payload,
                "llm_annotation": rep.llm_annotation,
                "used_provider": rep.used_provider,
            }
        return out

    def summary(self) -> str:
        """Human-readable combined summary."""
        lines = ["HMAS Combined Assessment Report", "=" * 40]
        lines.append(f"Dispatch order: {' -> '.join(self.dispatch_order)}")
        lines.append("")
        for name in self.dispatch_order:
            rep = self.reports[name]
            lines.append(f"[{name}] {rep.role}")
            q = rep.payload
            if "aggregate" in q:
                agg = q["aggregate"]
                lines.append(
                    f"  gate PASS/WARN/FAIL: {agg.get('gate_pass')}/"
                    f"{agg.get('gate_warn')}/{agg.get('gate_fail')}  "
                    f"avg overall={agg.get('avg_overall')}"
                )
            if "graph_stats" in q:
                gs = q["graph_stats"]
                lines.append(
                    f"  graph: {gs['total_nodes']} nodes / "
                    f"{gs['total_relationships']} rels  "
                    f"(conflict candidates screened: "
                    f"{q.get('conflict_candidates_screened')})"
                )
            if "objectives_checked" in q:
                lines.append(
                    f"  compliance: {q['passing']}/{q['objectives_checked']} "
                    f"passing ({q['compliance_rate']:.1%}), "
                    f"{q['violation_count']} violations"
                )
            if rep.used_provider:
                lines.append(f"  LLM annotation via: {rep.used_provider}")
            lines.append("")
        return "\n".join(lines)


class Coordinator:
    """Hierarchical root that dispatches a dataset through registered agents."""

    def __init__(self, agents: list[Agent] | None = None) -> None:
        """Construct with an explicit agent list, or build the default three.

        Default order is Quality -> Formalization -> Traceability, matching the
        Layer 1 -> 2 -> 3 progression in architecture.md.
        """
        if agents is None:
            agents = [
                QualityAgent("quality"),
                FormalizationAgent("formalization"),
                TraceabilityAgent("traceability"),
            ]
        self.agents: list[Agent] = list(agents)

    @classmethod
    def with_default_agents(
        cls,
        providers: dict[str, ModelProvider] | None = None,
    ) -> Coordinator:
        """Build the default three-agent hierarchy, optionally wiring providers.

        Args:
            providers: agent name -> ``ModelProvider``. A provider is attached
                to its named agent (enabling that agent's augmentative LLM
                annotation). Demonstrates heterogeneous models per role.
        """
        coord = cls()
        if providers:
            coord.attach_providers(providers)
        return coord

    def attach_providers(self, providers: dict[str, ModelProvider]) -> None:
        """Attach BYOM providers per agent name (only where none is set)."""
        for agent in self.agents:
            if agent.name in providers and agent.provider is None:
                agent.provider = providers[agent.name]
                agent.provider_name = type(providers[agent.name]).__name__

    def dispatch(self, requirements: list[Any]) -> AssessmentReport:
        """Run every agent in registration order, merging their reports.

        Deterministic and sequential. Each agent receives the same requirement
        dataset; cross-agent state (e.g. the built graph) is threaded through
        the shared request ``context`` so a later agent could reuse it.
        """
        request = AgentRequest(requirements=requirements)
        combined = AssessmentReport()
        for agent in self.agents:
            report = agent.run(request)
            combined.dispatch_order.append(agent.name)
            combined.reports[agent.name] = report
            combined.provider_usage[agent.name] = report.used_provider
            # Thread the built graph forward for potential downstream reuse.
            graph = report.payload.get("_graph")
            if graph is not None:
                request.context["graph"] = graph
        return combined
