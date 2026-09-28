"""Closed conjunction fragment; no NLP inference, eval, SMT or temporal semantics.

Booleans/enums: equality. Numbers: equality or inclusive intervals. The
reachability model explicitly declares either the Cartesian product of domains
or a finite exhaustive set of reachable valuations. Conditions and guarantees
are lists of atoms; conjunction preserves repeated-variable constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

UNITS = {
    "1": ("scalar", Decimal(1)),
    "ns": ("time", Decimal("0.000000001")),
    "us": ("time", Decimal("0.000001")),
    "µs": ("time", Decimal("0.000001")),
    "ms": ("time", Decimal("0.001")),
    "s": ("time", Decimal(1)),
    "Hz": ("frequency", Decimal(1)),
    "kHz": ("frequency", Decimal(1000)),
    "MHz": ("frequency", Decimal(1000000)),
    "V": ("voltage", Decimal(1)),
    "mV": ("voltage", Decimal("0.001")),
}


class UnsupportedError(ValueError):
    """Well-formed input outside the documented semantic fragment."""


def number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise UnsupportedError("Expected a finite numeric value")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise UnsupportedError("Expected a finite numeric value") from exc
    if not result.is_finite():
        raise UnsupportedError("Non-finite numbers are unsupported")
    return result


def quantity(value: Any, dimension: str = "time") -> Decimal:
    if not isinstance(value, dict) or set(value) != {"value", "unit"}:
        raise UnsupportedError("Quantity requires exactly value and unit")
    unit = UNITS.get(value["unit"])
    if unit is None or unit[0] != dimension:
        raise UnsupportedError(f"UnsupportedError/incompatible unit: {value['unit']}")
    return number(value["value"]) * unit[1]


@dataclass(frozen=True)
class Domain:
    kind: str
    values: frozenset[Any] = frozenset()
    lo: Decimal = Decimal("-Infinity")
    hi: Decimal = Decimal("Infinity")

    @property
    def empty(self) -> bool:
        return self.lo > self.hi if self.kind == "number" else not self.values

    def intersect(self, other: Domain) -> Domain:
        if self.kind != other.kind:
            raise UnsupportedError("Incompatible variable kinds")
        if self.kind == "number":
            return Domain(self.kind, lo=max(self.lo, other.lo), hi=min(self.hi, other.hi))
        return Domain(self.kind, self.values & other.values)


def declarations(model: dict) -> dict[str, Domain]:
    if not isinstance(model, dict) or not isinstance(model.get("variables"), dict):
        raise UnsupportedError("Declared variables are required")
    if set(model) - {"variables", "reachability", "source", "version"}:
        raise UnsupportedError("UnsupportedError model construct")
    result = {}
    for name, spec in model["variables"].items():
        if not isinstance(spec, dict):
            raise UnsupportedError(f"Invalid declaration: {name}")
        kind = spec.get("type")
        if kind == "boolean":
            if set(spec) - {"type"}:
                raise UnsupportedError(f"UnsupportedError boolean declaration: {name}")
            result[name] = Domain(kind, frozenset([True, False]))
        elif kind == "enum":
            values = spec.get("values")
            if (
                set(spec) - {"type", "values"}
                or not isinstance(values, list)
                or not values
                or any(not isinstance(v, str) for v in values)
            ):
                raise UnsupportedError(f"Invalid enum declaration: {name}")
            result[name] = Domain(kind, frozenset(values))
        elif kind == "number":
            if set(spec) - {"type", "unit", "min", "max"}:
                raise UnsupportedError(f"UnsupportedError numeric declaration: {name}")
            unit = UNITS.get(spec.get("unit", "1"))
            if unit is None:
                raise UnsupportedError(f"UnsupportedError declared unit: {name}")
            lo = number(spec["min"]) * unit[1] if "min" in spec else Decimal("-Infinity")
            hi = number(spec["max"]) * unit[1] if "max" in spec else Decimal("Infinity")
            result[name] = Domain(kind, lo=lo, hi=hi)
        else:
            raise UnsupportedError(f"UnsupportedError variable type for {name}: {kind}")
        if result[name].empty:
            raise UnsupportedError(f"Empty declared domain: {name}")
    if not result:
        raise UnsupportedError("No declared variables")
    return result


def constrain(atoms: list[dict], model: dict) -> dict[str, Domain]:
    result = declarations(model)
    if not isinstance(atoms, list):
        raise UnsupportedError("Conditions/guarantees must be conjunction lists")
    for atom in atoms:
        if not isinstance(atom, dict) or set(atom) - {"var", "eq", "min", "max", "unit"}:
            raise UnsupportedError("UnsupportedError atom (only var, eq/min/max, unit)")
        var = atom.get("var")
        if not isinstance(var, str) or var not in result:
            raise UnsupportedError(f"Undeclared variable: {var}")
        spec = model["variables"][var]
        domain = result[var]
        if domain.kind in ("boolean", "enum"):
            value = atom.get("eq")
            if set(atom) != {"var", "eq"}:
                raise UnsupportedError(f"Only equality supported for {var}")
            if (domain.kind == "boolean" and not isinstance(value, bool)) or (
                domain.kind == "enum" and not isinstance(value, str)
            ):
                raise UnsupportedError(f"Incorrect value type for {var}")
            # Out-of-domain enum values are invalid mappings, not impossible conditions.
            if value not in declarations(model)[var].values:
                raise UnsupportedError(f"Undeclared enum value for {var}: {value}")
            restriction = Domain(domain.kind, frozenset([value]))
        else:
            if (
                "eq" in atom
                and ("min" in atom or "max" in atom)
                or not any(k in atom for k in ("eq", "min", "max"))
            ):
                raise UnsupportedError("Use numeric eq OR min/max")
            declared = UNITS[spec.get("unit", "1")]
            unit = UNITS.get(atom.get("unit", spec.get("unit", "1")))
            if unit is None or unit[0] != declared[0]:
                raise UnsupportedError(f"Incompatible units for {var}")
            lo = hi = number(atom["eq"]) * unit[1] if "eq" in atom else None
            if lo is None:
                lo = number(atom["min"]) * unit[1] if "min" in atom else Decimal("-Infinity")
                hi = number(atom["max"]) * unit[1] if "max" in atom else Decimal("Infinity")
            assert hi is not None
            restriction = Domain("number", lo=lo, hi=hi)
        result[var] = domain.intersect(restriction)
    return result


def overlap(a: dict[str, Domain], b: dict[str, Domain]) -> bool:
    return all(not a[k].intersect(b[k]).empty for k in a)


def reachable(condition: list[dict], model: dict) -> bool:
    constrained = constrain(condition, model)
    if any(d.empty for d in constrained.values()):
        return False
    reach = model.get("reachability", {})
    if not isinstance(reach, dict) or reach.get("reviewed") is not True or not reach.get("source"):
        raise UnsupportedError("Reachability requires an explicit reviewed model and source")
    if reach.get("kind") == "cartesian":
        if set(reach) - {"kind", "reviewed", "source"}:
            raise UnsupportedError("UnsupportedError Cartesian reachability construct")
        return True
    if reach.get("kind") == "states":
        if set(reach) - {"kind", "reviewed", "source", "states"}:
            raise UnsupportedError("UnsupportedError finite-state reachability construct")
        states = reach.get("states")
        if not isinstance(states, list):
            raise UnsupportedError("Exhaustive reachable states must be a list")
        matched = False
        for state in states:
            if not isinstance(state, dict) or set(state) != set(constrained):
                raise UnsupportedError("Each reachable state must assign every declared variable")
            d = constrain([{"var": k, "eq": v} for k, v in state.items()], model)
            if any(x.empty for x in d.values()):
                raise UnsupportedError("Reachable state lies outside a variable domain")
            matched |= overlap(d, constrained)
        return matched
    raise UnsupportedError("Reachability supports cartesian or exhaustive states only")
