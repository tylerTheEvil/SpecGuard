"""Aggregate statistics over taxonomy rows — the numeric backbone of the
coverage map. Stdlib-only.
"""

from __future__ import annotations

from collections import Counter

from specguard.taxonomy.schema import TaxonomyRow

# Bucket the (sometimes compound) ``standard`` field into the three families
# the coverage map reports on.
_PRIMARY_STANDARDS = ("DO-178C", "DO-254")


def standard_family(standard: str) -> str:
    """Map a row's ``standard`` to one of DO-178C / DO-254 / cross-domain.

    Cross-domain objectives carry compound standard strings
    (e.g. ``ARP4754A+DO-178C+DO-254``); anything that is not exactly a single
    primary standard is bucketed as ``cross-domain``.
    """
    return standard if standard in _PRIMARY_STANDARDS else "cross-domain"


def compute_stats(rows: list[TaxonomyRow]) -> dict[str, object]:
    """Return counts per standard family / zone / class / template plus totals."""
    by_standard: Counter[str] = Counter()
    by_zone: Counter[str] = Counter()
    by_semantic_class: Counter[str] = Counter()
    by_template: Counter[str] = Counter()

    codified = 0
    for row in rows:
        by_standard[standard_family(row.standard)] += 1
        by_zone[row.checkability_zone] += 1
        by_semantic_class[row.semantic_class] += 1
        if row.topological_template:
            by_template[row.topological_template] += 1
        if row.is_codified:
            codified += 1

    return {
        "total": len(rows),
        "codified": codified,
        "classified_only": len(rows) - codified,
        "distinct_templates": len(by_template),
        "by_standard": dict(by_standard),
        "by_zone": dict(by_zone),
        "by_semantic_class": dict(by_semantic_class),
        "by_template": dict(by_template),
    }


def zone_counts_by_standard(rows: list[TaxonomyRow]) -> dict[str, dict[str, int]]:
    """Per-standard-family zone breakdown, e.g. ``{'DO-178C': {'machine': 6, ...}}``.

    Used by the coverage-map figure; every family carries all three zone keys
    (zero-filled) so the stacked-bar segments line up.
    """
    families = ("DO-178C", "DO-254", "cross-domain")
    zones = ("machine", "screened", "human")
    table: dict[str, dict[str, int]] = {fam: dict.fromkeys(zones, 0) for fam in families}
    for row in rows:
        fam = standard_family(row.standard)
        if row.checkability_zone in table[fam]:
            table[fam][row.checkability_zone] += 1
    return table
