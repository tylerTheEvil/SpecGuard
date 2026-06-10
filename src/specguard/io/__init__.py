"""SpecGuard requirement input parsers (stdlib-only).

This subpackage turns engineer-supplied requirement files (plain text,
Markdown tables, CSV) into the lightweight requirement objects the Layer 1
pipeline consumes. It is part of the deterministic tool surface driven by the
``specguard`` CLI and stays stdlib-only so it imports with no optional extras.

Deliberately NOT supported: ReqIF / DOORS / Polarion native formats. Those are
a separate work item (a rabbit hole); the CLI targets the lowest-common-
denominator exchange formats an engineer can produce in seconds.
"""

from __future__ import annotations

from specguard.io.parsers import (
    ParsedRequirement,
    ParseError,
    parse_requirements,
)

__all__ = [
    "ParseError",
    "ParsedRequirement",
    "parse_requirements",
]
