"""Checkability taxonomy (dissertation Contribution #2).

A machine-readable classification of regulatory objectives by *how they can be
verified* — semantic class, checkability zone (machine / screened / human),
topological template, and decision rule. The CSV at ``taxonomy/`` is the
human-editable source of truth; this package only reads and validates it.

Stdlib-only: importable and runnable under the DO-330-qualifiable core (no
extras). The coverage-map *figure* generator lives in ``scripts/`` behind the
``[viz]`` extra and is never imported from here.
"""

from __future__ import annotations

from specguard.taxonomy.loader import load_taxonomy
from specguard.taxonomy.schema import (
    CHECKABILITY_ZONES,
    COLUMNS,
    DECISION_RULES,
    SEMANTIC_CLASSES,
    TOPOLOGICAL_TEMPLATES,
    VALID_DAL,
    TaxonomyRow,
    zone_for_class,
)
from specguard.taxonomy.stats import compute_stats, standard_family, zone_counts_by_standard
from specguard.taxonomy.validate import ValidationError, validate

__all__ = [
    "CHECKABILITY_ZONES",
    "COLUMNS",
    "DECISION_RULES",
    "SEMANTIC_CLASSES",
    "TOPOLOGICAL_TEMPLATES",
    "VALID_DAL",
    "TaxonomyRow",
    "ValidationError",
    "compute_stats",
    "load_taxonomy",
    "standard_family",
    "validate",
    "zone_counts_by_standard",
    "zone_for_class",
]
