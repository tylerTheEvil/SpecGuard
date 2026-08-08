"""Ollama concrete BYOM provider — locally hosted open-weights models.

Implements both :class:`~specguard.llm.provider.ModelProvider` and
:class:`~specguard.llm.provider.StructuredModelProvider` against an Ollama
server's HTTP API (``/api/chat``). This is the second reference adapter for
the BYOM interface and the one that demonstrates the interface's point:
a locally hosted open-weights model slots into every LLM-augmentative layer
with no vendor SDK and no API key.

Design decision — stdlib only (``urllib``), no ``ollama`` client package
------------------------------------------------------------------------
The official ``ollama`` Python package would add a third-party dependency for
what is a single JSON-over-HTTP call. Using ``urllib.request`` keeps this
adapter importable with no extras installed, consistent with the
optional-extra quarantine pattern: the only external requirement is a
*running server*, and that failure mode is reported with a clear start-up
hint rather than an ImportError.

Design decision — native structured output via ``format``
---------------------------------------------------------
Ollama (>= 0.5) supports grammar-constrained decoding: passing a JSON schema
as the ``format`` field forces the sampler itself to emit conforming JSON.
This adapter therefore implements :class:`StructuredModelProvider` rather
than relying on the prompt-and-parse fallback — for small local models the
fallback's parse-failure path is a real risk (one malformed response after
one retry aborts a whole extraction run), while constrained decoding makes
malformed JSON structurally impossible. The result is still parsed
defensively with stdlib ``json``.

Determinism note: ``temperature`` defaults to 0 and ``seed`` to 42 (matching
the seeded-faults experiments) so that evaluation runs are repeatable; these
are provider defaults, not a claim that the LLM layer is qualifiable — it
remains augmentative by design.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://localhost:11434"

_CONNECT_HINT = (
    "Could not reach the Ollama server at {url}.\n"
    "Start it with `ollama serve` (or the Ollama desktop app) and ensure the "
    "model is pulled (`ollama list`). The URL can be overridden via the "
    "SPECGUARD_OLLAMA_URL environment variable or the base_url argument."
)

# The extraction prompt carries the full entity inventory (components,
# standards, and every requirement id). Ollama silently truncates prompts that
# exceed the context window, which would surface as spurious evidence-guard
# rejections rather than an error — so the default context is set well above
# the largest SpecGuard prompt instead of trusting the model's default.
_DEFAULT_OPTIONS: dict = {"temperature": 0, "num_ctx": 8192, "seed": 42}


class OllamaProvider:
    """BYOM provider backed by a local Ollama server.

    Args:
        model: Ollama model name as shown by ``ollama list``
            (e.g. ``gemma4:latest``). No default — unlike a vendor API there
            is no canonical model; the caller must name one that is pulled.
        base_url: server URL; defaults to ``SPECGUARD_OLLAMA_URL`` from the
            environment, then ``http://localhost:11434``.
        timeout: per-request timeout in seconds. Local inference on consumer
            hardware is slow; the default is generous rather than snappy.
        options: Ollama sampler options merged over the defaults
            (``temperature: 0``, ``num_ctx: 8192``, ``seed: 42``).
    """

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        timeout: float = 300.0,
        options: dict | None = None,
    ) -> None:
        self.model = model
        self.base_url = (
            base_url
            or os.environ.get("SPECGUARD_OLLAMA_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout
        self.options = {**_DEFAULT_OPTIONS, **(options or {})}

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's text completion for ``prompt``."""
        response = self._chat(prompt, system=system, fmt=None)
        return response

    def complete_structured(
        self, prompt: str, schema: dict, *, system: str | None = None
    ) -> dict:
        """Return a JSON object using Ollama's schema-constrained decoding."""
        text = self._chat(prompt, system=system, fmt=schema)
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("Native structured output did not return a JSON object.")
        return value

    def _chat(self, prompt: str, *, system: str | None, fmt: dict | None) -> str:
        """POST one ``/api/chat`` request and return the message content."""
        messages: list[dict] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": self.options,
        }
        if fmt is not None:
            payload["format"] = fmt

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Ollama request failed (HTTP {exc.code}): {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(_CONNECT_HINT.format(url=self.base_url)) from exc

        message = body.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise RuntimeError(
                f"Unexpected Ollama response shape: {json.dumps(body)[:500]}"
            )
        return message["content"]
