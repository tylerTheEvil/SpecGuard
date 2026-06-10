"""SpecGuard BYOM (Bring Your Own Model) layer — optional research extension.

This package is the concrete artifact behind dissertation novelty #1's
*BYOM interface*: a minimal, framework-agnostic provider protocol that lets a
heterogeneous model be plugged into any LLM-augmentative layer (edge
extraction in Phase 3b, the Quality/Formalization/Traceability agents in
Phase 4) without coupling the deterministic, DO-330-qualifiable core to any
vendor SDK.

Install the extra before using a concrete provider:

    pip install -e '.[llm]'

The protocol itself (:mod:`specguard.llm.provider`) is pure ``typing`` and
imports with no extras — only the concrete :class:`AnthropicProvider` requires
the ``anthropic`` package, and that import is lazy/guarded.

Design note (feeds the dissertation): the BYOM contract is deliberately split
into a *minimal* :class:`ModelProvider` (one method, ``complete``) and an
*optional* :class:`StructuredModelProvider` (``complete_structured``). The
split keeps the mandatory surface a provider must implement as small as
possible — anything that can return text qualifies as a model provider — while
still exposing native structured-output capabilities where a backend has them.
A module-level :func:`complete_structured` fallback synthesises structured
completion on top of *any* plain ``ModelProvider`` (ask for JSON, parse with
stdlib ``json``, one retry on parse failure), so callers never have to branch
on whether a given provider supports structured output natively.
"""

from __future__ import annotations

from specguard.llm.provider import (
    ModelProvider,
    StructuredModelProvider,
    complete_structured,
    supports_structured,
)

__all__ = [
    "ModelProvider",
    "StructuredModelProvider",
    "complete_structured",
    "supports_structured",
]
