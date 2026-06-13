"""Deterministic mock BYOM provider for tests and offline smoke runs.

:class:`MockProvider` satisfies :class:`~specguard.llm.provider.ModelProvider`
and, when constructed with ``native_structured=True``, also
:class:`~specguard.llm.provider.StructuredModelProvider`. It carries no network
dependency, so the entire LLM-augmentative stack — protocol, fallback helper,
edge extractor, review queue — is exercisable in CI with no API key and
without the ``anthropic`` package installed.

Two complementary response strategies are supported:

* **Substring routing** (``responses``): a mapping of prompt substrings to
  canned responses; the first key found in the prompt wins. Useful for
  per-input fixtures in the extractor tests.
* **Response queue** (``queue``): an ordered list popped left-to-right on each
  call, independent of prompt content. Useful for scripting multi-step flows
  such as the parse-failure-then-retry path of the structured fallback.

If neither matches/remains, ``default`` is returned. Every call is recorded in
:attr:`calls` for assertions.

Implementation note: ``complete_structured`` is **not** a class method. It is
bound onto the instance only when ``native_structured=True``. Because
``ModelProvider`` / ``StructuredModelProvider`` are ``runtime_checkable``
protocols that test for *attribute presence*, this is what lets
``supports_structured(mock)`` correctly report ``False`` for a plain mock and
``True`` for a native one — i.e. the mock can faithfully simulate both a
text-only backend (forcing the prompt-and-parse fallback) and a structured-
capable backend.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass


@dataclass
class _Call:
    """One recorded invocation of the provider."""

    method: str
    prompt: str
    system: str | None


class MockProvider:
    """Configurable, deterministic stand-in for a real model backend.

    Args:
        responses: substring -> canned-response map (substring routing).
        queue: ordered responses popped per call (overrides substring routing
            while non-empty).
        default: response when neither routing matches.
        native_structured: if ``True``, a ``complete_structured`` method is
            bound onto the instance (exercises the native structured path); if
            ``False``, no such method exists, forcing callers through the
            prompt-and-parse fallback in :func:`specguard.llm.complete_structured`.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        *,
        queue: list[str] | None = None,
        default: str = "",
        native_structured: bool = False,
    ) -> None:
        self.responses = responses or {}
        self._queue: deque[str] = deque(queue or [])
        self.default = default
        self.calls: list[_Call] = []
        self.native_structured = native_structured
        if native_structured:
            # Bind the structured implementation onto this instance only.
            self.complete_structured = self._complete_structured_impl  # type: ignore[attr-defined]

    def _resolve(self, prompt: str) -> str:
        if self._queue:
            return self._queue.popleft()
        for needle, response in self.responses.items():
            if needle in prompt:
                return response
        return self.default

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append(_Call("complete", prompt, system))
        return self._resolve(prompt)

    def _complete_structured_impl(
        self, prompt: str, schema: dict, *, system: str | None = None
    ) -> dict:
        self.calls.append(_Call("complete_structured", prompt, system))
        raw = self._resolve(prompt)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("MockProvider structured response was not a JSON object.")
        return value
