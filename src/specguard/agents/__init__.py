"""SpecGuard HMAS skeleton — dissertation novelty #1 (interface validation).

This package is a **skeleton validating the HMAS interfaces**; a full HMAS with
polyglot persistence (Neo4j + MongoDB + VectorDB) and asynchronous,
negotiating agents is **future work** (per CLAUDE.md honesty rules). What it
provides is the minimal, deterministic, framework-free composition of the three
SpecGuard layers behind a uniform agent interface, with an optional BYOM model
per agent role:

    Coordinator
    ├── QualityAgent        (Layer 1: deterministic gate + optional LLM analyst)
    ├── FormalizationAgent  (Layer 2: knowledge-graph queries, NetworkX)
    └── TraceabilityAgent   (Layer 3: compliance codification + cross-domain)

It is stdlib-only beyond SpecGuard's own layers and the ``typing``-based BYOM
protocol in :mod:`specguard.llm`; it never imports ``anthropic`` or any
agent-framework dependency, and runs with no Neo4j.
"""

from __future__ import annotations

from .base import Agent, AgentReport, AgentRequest
from .coordinator import AssessmentReport, Coordinator
from .formalization_agent import FormalizationAgent
from .quality_agent import QualityAgent
from .traceability_agent import TraceabilityAgent

__all__ = [
    "Agent",
    "AgentRequest",
    "AgentReport",
    "Coordinator",
    "AssessmentReport",
    "QualityAgent",
    "FormalizationAgent",
    "TraceabilityAgent",
]
