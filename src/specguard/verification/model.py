"""JSON bundle schema v1. Review markers are provenance, not authentication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COLLECTIONS = (
    "requirements",
    "assumptions",
    "scenarios",
    "contracts",
    "evidence",
    "timing",
    "hazards",
    "artifacts",
)
LABELS = dict(
    zip(
        COLLECTIONS,
        (
            "Requirement",
            "Assumption",
            "Scenario",
            "Contract",
            "Evidence",
            "TimingAllocation",
            "SafetyHazard",
            "Artifact",
        ),
        strict=True,
    )
)


def digest(value: Any) -> str:
    """Canonical content hash; changing text without incrementing version still invalidates."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass
class Bundle:
    data: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bundle:
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Expected an object with schema_version=1")
        if not isinstance(data.get("id"), str) or not data["id"].strip():
            raise ValueError("Bundle requires a nonempty id")
        allowed = {"schema_version", "id", "scope", "model", "synthetic", *COLLECTIONS}
        if set(data) - allowed:
            raise ValueError(f"Unsupported bundle fields: {sorted(set(data) - allowed)}")
        ids = set()
        for collection in COLLECTIONS:
            rows = data.get(collection, [])
            if not isinstance(rows, list):
                raise ValueError(f"{collection} must be a list")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                    raise ValueError(f"{collection} records require nonempty string ids")
                if row["id"] in ids:
                    raise ValueError(f"Duplicate artifact id: {row['id']}")
                ids.add(row["id"])
                for key in (
                    "assumption_ids",
                    "scenario_ids",
                    "requirement_ids",
                    "evidence",
                    "mitigates",
                    "parent_ids",
                    "verification_ids",
                ):
                    value = row.get(key, [])
                    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                        raise ValueError(f"{row['id']}.{key} must be a list of ids")
                for key in (
                    "source",
                    "statement",
                    "mode",
                    "event",
                    "response",
                    "hazard_id",
                    "owner",
                    "verification_method",
                    "review_status",
                ):
                    value = row.get(key)
                    if value is not None and not isinstance(value, str):
                        raise ValueError(f"{row['id']}.{key} must be a string")
                for key in ("not_applicable_fields", "dependencies", "requirement_hashes"):
                    value = row.get(key, {})
                    if not isinstance(value, dict) or any(
                        not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()
                    ):
                        raise ValueError(f"{row['id']}.{key} must map strings to strings")
        if not isinstance(data.get("scope", {}), dict):
            raise ValueError("scope must be an object")
        for key in ("complete",):
            if not isinstance(data.get("scope", {}).get(key, []), list):
                raise ValueError(f"scope.{key} must be a list")
        if not isinstance(data.get("scope", {}).get("expected", {}), dict):
            raise ValueError("scope.expected must be an object")
        scope = data.get("scope", {})
        for kind, expected in scope.get("expected", {}).items():
            if (
                kind not in COLLECTIONS
                or not isinstance(expected, list)
                or any(not isinstance(v, str) for v in expected)
            ):
                raise ValueError("scope.expected must map collection names to lists of ids")
        digest(data)  # refuse NaN / infinity and non-JSON values
        return cls(data)

    @classmethod
    def load(cls, path: str | Path) -> Bundle:
        return cls.from_dict(json.loads(Path(path).read_text()))

    def rows(self, kind: str) -> list[dict[str, Any]]:
        return self.data.get(kind, [])

    @property
    def index(self) -> dict[str, dict[str, Any]]:
        return {r["id"]: r for k in COLLECTIONS for r in self.rows(k)}

    def complete(self, kind: str) -> bool:
        scope = self.data.get("scope", {})
        expected = scope.get("expected", {}).get(kind)
        actual = [r["id"] for r in self.rows(kind)]
        return (
            scope.get("reviewed") is True
            and bool(scope.get("source"))
            and kind in scope.get("complete", [])
            and isinstance(expected, list)
            and len(expected) == len(set(expected))
            and set(expected) == set(actual)
        )

    def dependency_ids(self, ids: list[str]) -> list[str]:
        """Explicit semantic dependencies; evidence back-links are not dependencies."""
        index = self.index
        found: set[str] = set()
        pending = list(ids)
        while pending:
            key = pending.pop()
            if key in found:
                continue
            found.add(key)
            item = index.get(key, {})
            for field in ("assumption_ids", "scenario_ids", "requirement_ids", "parent_ids"):
                pending.extend(item.get(field, []))
        return sorted(found)

    def versions(self, ids: list[str]) -> dict[str, str]:
        index = self.index
        return {i: digest(index[i]) for i in self.dependency_ids(ids) if i in index}
