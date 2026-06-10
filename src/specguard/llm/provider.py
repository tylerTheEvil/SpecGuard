"""BYOM (Bring Your Own Model) provider protocol.

This module defines the model-provider contract that is the *BYOM interface*
of dissertation novelty #1 (Hierarchical Multi-Agent System with heterogeneous
models per agent role). It is intentionally a structural ``typing.Protocol``,
not an abstract base class: any object that exposes the right methods is a
provider, so a contributor can wire in OpenAI, a local llama.cpp server, or a
test double without inheriting from SpecGuard types or pulling an
agent-framework dependency.

Design decision — two protocols, not one
----------------------------------------
The contract is split into two protocols rather than a single fat one:

* :class:`ModelProvider` — the *minimal* surface. A single ``complete`` method
  returning free text. The rationale: the lowest common denominator across
  every chat/completion backend is "give me text for this prompt". Keeping the
  mandatory surface to one method maximises the set of backends that can serve
  as a BYOM provider with near-zero adapter code.

* :class:`StructuredModelProvider` — an *optional, narrower* capability that
  adds ``complete_structured`` for backends with native guaranteed-JSON output
  (e.g. Anthropic's ``output_config`` JSON-schema mode). Modelling this as a
  second protocol (rather than an optional method on the first) means a plain
  text provider does not have to advertise or stub a structured method, and
  ``isinstance``/``runtime_checkable`` can be used to detect the capability.

Design decision — a universal structured-output fallback
--------------------------------------------------------
Callers (the edge extractor, future agents) want structured output regardless
of whether the supplied provider implements it natively. Forcing every caller
to branch on capability would scatter prompt-and-parse logic. Instead, the
module-level :func:`complete_structured` helper synthesises structured
completion on top of *any* :class:`ModelProvider`:

    1. If the provider natively supports structured output, delegate to it.
    2. Otherwise, append a JSON-only instruction to the system prompt, call
       ``complete``, and parse the result with the stdlib ``json`` module.
    3. On a parse failure, retry exactly once with a terse corrective
       instruction (LLMs frequently fix a single malformed-JSON mistake on a
       second pass). A second failure raises :class:`StructuredOutputError`.

This keeps the BYOM surface minimal while giving every consumer a single,
provider-agnostic structured-output entry point. The fallback is honest about
its limits: it offers *best-effort* JSON, not the hard schema guarantee a
native structured mode provides — documented here so the dissertation does not
overclaim qualifiability of the LLM layer (it is augmentative by design).
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

__all__ = [
    "ModelProvider",
    "StructuredModelProvider",
    "StructuredOutputError",
    "complete_structured",
    "supports_structured",
]


class StructuredOutputError(RuntimeError):
    """Raised when structured (JSON) completion cannot be obtained or parsed.

    Carries the last raw model output in :attr:`raw` to aid debugging of
    malformed responses.
    """

    def __init__(self, message: str, *, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw


@runtime_checkable
class ModelProvider(Protocol):
    """Minimal BYOM contract: turn a prompt into text.

    The single mandatory method any model backend must expose to participate
    in SpecGuard's augmentative LLM layers. ``system`` is an optional system
    prompt; backends without a system-role concept may fold it into the user
    turn.
    """

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's text completion for ``prompt``."""
        ...


@runtime_checkable
class StructuredModelProvider(ModelProvider, Protocol):
    """Optional capability: native guaranteed-JSON completion.

    Providers whose backend supports schema-constrained output (e.g. Anthropic
    ``output_config`` JSON-schema mode) implement this in addition to
    :class:`ModelProvider`. Consumers should not call this directly; use the
    module-level :func:`complete_structured`, which delegates here when the
    capability is present and falls back to prompt-and-parse otherwise.
    """

    def complete_structured(
        self, prompt: str, schema: dict, *, system: str | None = None
    ) -> dict:
        """Return a JSON object conforming to ``schema`` (best-effort native)."""
        ...


def supports_structured(provider: ModelProvider) -> bool:
    """Return ``True`` if ``provider`` advertises native structured output.

    Uses ``runtime_checkable`` protocol membership. Because ``Protocol``
    membership only checks method *presence*, this is a capability hint, not a
    guarantee of correctness — :func:`complete_structured` still validates and
    parses the result.
    """
    return isinstance(provider, StructuredModelProvider)


_JSON_INSTRUCTION = (
    "You must respond with a single valid JSON object and nothing else. "
    "Do not wrap it in Markdown code fences. Do not add commentary before or "
    "after the JSON. The object must conform to this JSON schema:\n{schema}"
)

_RETRY_INSTRUCTION = (
    "Your previous response was not valid JSON. Respond again with ONLY a "
    "single valid JSON object conforming to the schema, no other text."
)


def _strip_code_fence(text: str) -> str:
    """Best-effort removal of Markdown code fences around a JSON payload."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop the opening fence line (``` or ```json) and the closing fence.
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def complete_structured(
    provider: ModelProvider,
    prompt: str,
    schema: dict,
    *,
    system: str | None = None,
) -> dict:
    """Obtain a structured (JSON object) completion from any provider.

    Provider-agnostic entry point used by every SpecGuard LLM consumer. If
    ``provider`` natively supports :class:`StructuredModelProvider`, delegates
    to it. Otherwise synthesises structured output by instructing the model to
    emit JSON, parsing with stdlib ``json``, and retrying once on a parse
    failure (see module docstring for the rationale).

    Raises:
        StructuredOutputError: if the response is not parseable JSON after one
            retry, or parses to a non-object (the contract is a JSON *object*).
    """
    if supports_structured(provider):
        # Static type checkers cannot narrow a runtime isinstance on a Protocol
        # to the subtype method; the runtime guarantee comes from the check.
        return provider.complete_structured(prompt, schema, system=system)  # type: ignore[attr-defined]

    schema_text = json.dumps(schema, indent=2, ensure_ascii=False)
    json_directive = _JSON_INSTRUCTION.format(schema=schema_text)
    augmented_system = json_directive if system is None else f"{system}\n\n{json_directive}"

    raw = provider.complete(prompt, system=augmented_system)
    parsed = _try_parse_object(raw)
    if parsed is not None:
        return parsed

    # One corrective retry. Fold the prior output and the corrective directive
    # into the prompt so the model sees what it produced and what to fix.
    retry_prompt = f"{prompt}\n\nYour previous output was:\n{raw}\n\n{_RETRY_INSTRUCTION}"
    raw_retry = provider.complete(retry_prompt, system=augmented_system)
    parsed_retry = _try_parse_object(raw_retry)
    if parsed_retry is not None:
        return parsed_retry

    raise StructuredOutputError(
        "Provider did not return valid JSON after one retry.",
        raw=raw_retry,
    )


def _try_parse_object(raw: str) -> dict | None:
    """Parse ``raw`` to a JSON object, or return ``None`` if not possible."""
    try:
        value = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    return value
