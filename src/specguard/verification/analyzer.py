"""P0/P1/P2 project checks over a reviewed, versioned JSON snapshot."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from .model import Bundle, digest
from .results import CheckResult, summarize
from .results import CheckStatus as S
from .semantics import UnsupportedError, constrain, overlap, quantity, reachable

FRAGMENT = (
    "Conjunctions of Boolean/enum equalities and closed numeric intervals; "
    "explicit Cartesian or finite-state reachability; static pairwise checks only. "
    "No temporal realizability, controller synthesis or natural-language consistency proof."
)


class Analyzer:
    def __init__(self, bundle: Bundle) -> None:
        self.bundle = bundle
        self.index = bundle.index
        self.results: list[CheckResult] = []
        self.evidence_results: dict[str, CheckResult] = {}
        self.assumption_results: dict[str, CheckResult] = {}

    def add(
        self,
        rule: str,
        objects: list[str],
        status: S,
        reason: str,
        *,
        missing: list[str] | None = None,
        freshness: str = "CURRENT",
        details: dict | None = None,
        evidence: list[str] | None = None,
    ) -> CheckResult:
        sources = [
            self.index[i]["source"]
            for i in objects
            if i in self.index and self.index[i].get("source")
        ]
        result = CheckResult(
            rule,
            objects,
            status,
            reason,
            applicability="Declared project objects and reviewed scope; see prerequisites",
            scope=self.bundle.data["id"],
            evidence=list(evidence or []) + sources,
            missing_prerequisites=missing or [],
            freshness=freshness,
            dependency_versions={
                **self.bundle.versions(objects),
                "$scope": digest(self.bundle.data.get("scope", {})),
                "$model": digest(self.bundle.data.get("model", {})),
            },
            details=details or {},
        )
        if rule.startswith(("P2-", "P1-ASSUMPTION-COMPATIBILITY")):
            result.limits.append(FRAGMENT)
        self.results.append(result)
        return result

    def inventory(self, kind: str, rule: str) -> None:
        if not self.bundle.complete(kind):
            self.add(
                rule,
                [],
                S.UNKNOWN,
                f"{kind} inventory is not reviewed and complete",
                missing=[f"reviewed scope.expected.{kind} and complete inventory"],
                details={
                    "scope_unknown": True,
                    "expected_objects": self.bundle.data.get("scope", {})
                    .get("expected", {})
                    .get(kind),
                    "available_objects": [r["id"] for r in self.bundle.rows(kind)],
                },
            )
        elif not self.bundle.rows(kind):
            self.add(
                rule, [], S.NOT_APPLICABLE, f"Reviewed scope explicitly enumerates zero {kind}"
            )

    def evidence(self) -> None:
        self.inventory("evidence", "P0-EVIDENCE-SCOPE")
        for item in self.bundle.rows("evidence"):
            dependencies = item.get("dependencies", {})
            missing = []
            stale = False
            if not isinstance(dependencies, dict) or not dependencies:
                missing.append("nonempty dependency hash map")
                dependencies = {}
            for key, expected in dependencies.items():
                if key not in self.index:
                    missing.append(f"dependency {key}")
                elif digest(self.index[key]) != expected:
                    stale = True
            if item.get("review_status") != "accepted" or not item.get("source"):
                missing.append("accepted evidence with source")
            omitted = set(self.bundle.dependency_ids(list(dependencies))) - set(dependencies)
            missing.extend(f"unrecorded dependency {key}" for key in sorted(omitted))
            outcome = item.get("outcome")
            trusted_failure = (
                outcome == "FAIL"
                and item.get("review_status") == "accepted"
                and bool(item.get("source"))
                and bool(dependencies)
            )
            status = (
                S.FAIL
                if trusted_failure
                else (S.PASS if outcome == "PASS" and not missing else S.UNKNOWN)
            )
            if outcome not in ("PASS", "FAIL"):
                missing.append("supported evidence outcome")
            r = self.add(
                "P0-EVIDENCE",
                [item["id"], *dependencies],
                status,
                "Recorded evidence verdict; dependency hashes checked",
                missing=missing,
                freshness="STALE" if stale else ("UNKNOWN" if missing else "CURRENT"),
                evidence=[item["id"]],
                details={"recorded_dependencies": dependencies, "recorded_outcome": outcome},
            )
            self.evidence_results[item["id"]] = r

    def timing(self) -> None:
        self.inventory("timing", "P0-TIMING-SCOPE")
        for item in self.bundle.rows("timing"):
            missing = []
            if item.get("composition") != "additive":
                self.add(
                    "P0-TIMING",
                    [item["id"]],
                    S.UNKNOWN,
                    "Only explicitly additive nonnegative allocations are supported",
                    missing=["additive composition model"],
                )
                continue
            try:
                budget = quantity(item.get("budget"))
                if budget < 0:
                    raise UnsupportedError("Negative system budget")
                components = item.get("components")
                if not isinstance(components, list) or not components:
                    raise UnsupportedError("Enumerated timing components required")
                known = quantity({"value": 0, "unit": "s"})
                for component in components:
                    if not isinstance(component, dict) or not component.get("id"):
                        raise UnsupportedError("Each component needs an id")
                    if component.get("budget") is None:
                        missing.append(f"budget for {component['id']}")
                        continue
                    value = quantity(component["budget"])
                    if value < 0:
                        raise UnsupportedError("Negative component allocation")
                    known += value
                ids = [c["id"] for c in components]
                if len(ids) != len(set(ids)):
                    raise UnsupportedError("Duplicate timing component ids")
                if item.get("components_complete") is not True:
                    missing.append("complete component inventory")
                if item.get("review_status") != "accepted" or not item.get("source"):
                    missing.append("reviewed timing allocation model")
                proven_overrun = (
                    known > budget and "reviewed timing allocation model" not in missing
                )
                status = S.FAIL if proven_overrun else (S.UNKNOWN if missing else S.PASS)
                self.add(
                    "P0-TIMING",
                    [item["id"]],
                    status,
                    "Known nonnegative allocations exceed budget"
                    if proven_overrun
                    else "Additive allocation checked in seconds",
                    missing=missing,
                    details={
                        "budget_s": str(budget),
                        "known_sum_s": str(known),
                        "components": ids,
                        "composition": "additive",
                    },
                )
            except (UnsupportedError, TypeError, KeyError) as exc:
                self.add(
                    "P0-TIMING",
                    [item["id"]],
                    S.UNKNOWN,
                    str(exc),
                    missing=["supported complete timing data"],
                )

    def assumptions(self) -> None:
        self.inventory("assumptions", "P1-ASSUMPTION-SCOPE")
        for item in self.bundle.rows("assumptions"):
            missing = [
                key
                for key in (
                    "statement",
                    "source",
                    "scope",
                    "owner",
                    "verification_method",
                    "version",
                )
                if not item.get(key)
            ]
            if item.get("review_status") != "accepted":
                missing.append("human review acceptance")
            refs = item.get("evidence", [])
            valid = [self.evidence_results[e] for e in refs if e in self.evidence_results]
            # Evidence must actually depend on the assumption; a random passing test is not support.
            valid = [r for r in valid if item["id"] in r.details["recorded_dependencies"]]
            if not valid or len(valid) != len(refs):
                missing.append("evidence bound to this assumption")
            stale = any(r.freshness == "STALE" for r in valid)
            if stale or any(r.status == S.UNKNOWN or r.freshness != "CURRENT" for r in valid):
                missing.append("current confirmed evidence")
            status = (
                S.FAIL
                if any(r.status == S.FAIL for r in valid)
                else (S.UNKNOWN if missing else S.PASS)
            )
            self.assumption_results[item["id"]] = self.add(
                "P1-ASSUMPTION",
                [item["id"]],
                status,
                "Assumption confirmation prerequisites checked",
                missing=missing,
                freshness="STALE" if stale else "CURRENT",
                evidence=refs,
            )
        for kind in ("requirements", "contracts"):
            for item in self.bundle.rows(kind):
                for ref in item.get("assumption_ids", []):
                    r = self.assumption_results.get(ref)
                    ok = r is not None and r.status == S.PASS and r.freshness == "CURRENT"
                    self.add(
                        "P1-ASSUMPTION-DEPENDENCY",
                        [item["id"], ref],
                        S.PASS if ok else S.UNKNOWN,
                        "Dependency confirmed"
                        if ok
                        else "Conclusion depends on unconfirmed or stale assumption",
                        missing=[] if ok else [ref],
                        freshness=r.freshness if r else "UNKNOWN",
                    )
        # Cross-domain claims use the exact P2 fragment; no free-text equivalence inference.
        for a, b in combinations(self.bundle.rows("assumptions"), 2):
            if {a.get("domain"), b.get("domain")} != {"SW", "HW"}:
                continue
            if a.get("scope") != b.get("scope"):
                self.add(
                    "P1-ASSUMPTION-COMPATIBILITY",
                    [a["id"], b["id"]],
                    S.UNKNOWN,
                    "Different assumption scopes have no declared overlap mapping",
                )
                continue
            try:
                if any(
                    x.get("review_status") != "accepted" or not x.get("claim") or "when" not in x
                    for x in (a, b)
                ):
                    raise UnsupportedError("Reviewed claims and explicit conditions required")
                model = self.bundle.data.get("model", {})
                # Validate guarantees even if the conditions turn out to be disjoint.
                da, db = constrain(a["claim"], model), constrain(b["claim"], model)
                if not reachable(a["when"] + b["when"], model):
                    status, reason = S.NOT_APPLICABLE, "Assumption conditions cannot overlap"
                else:
                    status = S.PASS if overlap(da, db) else S.FAIL
                    reason = "SW/HW structured assumption claims checked in shared scope"
                self.add(
                    "P1-ASSUMPTION-COMPATIBILITY",
                    [a["id"], b["id"]],
                    status,
                    reason,
                    details={
                        "conditions": [a["when"], b["when"]],
                        "claims": [a["claim"], b["claim"]],
                    },
                )
            except (UnsupportedError, TypeError, KeyError) as exc:
                self.add("P1-ASSUMPTION-COMPATIBILITY", [a["id"], b["id"]], S.UNKNOWN, str(exc))

    def scenarios(self) -> dict[str, Any]:
        self.inventory("scenarios", "P1-SCENARIO-SCOPE")
        eligible: list[CheckResult] = []
        for item in self.bundle.rows("scenarios"):
            if item.get("review_status") != "accepted" or not item.get("source"):
                self.add(
                    "P1-SCENARIO",
                    [item["id"]],
                    S.UNKNOWN,
                    "Candidate scenario has not been reviewed",
                    missing=["human acceptance"],
                )
                continue
            if item.get("applicable") is False and item.get("not_applicable_reason"):
                self.add(
                    "P1-SCENARIO", [item["id"]], S.NOT_APPLICABLE, item["not_applicable_reason"]
                )
                continue
            if item.get("applicable") is not True:
                self.add(
                    "P1-SCENARIO",
                    [item["id"]],
                    S.UNKNOWN,
                    "Scenario applicability is not established",
                )
                continue
            missing = []
            na = item.get("not_applicable_fields", {})
            fields = (
                "mode",
                "event",
                "hazard_id",
                "requirement_ids",
                "response",
                "time_limit",
                "responsibility",
            )
            # Applicability cannot exempt the required reaction/requirement/domain obligation.
            allowed_na = {"hazard_id", "time_limit"}
            for key in fields:
                if not item.get(key) and not (key in allowed_na and na.get(key)):
                    missing.append(key)
            for ref in item.get("requirement_ids", []):
                if ref not in {r["id"] for r in self.bundle.rows("requirements")}:
                    missing.append(f"requirement {ref}")
            if item.get("hazard_id") and item["hazard_id"] not in {
                h["id"] for h in self.bundle.rows("hazards")
            }:
                missing.append(f"hazard {item['hazard_id']}")
            domains = item.get("responsibility", {})
            if domains and (
                not isinstance(domains, dict)
                or set(domains) - {"SW", "HW"}
                or not all(isinstance(v, str) and v.strip() for v in domains.values())
            ):
                missing.append("explicit SW/HW responsibility allocation")
            unsupported = []
            if item.get("time_limit"):
                try:
                    if quantity(item["time_limit"]) < 0:
                        raise UnsupportedError("Negative scenario time limit")
                except (UnsupportedError, TypeError, KeyError) as exc:
                    unsupported.append(str(exc))
            complete = self.bundle.complete("scenarios") and item.get("complete") is True
            # Inaccessible linked inventories cannot justify claiming the field is absent.
            unavailable = any(x.startswith("requirement ") for x in missing) and not (
                self.bundle.complete("requirements")
            )
            unavailable |= any(x.startswith("hazard ") for x in missing) and not (
                self.bundle.complete("hazards")
            )
            status = (
                S.FAIL
                if complete
                and (
                    any(not x.startswith(("requirement ", "hazard ")) for x in missing)
                    or (missing and not unavailable)
                )
                else (S.UNKNOWN if missing or unsupported or not complete else S.PASS)
            )
            r = self.add(
                "P1-SCENARIO",
                [item["id"], *item.get("requirement_ids", [])],
                status,
                "Required scenario fields missing"
                if missing
                else "Declared scenario response fields checked",
                missing=missing + unsupported + ([] if complete else ["complete scenario"]),
                details={"not_applicable_fields": na, "event": item.get("event")},
                evidence=item.get("evidence", []),
            )
            eligible.append(r)
        for kind in ("requirements", "contracts"):
            for item in self.bundle.rows(kind):
                for ref in item.get("scenario_ids", []):
                    scenario = next(
                        (s for s in self.bundle.rows("scenarios") if s["id"] == ref), None
                    )
                    ok = scenario is not None and scenario.get("review_status") == "accepted"
                    self.add(
                        "P1-SCENARIO-LINK",
                        [item["id"], ref],
                        S.PASS if ok else S.UNKNOWN,
                        "Reviewed scenario link" if ok else "Missing/unreviewed linked scenario",
                    )
        reviewed_model = self.bundle.complete("scenarios")
        return {
            "reviewed_applicable_scenarios": len(eligible),
            "covered": sum(r.status == S.PASS for r in eligible),
            "fraction": sum(r.status == S.PASS for r in eligible) / len(eligible)
            if reviewed_model and eligible
            else None,
            "scope_reviewed_complete": reviewed_model,
            "meaning": "Required fields of enumerated reviewed applicable scenarios only",
        }

    def structure(self) -> None:
        """Explicit per-requirement link obligations, separate from evidence sufficiency."""
        for req in self.bundle.rows("requirements"):
            for obligation in req.get("required_links", []):
                relation = obligation.get("relation")
                field = {
                    "MITIGATES": "mitigates",
                    "VERIFIES": "verification_ids",
                    "DERIVES_FROM": "parent_ids",
                }.get(relation)
                reason = obligation.get("reason")
                if field is None or not reason or obligation.get("reviewed") is not True:
                    self.add(
                        "P0-STRUCTURE",
                        [req["id"]],
                        S.UNKNOWN,
                        "UnsupportedError or unreviewed link obligation",
                    )
                    continue
                target_kind = {
                    "MITIGATES": "hazards",
                    "VERIFIES": "evidence",
                    "DERIVES_FROM": "requirements",
                }[relation]
                expected = obligation.get("targets")
                if not isinstance(expected, list) or not expected:
                    self.add(
                        "P0-STRUCTURE",
                        [req["id"]],
                        S.UNKNOWN,
                        "Explicit expected link targets required",
                    )
                    continue
                targets = {r["id"] for r in self.bundle.rows(target_kind)}
                for target in expected:
                    linked = target in req.get(field, []) and target in targets
                    complete = (
                        req.get("links_complete") is True
                        and self.bundle.complete(target_kind)
                        and self.bundle.complete("requirements")
                    )
                    status = S.PASS if linked else (S.FAIL if complete else S.UNKNOWN)
                    self.add(
                        "P0-STRUCTURE",
                        [req["id"], target],
                        status,
                        f"{relation} structural obligation: {reason}. "
                        "Edge presence does not establish mitigation/verification sufficiency.",
                        missing=[] if linked else [f"{relation} link/target {target}"],
                        details={"relation": relation, "inventory_complete": complete},
                    )

    def contracts(self, max_pairs: int) -> None:
        self.inventory("contracts", "P2-CONTRACT-SCOPE")
        contracts = self.bundle.rows("contracts")
        supported: dict[str, dict] = {}
        model = self.bundle.data.get("model", {})
        for item in contracts:
            refs = item.get("requirement_ids", [])
            stale = False
            try:
                allowed = {
                    "id",
                    "version",
                    "source",
                    "review_status",
                    "requirement_ids",
                    "requirement_hashes",
                    "bindings",
                    "when",
                    "guarantees",
                    "assumption_ids",
                    "scenario_ids",
                    "domain",
                }
                if set(item) - allowed:
                    raise UnsupportedError(
                        "UnsupportedError contract construct: " + str(set(item) - allowed)
                    )
                if item.get("review_status") != "accepted" or not item.get("source") or not refs:
                    raise UnsupportedError(
                        "Human-reviewed formalization and requirement source required"
                    )
                requirements = {r["id"]: r for r in self.bundle.rows("requirements")}
                for ref in refs:
                    if ref not in requirements or ref not in item.get("requirement_hashes", {}):
                        raise UnsupportedError(
                            f"Missing requirement or reviewed content hash: {ref}"
                        )
                    stale |= digest(requirements[ref]) != item["requirement_hashes"][ref]
                if stale:
                    raise UnsupportedError("Formalization refers to a changed requirement")
                if "when" not in item or not item.get("guarantees"):
                    raise UnsupportedError("Explicit when and nonempty guarantees are required")
                condition = constrain(item["when"], model)
                guarantee = constrain(item["guarantees"], model)
                used = {a["var"] for a in item["when"] + item["guarantees"]}
                if not isinstance(item.get("bindings"), dict) or any(
                    not isinstance(item["bindings"].get(v), str) or not item["bindings"][v].strip()
                    for v in used
                ):
                    raise UnsupportedError("Reviewed variable-to-source bindings are required")
                for ref in item.get("assumption_ids", []):
                    dep = self.assumption_results.get(ref)
                    if dep is None or dep.status != S.PASS or dep.freshness != "CURRENT":
                        raise UnsupportedError(f"Unconfirmed assumption: {ref}")
                if not reachable(item["when"], model):
                    self.add(
                        "P2-CONDITION",
                        [item["id"], *refs],
                        S.NOT_APPLICABLE,
                        "Impossible antecedent in declared model; no vacuous consistency PASS",
                        details={"conditions": item["when"]},
                    )
                    # Still include in pair checks; those report non-overlap explicitly.
                elif any(d.empty for d in guarantee.values()) or not overlap(condition, guarantee):
                    self.add(
                        "P2-CONTRACT",
                        [item["id"], *refs],
                        S.FAIL,
                        "Guarantees incompatible with declared domains/condition",
                        details={"conditions": item["when"], "guarantees": item["guarantees"]},
                    )
                else:
                    self.add(
                        "P2-CONDITION",
                        [item["id"], *refs],
                        S.PASS,
                        "Reviewed antecedent reachable in declared model",
                        details={"conditions": item["when"]},
                    )
                supported[item["id"]] = item
            except (UnsupportedError, TypeError, KeyError) as exc:
                self.add(
                    "P2-CONTRACT",
                    [item["id"], *refs],
                    S.UNKNOWN,
                    str(exc),
                    missing=["supported, current, reviewed formalization/model"],
                    freshness="STALE" if stale else "CURRENT",
                )
        total = len(contracts) * (len(contracts) - 1) // 2
        for index, (a, b) in enumerate(combinations(contracts, 2)):
            if index >= max_pairs:
                self.add(
                    "P2-PAIR-SCOPE",
                    [],
                    S.UNKNOWN,
                    "Resource limit: pair scope incomplete",
                    missing=[f"{total - max_pairs} unexamined pairs"],
                    details={
                        "expected_pairs": total,
                        "examined_pairs": max_pairs,
                        "unexamined_checks": total - max_pairs,
                    },
                )
                break
            objects = [
                a["id"],
                b["id"],
                *a.get("requirement_ids", []),
                *b.get("requirement_ids", []),
            ]
            details = {
                "conditions": [a.get("when"), b.get("when")],
                "guarantees": [a.get("guarantees"), b.get("guarantees")],
            }
            if a["id"] not in supported or b["id"] not in supported:
                self.add(
                    "P2-PAIR",
                    objects,
                    S.UNKNOWN,
                    "Pair contains unsupported/unconfirmed or stale formalization",
                    details=details,
                )
                continue
            try:
                shared = set(a["bindings"]) & set(b["bindings"])
                if any(a["bindings"][v] != b["bindings"][v] for v in shared):
                    raise UnsupportedError("Incompatible source bindings for shared variables")
                condition = a["when"] + b["when"]
                if not reachable(condition, model):
                    status, reason = (
                        S.NOT_APPLICABLE,
                        "Conditions/modes/configurations cannot overlap",
                    )
                else:
                    ga = constrain(a["guarantees"], model)
                    gb = constrain(b["guarantees"], model)
                    status = S.PASS if overlap(ga, gb) else S.FAIL
                    reason = (
                        "No disjoint guarantees in supported pair fragment"
                        if status == S.PASS
                        else "Incompatible guarantee constraints under reachable conditions; "
                        "this is not an execution counterexample"
                    )
                self.add("P2-PAIR", objects, status, reason, details=details)
            except (UnsupportedError, TypeError, KeyError) as exc:
                self.add("P2-PAIR", objects, S.UNKNOWN, str(exc), details=details)


def analyze_bundle(bundle: Bundle, *, phase: str = "p2", max_pairs: int = 10000) -> dict[str, Any]:
    """Run P0/P1, optionally P2, with visible partial scope and no external effects."""
    if phase not in ("p1", "p2") or max_pairs < 0:
        raise ValueError("phase must be p1/p2 and max_pairs must be nonnegative")
    analyzer = Analyzer(bundle)
    analyzer.inventory("requirements", "P0-REQUIREMENT-SCOPE")
    analyzer.evidence()
    analyzer.timing()
    analyzer.structure()
    analyzer.assumptions()
    coverage = analyzer.scenarios()
    if phase == "p2":
        analyzer.contracts(max_pairs)
    return {
        "schema_version": 1,
        "bundle_id": bundle.data["id"],
        "bundle_hash": digest(bundle.data),
        "configuration": "baseline+P0/P1" + ("/P2" if phase == "p2" else ""),
        "synthetic": bundle.data.get("synthetic", False),
        "scenario_coverage": coverage,
        "summary": summarize(analyzer.results),
        "results": [r.to_dict() for r in analyzer.results],
        "limits": [FRAGMENT],
    }


def render_report(report: dict[str, Any]) -> str:
    stats = report["summary"]
    lines = [
        f"Project checks: {report['bundle_id']} ({report['configuration']})",
        f"Status: {stats['status']}; {stats['counts']}; STALE: {stats['stale']}",
        f"Completed applicable: {stats['completed_applicable_checks']}/"
        f"{stats['expected_checks']}; PASS fraction: {stats['pass_fraction_completed']}",
        f"Scenario coverage: {report['scenario_coverage']}",
    ]
    for r in report["results"]:
        lines.append(
            f"[{r['status']}/{r['freshness']}] {r['rule_id']} {r['objects']}: {r['reason']}"
        )
        if r["missing_prerequisites"]:
            lines.append(f"  Missing: {r['missing_prerequisites']}")
        if r["evidence"]:
            lines.append(f"  Sources/evidence: {r['evidence']}")
    return "\n".join(lines)
