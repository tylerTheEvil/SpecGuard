"""Formalization Agent — wraps Layer 2 (knowledge graph build + queries).

Builds the property graph from the requirements (and their smell results) and
runs a representative subset of the NetworkX-backed queries from
``specguard.graph.queries``. No Neo4j is required: the in-memory NetworkX
mirror is sufficient for interface validation, and keeps plain ``pytest`` green
without a database.

The built ``RequirementGraph`` is placed into ``AgentReport.payload`` and also
threaded back through ``AgentRequest.context`` by the Coordinator, so a later
agent could reuse it rather than rebuild — demonstrating the cross-agent state
channel of the request type.

LLM role here is intentionally minimal: graph construction is deterministic
(pattern-based entity extraction in ``builder.py``), so the optional provider
only annotates the resulting topology. Detection/formalization never depends on
it — same augmentative contract as the Quality Agent.
"""

from __future__ import annotations

from specguard.core import assess_dataset
from specguard.graph.builder import build_graph
from specguard.graph.queries import (
    graph_to_networkx,
    q6_cross_cutting_requirements,
    q8_safety_critical_with_smells,
    q14_potential_conflicts,
)

from .base import Agent, AgentReport, AgentRequest


class FormalizationAgent(Agent):
    """Wraps the Layer 2 knowledge graph (NetworkX, no Neo4j requirement)."""

    role = "Formalization Agent (Layer 2 knowledge-graph queries)"

    def run(self, request: AgentRequest) -> AgentReport:
        smell_results = assess_dataset(request.requirements)
        rg = build_graph(request.requirements, smell_results)
        g = graph_to_networkx(rg)

        stats = rg.stats()
        cross_cutting = q6_cross_cutting_requirements(g)
        safety_with_smells = q8_safety_critical_with_smells(g)
        conflict_candidates = q14_potential_conflicts(g)

        payload = {
            "graph_stats": stats,
            # Q14 is a topological screening filter, NOT conflict detection
            # (per CLAUDE.md / architecture.md) — keep the honest label.
            "conflict_candidates_screened": len(conflict_candidates),
            "cross_cutting_count": len(cross_cutting),
            "safety_critical_with_smells": safety_with_smells,
            # Expose the built graph so the Coordinator can thread it forward.
            "_graph": rg,
        }

        annotation: str | None = None
        used_provider: str | None = None
        if self.provider is not None:
            prompt = (
                "A requirements knowledge graph was built deterministically "
                f"with {stats['total_nodes']} nodes and "
                f"{stats['total_relationships']} relationships. "
                f"{len(cross_cutting)} requirements span 2+ components and "
                f"{len(conflict_candidates)} requirement pairs were screened "
                "as conflict candidates (topological screening, not confirmed "
                "conflicts). Summarise the graph's shape in one short paragraph."
            )
            annotation = self.provider.complete(
                prompt,
                system="You are an augmentative analyst describing a graph; "
                "you never alter its computed structure.",
            )
            used_provider = self.provider_name

        return AgentReport(
            agent_name=self.name,
            role=self.role,
            payload=payload,
            llm_annotation=annotation,
            used_provider=used_provider,
        )
