"""Scoped project checks, independent of optional graph and LLM packages."""

from .results import CheckResult, CheckStatus, summarize

__all__ = ["CheckResult", "CheckStatus", "summarize"]
