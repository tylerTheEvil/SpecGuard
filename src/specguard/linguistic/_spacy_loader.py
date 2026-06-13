"""Lazy spaCy model loader with caching and actionable error messages."""

from __future__ import annotations

_NLP_CACHE: dict[str, object] = {}

_MODEL_NAME = "en_core_web_sm"

_INSTALL_HINT = (
    "The SpecGuard linguistic extra requires spaCy and the en_core_web_sm model.\n"
    "Install with:\n"
    "    pip install -e '.[linguistic]'\n"
    "    python -m spacy download en_core_web_sm"
)


def load_nlp(model: str = _MODEL_NAME):
    """Return a cached spaCy Language object, loading on first call.

    Raises ImportError with install instructions if spaCy or the model
    is not available.
    """
    if model in _NLP_CACHE:
        return _NLP_CACHE[model]

    try:
        import spacy  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(_INSTALL_HINT) from exc

    try:
        nlp = spacy.load(model)
    except OSError as exc:
        raise ImportError(
            f"spaCy model '{model}' not found.\n{_INSTALL_HINT}"
        ) from exc

    _NLP_CACHE[model] = nlp
    return nlp
