"""Schema for the checkability taxonomy (dissertation Contribution #2, Artifact 1).

The taxonomy classifies each regulatory objective by *how it can be verified*:
its semantic class, the resulting checkability zone, and — when machine- or
screen-checkable — the topological template and decision rule that codify it.

This module is the single source of allowed values plus the zone rule. It is
deliberately **stdlib-only** so it sits on the DO-330-qualifiable side of the
trust boundary (same constraint as :mod:`specguard.core`).

Vocabulary references (definitions live in ``docs/taxonomy.md``):
  - semantic classes — what kind of claim the objective makes;
  - checkability zones — machine / screened / human (derivable from the class);
  - topological templates ``T1``..``T6`` — the graph shapes that codify a claim;
  - decision rules ``DR1``..``DR7`` — the human classification heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass

# Column order of taxonomy/checkability_taxonomy.csv — the dataclass mirrors it.
COLUMNS: tuple[str, ...] = (
    "objective_id",
    "standard",
    "table_section",
    "title",
    "formulation_paraphrase",
    "dal_applicability",
    "semantic_class",
    "checkability_zone",
    "topological_template",
    "template_params",
    "decision_rule",
    "prototype_instance",
    "notes_disputed",
)

SEMANTIC_CLASSES: frozenset[str] = frozenset(
    {
        "structural",
        "structural-consistency",
        "traceability",
        "numerical-consistency",
        "coverage",
        "hybrid",
        "not-machine-checkable",
    }
)

CHECKABILITY_ZONES: frozenset[str] = frozenset({"machine", "screened", "human"})

TOPOLOGICAL_TEMPLATES: frozenset[str] = frozenset(
    {
        "T1-mandatory-edge",
        "T2-disjunctive",
        "T3-coreference-consistency",
        "T4-numerical-aggregation",
        "T5-conjunctive-cross-domain",
        "T6-proxy-screen",
    }
)

DECISION_RULES: frozenset[str] = frozenset({f"DR{i}" for i in range(1, 8)})

VALID_DAL: frozenset[str] = frozenset({"A", "B", "C", "D"})

# Zone rule: which zone a semantic class implies. Pure mapping; the validator
# enforces that the CSV's declared zone agrees with this.
_CLASS_TO_ZONE: dict[str, str] = {
    "structural": "machine",
    "structural-consistency": "machine",
    "traceability": "machine",
    "numerical-consistency": "machine",
    "coverage": "machine",
    "hybrid": "screened",
    "not-machine-checkable": "human",
}


def zone_for_class(semantic_class: str) -> str | None:
    """Return the checkability zone implied by a semantic class.

    Pure function (never raises): returns ``None`` for an unknown class so the
    validator can report the bad enum separately rather than crashing here.
    """
    return _CLASS_TO_ZONE.get(semantic_class)


@dataclass(frozen=True)
class TaxonomyRow:
    """One classified objective — mirrors the CSV columns verbatim (all str)."""

    objective_id: str
    standard: str
    table_section: str
    title: str
    formulation_paraphrase: str
    dal_applicability: str
    semantic_class: str
    checkability_zone: str
    topological_template: str
    template_params: str
    decision_rule: str
    prototype_instance: str
    notes_disputed: str

    def dal_tokens(self) -> list[str]:
        """Parse ``dal_applicability`` into its ``;``-separated tokens."""
        return [t.strip() for t in self.dal_applicability.split(";") if t.strip()]

    @property
    def is_human(self) -> bool:
        """A human-zone row carries no template and no decision rule."""
        return self.checkability_zone == "human"

    @property
    def is_codified(self) -> bool:
        """True when a real ``ComplianceConstraint`` prototype is referenced."""
        return bool(self.prototype_instance.strip())
