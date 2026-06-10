"""Anthropic concrete BYOM provider.

Implements both :class:`~specguard.llm.provider.ModelProvider` and
:class:`~specguard.llm.provider.StructuredModelProvider` over the official
``anthropic`` SDK. This is one reference adapter for the BYOM interface — the
architecture deliberately does not privilege any single vendor; a contributor
can drop in another provider by satisfying the same protocol.

The ``anthropic`` import is lazy and guarded: importing this module costs
nothing, and the helpful install hint only fires when a provider is actually
instantiated without the package present. This keeps the deterministic core
(and plain ``pytest``) working with no extras installed.

SDK usage notes (current as of 2026-06; do not "modernise" from stale memory):

* ``anthropic.Anthropic()`` resolves ``ANTHROPIC_API_KEY`` from the
  environment automatically — keys are never passed or stored here.
* No ``temperature`` / ``top_p`` / ``top_k`` (current Opus models 400 on
  these) and no assistant-turn prefills.
* Native structured output uses
  ``output_config={"format": {"type": "json_schema", "schema": ...}}``; the
  schema must carry ``additionalProperties: false`` on every object and avoid
  ``minLength`` / ``maximum``-style constraints. The SDK auto-retries 429/5xx.
"""

from __future__ import annotations

import json

DEFAULT_MODEL = "claude-opus-4-8"

_INSTALL_HINT = (
    "AnthropicProvider requires the 'anthropic' package.\n"
    "Install the SpecGuard LLM extra with:\n"
    "    pip install -e '.[llm]'\n"
    "and ensure ANTHROPIC_API_KEY is set in the environment."
)


class AnthropicProvider:
    """BYOM provider backed by the Anthropic Messages API.

    Args:
        model: model id (default ``claude-opus-4-8``; cheaper alternatives
            include ``claude-sonnet-4-6`` and ``claude-haiku-4-5``).
        max_tokens: response token budget per call.
        client: optional pre-built ``anthropic.Anthropic`` client (mainly for
            injection in tests); if omitted, one is constructed lazily on first
            use, which is when the missing-package hint would fire.

    The constructor imports ``anthropic`` eagerly so that the install hint
    surfaces at the point of instantiation (a clear failure site) rather than
    deep inside a later ``complete`` call.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        max_tokens: int = 4096,
        client: object | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            try:
                import anthropic  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(_INSTALL_HINT) from exc
            self._client = anthropic.Anthropic()

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's text completion for ``prompt``."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return _extract_text(response)

    def complete_structured(
        self, prompt: str, schema: dict, *, system: str | None = None
    ) -> dict:
        """Return a JSON object using Anthropic's native schema-constrained mode.

        Uses ``output_config`` JSON-schema output. The returned text is still
        parsed defensively with stdlib ``json`` — native mode guarantees schema
        shape, not that downstream code skips validation.
        """
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        if system is not None:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        text = _extract_text(response)
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("Native structured output did not return a JSON object.")
        return value


def _extract_text(response: object) -> str:
    """Pull the first text block out of a Messages API response.

    The API returns ``response.content`` as a list of typed blocks; structured
    text lives in blocks whose ``type == "text"``.
    """
    content = response.content  # type: ignore[attr-defined]
    return next(block.text for block in content if block.type == "text")
