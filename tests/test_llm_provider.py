"""Tests for the BYOM provider protocol (Phase 3a).

Covers protocol conformance, the structured-output fallback helper (including
the parse-retry path), and the lazy/guarded ``anthropic`` import. All tests run
WITHOUT the ``anthropic`` package installed — the only test that touches the
concrete provider injects a fake client or simulates the import failure.
"""

from __future__ import annotations

import builtins

import pytest

from specguard.llm import (
    ModelProvider,
    StructuredModelProvider,
    complete_structured,
    supports_structured,
)
from specguard.llm.mock_provider import MockProvider
from specguard.llm.provider import StructuredOutputError

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_mock_is_model_provider():
    mock = MockProvider(default="hi")
    assert isinstance(mock, ModelProvider)
    assert mock.complete("anything") == "hi"


def test_plain_mock_is_not_structured_provider():
    mock = MockProvider(default="hi")
    assert not isinstance(mock, StructuredModelProvider)
    assert supports_structured(mock) is False


def test_native_mock_is_structured_provider():
    mock = MockProvider(native_structured=True, default='{"a": 1}')
    assert isinstance(mock, StructuredModelProvider)
    assert supports_structured(mock) is True


def test_substring_routing_and_queue():
    mock = MockProvider(responses={"foo": "FOO", "bar": "BAR"}, default="D")
    assert mock.complete("a foo b") == "FOO"
    assert mock.complete("no match") == "D"
    q = MockProvider(queue=["one", "two"], default="D")
    assert q.complete("x") == "one"
    assert q.complete("x") == "two"
    assert q.complete("x") == "D"


# ---------------------------------------------------------------------------
# Structured-output fallback helper
# ---------------------------------------------------------------------------


def test_fallback_parses_plain_json():
    mock = MockProvider(default='{"k": "v"}')
    result = complete_structured(mock, "prompt", {"type": "object"})
    assert result == {"k": "v"}
    # The JSON directive must have been injected into the system prompt.
    assert "JSON" in (mock.calls[0].system or "")


def test_fallback_strips_code_fence():
    mock = MockProvider(default='```json\n{"k": 1}\n```')
    assert complete_structured(mock, "p", {"type": "object"}) == {"k": 1}


def test_fallback_retry_on_parse_failure():
    # First response is junk, second is valid -> one retry succeeds.
    mock = MockProvider(queue=["not json at all", '{"ok": true}'])
    result = complete_structured(mock, "p", {"type": "object"})
    assert result == {"ok": True}
    assert len(mock.calls) == 2  # original + one retry


def test_fallback_raises_after_failed_retry():
    mock = MockProvider(queue=["junk", "still junk"])
    with pytest.raises(StructuredOutputError) as exc:
        complete_structured(mock, "p", {"type": "object"})
    assert exc.value.raw == "still junk"
    assert len(mock.calls) == 2


def test_fallback_rejects_non_object_json():
    # Valid JSON, but an array, not an object -> treated as parse failure.
    mock = MockProvider(queue=["[1, 2, 3]", "[4, 5]"])
    with pytest.raises(StructuredOutputError):
        complete_structured(mock, "p", {"type": "object"})


def test_native_path_used_when_available():
    mock = MockProvider(native_structured=True, default='{"native": true}')
    result = complete_structured(mock, "p", {"type": "object"})
    assert result == {"native": True}
    # Native path records a complete_structured call, not a plain complete.
    assert mock.calls[-1].method == "complete_structured"


# ---------------------------------------------------------------------------
# Lazy / guarded anthropic import
# ---------------------------------------------------------------------------


def test_anthropic_provider_with_injected_client():
    """Injecting a client avoids importing anthropic at all."""
    from specguard.llm.anthropic_provider import AnthropicProvider

    class _Block:
        type = "text"
        text = '{"edges": []}'

    class _Resp:
        content = [_Block()]

    class _Messages:
        def create(self, **kwargs):
            _Messages.last_kwargs = kwargs
            return _Resp()

    class _FakeClient:
        messages = _Messages()

    provider = AnthropicProvider(client=_FakeClient(), model="claude-haiku-4-5")
    assert provider.complete("hello", system="sys") == '{"edges": []}'
    # No temperature/top_p/top_k may be passed.
    kw = _Messages.last_kwargs
    assert "temperature" not in kw and "top_p" not in kw and "top_k" not in kw
    assert kw["model"] == "claude-haiku-4-5"
    assert kw["system"] == "sys"

    # Native structured path uses output_config.
    structured = provider.complete_structured("p", {"type": "object"})
    assert structured == {"edges": []}
    assert "output_config" in _Messages.last_kwargs


def test_anthropic_import_error_is_helpful(monkeypatch):
    """Instantiating without the anthropic package raises a helpful hint."""
    from specguard.llm import anthropic_provider

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic" or name.startswith("anthropic."):
            raise ImportError("No module named 'anthropic'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError) as exc:
        anthropic_provider.AnthropicProvider()
    assert ".[llm]" in str(exc.value)


def test_core_imports_without_extras():
    """The protocol module imports with no extras installed."""
    import importlib

    mod = importlib.import_module("specguard.llm.provider")
    assert hasattr(mod, "ModelProvider")
    assert hasattr(mod, "complete_structured")
