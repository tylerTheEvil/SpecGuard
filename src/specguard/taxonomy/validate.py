"""Validate taxonomy rows against the schema and the compliance modules.

Returns structured :class:`ValidationError` records; never raises on a data
problem — the CLI decides exit codes. Checks performed:

  (a) enum membership of semantic_class / checkability_zone /
      topological_template / decision_rule;
  (b) zone <-> class consistency via :func:`zone_for_class`;
  (c) human rows carry no template/decision_rule; non-human rows carry both;
  (d) dal_applicability tokens subset of {A,B,C,D};
  (e) objective_id uniqueness;
  (f) FK integrity: every non-empty prototype_instance resolves to a real
      ``ComplianceConstraint`` whose ``.objective_id`` equals the row's id.

The FK check imports the named compliance module lazily. The compliance
modules are stdlib-only, so this works with no extras; any import failure is
reported as a validation error rather than crashing.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from specguard.taxonomy.schema import (
    CHECKABILITY_ZONES,
    DECISION_RULES,
    SEMANTIC_CLASSES,
    TOPOLOGICAL_TEMPLATES,
    VALID_DAL,
    TaxonomyRow,
    zone_for_class,
)


@dataclass(frozen=True)
class ValidationError:
    """A single validation problem, attributed to a row and field."""

    objective_id: str
    field: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"objective_id": self.objective_id, "field": self.field, "message": self.message}


def _module_name_for(prototype_instance: str) -> str:
    """Map the ``<module>::SYMBOL`` left side to an importable module name.

    Accepts a file-path form (``compliance/do178c.py``) or a dotted form
    (``specguard.compliance.do178c`` / ``compliance.do178c``); always returns a
    fully-qualified ``specguard.*`` module name.
    """
    mod = prototype_instance.split("::", 1)[0].strip()
    if mod.endswith(".py"):
        mod = mod[:-3]
    mod = mod.replace("/", ".").replace("\\", ".").strip(".")
    if not mod.startswith("specguard."):
        mod = f"specguard.{mod}"
    return mod


def _check_fk(row: TaxonomyRow) -> list[ValidationError]:
    """Resolve prototype_instance and confirm the constraint id matches."""
    spec = row.prototype_instance.strip()
    if "::" not in spec:
        return [
            ValidationError(
                row.objective_id,
                "prototype_instance",
                f"malformed reference {spec!r}; expected '<module>::SYMBOL'",
            )
        ]
    module_name = _module_name_for(spec)
    symbol = spec.split("::", 1)[1].strip()
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        return [
            ValidationError(
                row.objective_id,
                "prototype_instance",
                f"cannot import module {module_name!r}: {exc}",
            )
        ]
    constraint = getattr(module, symbol, None)
    if constraint is None:
        return [
            ValidationError(
                row.objective_id,
                "prototype_instance",
                f"symbol {symbol!r} not found in {module_name!r}",
            )
        ]
    actual_id = getattr(constraint, "objective_id", None)
    if actual_id != row.objective_id:
        return [
            ValidationError(
                row.objective_id,
                "prototype_instance",
                f"{module_name}::{symbol}.objective_id={actual_id!r} "
                f"!= row objective_id {row.objective_id!r}",
            )
        ]
    return []


def validate(rows: list[TaxonomyRow]) -> list[ValidationError]:
    """Validate all rows; return every problem found (possibly empty)."""
    errors: list[ValidationError] = []
    seen: dict[str, int] = {}

    for row in rows:
        oid = row.objective_id

        # (e) objective_id uniqueness
        seen[oid] = seen.get(oid, 0) + 1
        if seen[oid] == 2:  # report once, on the first duplicate
            errors.append(ValidationError(oid, "objective_id", "duplicate objective_id"))

        # (a) enum membership
        class_ok = row.semantic_class in SEMANTIC_CLASSES
        if not class_ok:
            errors.append(
                ValidationError(oid, "semantic_class", f"unknown class {row.semantic_class!r}")
            )
        if row.checkability_zone not in CHECKABILITY_ZONES:
            errors.append(
                ValidationError(oid, "checkability_zone", f"unknown zone {row.checkability_zone!r}")
            )
        if row.topological_template and row.topological_template not in TOPOLOGICAL_TEMPLATES:
            errors.append(
                ValidationError(
                    oid, "topological_template", f"unknown template {row.topological_template!r}"
                )
            )
        if row.decision_rule and row.decision_rule not in DECISION_RULES:
            errors.append(
                ValidationError(oid, "decision_rule", f"unknown rule {row.decision_rule!r}")
            )

        # (b) zone <-> class consistency (only when the class is a known enum)
        if class_ok:
            expected_zone = zone_for_class(row.semantic_class)
            if expected_zone is not None and row.checkability_zone != expected_zone:
                errors.append(
                    ValidationError(
                        oid,
                        "checkability_zone",
                        f"class {row.semantic_class!r} implies zone "
                        f"{expected_zone!r}, found {row.checkability_zone!r}",
                    )
                )

        # (c) human vs non-human row shape
        if row.is_human:
            if row.topological_template:
                errors.append(
                    ValidationError(
                        oid, "topological_template", "human row must have an empty template"
                    )
                )
            if row.decision_rule:
                errors.append(
                    ValidationError(
                        oid, "decision_rule", "human row must have an empty decision_rule"
                    )
                )
        else:
            if not row.topological_template:
                errors.append(
                    ValidationError(
                        oid, "topological_template", "non-human row requires a template"
                    )
                )
            if not row.decision_rule:
                errors.append(
                    ValidationError(
                        oid, "decision_rule", "non-human row requires a decision_rule"
                    )
                )

        # (d) DAL tokens subset of {A,B,C,D}
        bad_dal = [t for t in row.dal_tokens() if t not in VALID_DAL]
        if bad_dal:
            errors.append(
                ValidationError(
                    oid, "dal_applicability", f"invalid DAL token(s): {', '.join(bad_dal)}"
                )
            )

        # (f) FK integrity (only when a prototype is referenced)
        if row.is_codified:
            errors.extend(_check_fk(row))

    return errors
