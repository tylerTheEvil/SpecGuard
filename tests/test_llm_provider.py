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


# ---------------------------------------------------------------------------
# Ollama provider (stdlib-only; server faked by patching urlopen)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def read(self):
        import json

        return json.dumps(self._body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(monkeypatch, content: str):
    """Fake urlopen returning an Ollama chat body; captures the Request."""
    import json

    captured: dict = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse({"message": {"role": "assistant", "content": content}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return captured


def test_ollama_is_structured_provider():
    from specguard.llm.ollama_provider import OllamaProvider

    provider = OllamaProvider("gemma4:latest")
    assert isinstance(provider, ModelProvider)
    assert supports_structured(provider) is True


def test_ollama_complete_payload_and_result(monkeypatch):
    from specguard.llm.ollama_provider import OllamaProvider

    captured = _patch_urlopen(monkeypatch, "hello back")
    provider = OllamaProvider("gemma4:latest")
    assert provider.complete("hi", system="sys") == "hello back"

    payload = captured["payload"]
    assert payload["model"] == "gemma4:latest"
    assert payload["stream"] is False
    assert "format" not in payload
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    # Deterministic defaults and the truncation-guard context size. The seed
    # matches the seeded-faults experiments (42) for cross-experiment
    # consistency; together with temperature 0 it pins eval reproducibility.
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["seed"] == 42
    assert captured["url"].endswith("/api/chat")


def test_ollama_structured_passes_schema_as_format(monkeypatch):
    from specguard.llm.ollama_provider import OllamaProvider

    captured = _patch_urlopen(monkeypatch, '{"edges": []}')
    provider = OllamaProvider("gemma4:latest")
    schema = {"type": "object", "properties": {"edges": {"type": "array"}}}
    assert provider.complete_structured("p", schema) == {"edges": []}
    assert captured["payload"]["format"] == schema


def test_ollama_structured_rejects_non_object(monkeypatch):
    from specguard.llm.ollama_provider import OllamaProvider

    _patch_urlopen(monkeypatch, "[1, 2]")
    provider = OllamaProvider("gemma4:latest")
    with pytest.raises(ValueError):
        provider.complete_structured("p", {"type": "object"})


def test_ollama_unreachable_server_hint(monkeypatch):
    import urllib.error

    from specguard.llm.ollama_provider import OllamaProvider

    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaProvider("gemma4:latest")
    with pytest.raises(RuntimeError) as exc:
        provider.complete("hi")
    assert "ollama serve" in str(exc.value)


def test_ollama_base_url_env_override(monkeypatch):
    from specguard.llm.ollama_provider import OllamaProvider

    monkeypatch.setenv("SPECGUARD_OLLAMA_URL", "http://example.org:9999/")
    captured = _patch_urlopen(monkeypatch, "ok")
    provider = OllamaProvider("gemma4:latest")
    provider.complete("hi")
    assert captured["url"] == "http://example.org:9999/api/chat"
