"""Agent base abstractions for the HMAS skeleton (dissertation novelty #1).

Scope honesty (per CLAUDE.md)
-----------------------------
This module is a **skeleton validating the HMAS interfaces**, not a
multi-agent runtime. There is no agent framework, no message bus, no async
orchestration, and no polyglot persistence — those remain **future work**.
What this package *does* establish is that the three SpecGuard layers
(deterministic detection, knowledge graph, compliance codification) compose
behind a single, typed, heterogeneous-agent interface, and that an optional
BYOM model can be attached per agent role without touching the
DO-330-qualifiable deterministic path. That composition is the architectural
claim novelty #1 makes; this code is the minimal artifact that exercises it.

Design decisions
----------------
* **Dataclass request/report types, not free-form dicts.** ``AgentRequest``
  and ``AgentReport`` are dataclasses so heterogeneous agents (whose internal
  payloads differ wildly — gate results vs. graph stats vs. compliance
  violations) compose under one return type. The variable part lives in the
  untyped ``payload`` dict; the invariant part (which agent ran, its role,
  whether an LLM annotation was attached) is typed. This mirrors the
  ``ModelProvider`` design choice in ``specguard.llm.provider``: keep the
  mandatory surface tiny, push capability-specific detail into an optional
  channel.

* **One ``run(request) -> AgentReport`` method.** A single abstract method is
  the lowest common denominator across the three agents. The Coordinator only
  needs this; anything richer would couple it to a specific agent's internals.

* **``Agent`` is an ABC, not a Protocol.** Unlike ``ModelProvider`` (which must
  accept third-party objects it does not own), every agent here is a SpecGuard
  type, so inheritance buys shared construction (name/role/provider wiring)
  with no downside.

* **LLM is strictly optional and augmentative.** An agent may carry a
  ``ModelProvider`` (the BYOM channel). The contract — enforced structurally by
  ``QualityAgent`` — is that deterministic results are computed *before and
  independently of* any LLM call; the model only annotates. Detection never
  depends on the model, preserving DO-330 qualifiability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from specguard.llm import ModelProvider


@dataclass
class AgentRequest:
    """A unit of work dispatched to an agent.

    The dataset travels as a plain object list (CVA6 ``Requirement`` objects in
    the demo) under ``requirements``; ``context`` carries any cross-agent state
    the Coordinator threads through (e.g. a built graph reused by a later
    agent). Keeping both generic lets one request type serve every agent role.
    """

    requirements: list[Any]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentReport:
    """A typed, uniform result envelope returned by every agent.

    Attributes:
        agent_name: stable identifier of the producing agent.
        role: human-readable role description (matches architecture.md).
        payload: agent-specific structured result (gate results, graph stats,
            compliance summary). Deliberately untyped — this is the
            heterogeneous channel.
        llm_annotation: optional plain-language note produced by an attached
            BYOM provider. ``None`` whenever no provider is attached. This field
            is *augmentative only*: nothing in ``payload`` is derived from it.
        used_provider: identifier of the provider that produced
            ``llm_annotation`` (for the heterogeneous-models-per-role evidence),
            or ``None``.
    """

    agent_name: str
    role: str
    payload: dict[str, Any] = field(default_factory=dict)
    llm_annotation: str | None = None
    used_provider: str | None = None


class Agent(ABC):
    """Base class for a SpecGuard HMAS agent.

    Each agent wraps exactly one SpecGuard layer and exposes it through the
    uniform ``run`` interface. An optional ``ModelProvider`` is the per-role
    BYOM channel; when ``None`` the agent is fully deterministic.
    """

    #: Subclasses set a stable role description matching architecture.md.
    role: str = "generic agent"

    def __init__(
        self,
        name: str,
        *,
        provider: ModelProvider | None = None,
        provider_name: str | None = None,
    ) -> None:
        """Construct an agent.

        Args:
            name: stable agent identifier used in reports and dispatch order.
            provider: optional BYOM model for the augmentative LLM annotation.
            provider_name: label recorded in the report when ``provider`` is
                used (lets the Coordinator demonstrate distinct models per
                role). Defaults to the provider's class name.
        """
        self.name = name
        self.provider = provider
        self.provider_name = provider_name or (
            type(provider).__name__ if provider is not None else None
        )

    @abstractmethod
    def run(self, request: AgentRequest) -> AgentReport:
        """Process ``request`` and return a uniform :class:`AgentReport`."""
        raise NotImplementedError
