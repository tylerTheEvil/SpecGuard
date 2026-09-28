# Scoped project checks (P0 → P1 → P2)

These checks find declared classes of requirements defects. They do not establish
system safety, operational reliability, completeness of a natural-language
specification, whole-standard DO-178C/DO-254 compliance, or DO-330 qualification.
New P0/P1/P2 identifiers are **project rules**, with no asserted normative mapping.
Existing DO-* identifiers remain illustrative legacy mappings.

## Workflow and CLI

The deterministic implementation uses the standard library only. Neo4j is lazy
and optional. A reviewed structured JSON bundle is the input; no LLM is involved.

```sh
specguard import examples/verification_bundle.json --format bundle \
  --dataset-tag synthetic-flight-control --json
specguard verify examples/verification_bundle.json
specguard verify examples/verification_bundle.json --json
specguard verify examples/verification_bundle.json --phase p1 --json
```

`import` validates and projects the bundle in memory by default. `verify` directly
imports the same file for analysis. Exit codes for `verify`: 0 = all resolved
(including justified N/A), 1 = incomplete/unknown/stale, 2 = any established
violation, 3 = invalid input or execution error. Counts preserve FAIL and ERROR
even if the exit code can express only one condition. `comply` retains its legacy
successful-report exit code 0; consumers must inspect its result statuses. It
returns 3 for execution errors. `assess` retains its text gate exit codes.

The example is **synthetic**, including its review/source labels and historical
test result. It covers loss/stale sensor data, timeout, reset during exchange and
recovery. This is an illustrative list, not an exhaustive hazard model or STPA.
Its deliberate defects include an omitted loss response, missing HW timing
allocation, an unconfirmed sensor assumption, stale evidence and two incompatible
ENABLE guarantees. See `results/grounded_checks/example_report.txt`.

Optional Neo4j workflow (these writes must be explicitly requested):

```sh
specguard import examples/verification_bundle.json --format bundle \
  --dataset-tag synthetic-flight-control --to-neo4j --json
# Use the exact revision returned by import:
specguard verify --neo4j --bundle-id synthetic-flight-control --revision HASH --json
```

Imports atomically add a content-addressed `SpecGuardSnapshot` plus typed artifact
nodes and edges, scoped by `(bundle_id, revision, artifact_id)`. Re-importing a
revision is idempotent; another revision/dataset is not replaced. The JSON
snapshot is the authoritative analysis input; arbitrary edits to its graph
projection do not silently rewrite its reviewed meaning. Reader verifies the
snapshot hash. Legacy unscoped graphs have no equivalent snapshot; the reader
reports an explicit error instead of assuming an import is complete. Memory and
Neo4j snapshot paths call the **same** analyzer. Real database parity remains
subject to running the opt-in integration test, not just mock adapter tests.

Python API:

```python
from specguard.verification.model import Bundle
from specguard.verification.analyzer import analyze_bundle

report = analyze_bundle(Bundle.load("examples/verification_bundle.json"))
```

`TraceabilityAgent.run(AgentRequest(requirements=[], context={"verification_bundle":
bundle_dict}))` exposes the same deterministic structured report. The normal
text-only agent no longer invents DAL, parent requirements, or test evidence.

## Result semantics and aggregation

Every `CheckResult` contains `rule_id`, `objects`, `scope`, `applicability`,
`status`, `reason`, `evidence` (IDs/source references), `missing_prerequisites`,
`dependency_versions` (content hashes), `freshness`, `details` and `limits`.

| Verdict | Meaning within the specified rule scope |
|---|---|
| PASS | Applicable check executed with sufficient stated prerequisites; the rule's property holds. |
| FAIL | A specific violation is established with objects and explanation. |
| UNKNOWN | Scope, data, review, reachability or supported semantics is insufficient. |
| NOT_APPLICABLE | Explicit reviewed absence of objects, excluded applicability, disjoint conditions, or an impossible antecedent; reason is retained. |
| ERROR | Execution/adapter/input failure. Never a PASS or ordinary skip. |

Freshness is an independent axis: CURRENT, STALE, UNKNOWN. Evidence retains a
recorded FAIL when dependencies change or become inaccessible. An old PASS can
remain visible as PASS/STALE, but does not contribute to current PASS fractions.
The analyzer verifies evidence dependency hashes and records the historical
outcome; it does **not** independently rerun the referenced system test.

Aggregate priority is FAIL, ERROR, UNKNOWN, then PASS/N/A. Counts, missing data
and freshness remain visible regardless of the aggregate. `pass_fraction_completed`
is current PASS / current (PASS + FAIL), with its denominator printed. A zero
denominator produces null. `completion_coverage` compares completed applicable
checks with known scheduled checks, including unexamined pairs under a limit;
it is null when the expected scope is unknown. N/A checks do not increase the
numerator. Counts count emitted results; an unexamined-pairs result can represent
multiple expected checks, recorded in `details.unexamined_checks`. These metrics
are **not** a percentage of compliance with an entire standard.

## JSON schema v1

Root fields: `schema_version: 1`, nonempty `id`, optional `synthetic`, `scope`,
`model`, and artifact collections `requirements`, `assumptions`, `scenarios`,
`contracts`, `evidence`, `timing`, `hazards`, `artifacts`. IDs are globally unique
within a bundle. See the runnable example for a complete document. Unknown root
fields and malformed record/reference types are rejected; unsupported contract
operators become UNKNOWN diagnostics.

`scope` explicitly supplies `reviewed: true`, a review `source`, a `complete` list
of collection names, and `expected: {collection: [ids...]}`. A collection is
closed only if the declared IDs exactly match loaded IDs. Omitted manifests are
UNKNOWN. An explicitly reviewed empty list can justify N/A. Review fields are
workflow provenance, not authenticated signatures; no auto-accept operation is
provided. Engineers must review their declarations, including completeness.

| Artifact | Supported fields and interpretation |
|---|---|
| Requirement | `id`, `text`, `version`, `source`; `assumption_ids`, `scenario_ids`, `parent_ids`, `mitigates`, `verification_ids`; optional `required_links`, `links_complete`. |
| Assumption | `statement`, `source`, `scope` (mode/config context), `owner`, `verification_method`, `review_status`, `evidence`, `version`; optional `domain: SW/HW`, `when`, `claim`. Confirmation needs accepted evidence actually bound to the assumption hash. |
| Scenario | `mode`, `event`, `hazard_id`, `response`, `time_limit`, `responsibility: {SW/HW: owner}`, `requirement_ids`, `evidence`, `source`, `review_status`, `applicable`, `complete`. |
| Evidence | `source`, `review_status: accepted`, `outcome: PASS/FAIL`, `dependencies: {artifact_id: sha256}`; optional `version`. |
| Timing | `budget: {value, unit}`, `composition: additive`, `components: [{id, budget?}]`, `components_complete`, accepted `review_status`, `source`. |
| Contract | accepted `review_status`, `source`, `requirement_ids`, `requirement_hashes`, `bindings`, explicit `when`, nonempty `guarantees`; optional `version`, `domain`, `assumption_ids`, `scenario_ids`. |

Scenario `applicable: false` needs `not_applicable_reason`. Only `hazard_id` and
`time_limit` can be individually exempted, using nonempty explanatory strings in
`not_applicable_fields`. A missing reaction, requirement, time limit or responsible
domain is FAIL only for a reviewed complete scenario/inventory; inaccessible
linked data is UNKNOWN. A known local field violation is retained alongside
inaccessible other data. Scenario coverage counts only reviewed applicable
scenarios and describes **required field coverage**, not proof that linked
natural-language requirements actually implement the response. Unreviewed
candidates do not enter that denominator. No confirmed scenario model means
UNKNOWN, not an empty complete scenario universe.

Requirement/contract `assumption_ids` express dependence; unconfirmed/stale
assumptions prevent a supported contract verdict. SW/HW assumptions can be
compared through `when`/`claim` only in the common fragment and identical explicit
scope; different scopes without a mapping are UNKNOWN.

Canonical hashing is SHA-256 of UTF-8 JSON with sorted keys, separators `,`/`:`,
`ensure_ascii=False`, and no NaN/infinity (`model.digest`). Hashes cover the entire
artifact, including its version and references. Evidence must record explicit
semantic dependencies transitively (`assumption_ids`, `scenario_ids`,
`requirement_ids`, `parent_ids`); omitted dependency bindings are UNKNOWN. Evidence
back-links do not introduce a circular hash dependency. Changing text while
keeping `version` unchanged still invalidates a recorded hash. Do not regenerate
old evidence hashes after edits merely to silence STALE: rerun/review the actual
verification and create a new evidence record.

Structural obligations use, for example:

```json
{"required_links": [{"relation": "MITIGATES", "targets": ["H1"],
  "reviewed": true, "reason": "Allocated hazard mitigation"}], "links_complete": true}
```

Supported relations here are DERIVES_FROM, VERIFIES and MITIGATES. They check
explicit links/targets, never sufficiency of mitigation or adequacy of testing.
Missing links are FAIL only when the relevant inventories and per-requirement
link set are declared complete.

## Contract fragment and limits

```json
{
  "variables": {
    "MODE": {"type": "enum", "values": ["RUN", "STOP"]},
    "READY": {"type": "boolean"},
    "LATENCY": {"type": "number", "unit": "ms", "min": 0, "max": 10}
  },
  "reachability": {"kind": "cartesian", "reviewed": true, "source": "review:model"}
}
```

An atom is `{"var":"READY","eq":true}`, `{"var":"MODE","eq":"RUN"}` or
`{"var":"LATENCY","min":1,"max":2,"unit":"ms"}`. Lists are conjunctions;
repeated variable atoms intersect. Numeric equality and inclusive intervals
use Decimal arithmetic; omitted interval endpoints are unbounded. Numeric types
represent real intervals, not integer/bit-vector arithmetic. Boolean values
must be JSON booleans. Enums use declared strings. `bindings` maps every used
variable to a source identifier; `requirement_hashes` binds the human-reviewed
formalization to current requirement content. A literal evidence span alone is
not semantic validation. There is no free-text regex formalizer or `eval`.

Units: dimensionless `1`; time `ns`, `us`, `µs`, `ms`, `s`; frequency `Hz`, `kHz`,
`MHz`; voltage `V`, `mV`. Dimension mismatch/unsupported units are UNKNOWN.
Timing allocations are nonnegative and add only under an explicit reviewed
additive composition. Missing components/budgets remain UNKNOWN, but a known
nonnegative subtotal already above budget is FAIL with missing data retained.
Parallel/unknown composition is UNKNOWN; summing it would be unjustified.
Legacy Neo4j timing properties are explicitly in nanoseconds and now require
`timing_composition: additive`; the bundle path supports mixed compatible units.

`cartesian` means every combination in the declared domains is assumed reachable
by the reviewed model. Alternatively, `reachability.kind: states` supplies an
exhaustive `states` list, each assigning every variable in declaration units.
There is no transition-system reachability analysis. Impossible antecedents are
reported explicitly as N/A, rather than proving consistency vacuously. Modes
and configurations are ordinary declared enum variables in conditions.

All contract pairs are examined, independently of Q14. `--max-pairs` defaults to
10000; reaching the bound emits an UNKNOWN scope result with expected/examined
counts. Disjoint guarantees on a common variable under compatible reachable
conditions are FAIL. The diagnostic is a set of incompatible constraints,
**not an execution counterexample**. No conflict in this fragment is not global
natural-language consistency, temporal realizability or controller existence.
Pairwise checking does not find every multi-contract conflict (for example,
interactions involving three different variables and general relations).
Unsupported disjunction, negation, arithmetic relationships, temporal operators,
functions and unreviewed reachability stay UNKNOWN.

## Compatibility and graph schema

- `QualityScores.completeness/consistency/verifiability` retain their numerical
  values/weights and API names, explicitly labeled local text heuristics in docs
  and CLI. They do not detect omitted scenarios or prove consistency.
- `ComplianceReport.results` and `to_dict()` add rule/object details and summary.
  Deprecated `compliance_rate` now means the current completed-check fraction,
  returning null when unassessed. Code formatting it as an unconditional float
  must change. CLI and agents are updated. Historical saved reports are not
  relabeled as results of the new implementation.
- Legacy `runner(query, params) -> list[dict]` still works, but empty output is
  UNKNOWN without independent `RuleScope`. Candidate missing-edge rows remain
  diagnostics until completeness is established. Positive numeric overrun
  witnesses retain FAIL even with an unknown broader inventory.
- API `run_compliance_check(..., scopes={rule_id: RuleScope(...)})` or CLI
  `comply --scope manifest.json` supplies per-rule expected objects, source,
  completeness, capability, missing prerequisites, evidence, versions and
  freshness independently of the violations query. Empty reviewed scopes need
  `not_applicable_reason`. These are reviewer assertions, not inferred facts.
  Legacy arbitrary graph versions/freshness are caller-supplied; automatic
  content-hash tracking is provided by the bundle path.
- The mock memory Cypher-pattern runner has incomplete semantics and explicitly
  cannot acquire PASS authority from a manifest. `comply --memory` is a labeled
  synthetic CVA6 demo, not an analysis of user data. Legacy Neo4j provenance is
  reported as null (unknown), rather than assuming its metadata is real. Unsupported `--dataset uav`
  on that runner is rejected instead of mislabeling CVA6. Use bundles for the
  supported common memory/Neo4j analysis path.
- `SafetyHazard` is canonical. Extraction and old review queues normalize the
  legacy `Hazard` alias; cross-domain queries can read both. New bundle MITIGATES
  accepts Requirement → SafetyHazard only. Legacy extraction permits a
  requirement-target MITIGATES constraint link for compatibility; it is **not**
  counted as a hazard mitigation and must not be reinterpreted silently.
- New links: Requirement/Contract → Assumption `DEPENDS_ON_ASSUMPTION`,
  Requirement/Contract → Scenario `COVERS_SCENARIO`, Contract → Requirement
  `FORMALIZES`, artifact → Evidence `SUPPORTED_BY`, Evidence → dependency
  `DEPENDS_ON`. Existing relation meanings are unchanged.
- Q14 remains a capped topology screening API (15 candidates), explicitly
  distinct from the all-pairs contract analyzer.
- Cypher exports no longer clear data. Destructive demo loaders refuse to run
  unless `SPECGUARD_ISOLATED_TEST_TARGET` exactly equals `URI/database`, explicitly
  designating a disposable DBMS/database. Neo4j fixtures check this **before
  connection/clearing**. CI sets it only for its service container. Never point
  it at a working database.

## Reproduction and independent evaluation

```sh
python experiments/grounded_checks.py --write-example
pytest tests/test_grounded_regressions.py tests/test_verification.py
# Only inside an explicitly designated disposable Neo4j environment:
pytest -m neo4j
```

Ten small cases are exported with IDs, defect classes, scope, statuses and
content hashes for `baseline`, `baseline+P0/P1` and `baseline+P0/P1/P2`.
`comparison_baseline.json` actually executes archived source from
`0f4a3057a1bf2800249558c484220ca5093ed091` in a separate subprocess. Baseline has
no structured analyzer: outputs say UNSUPPORTED rather than fabricating P1/P2
verdicts. `baseline.json` additionally preserves the initial pre-change probe.
No original manuscript or historical research result has been updated.

The synthetic examples are authored implementation checks, not an independent
gold standard. No universal precision/recall, reliability gain, or score-weight
calibration is reported. For a future holdout, have independent reviewers label
cases with review provenance and a predefined defect taxonomy, freeze rules and
weights/commit before accessing labels, and run
`python experiments/grounded_checks.py --cases /path/holdout.json --output /path/report`.
The file shape is a list of `{case_id, defect_class, bundle}`. Keep independent
labels in a separately controlled file for downstream comparison, report
UNKNOWN/unsupported coverage explicitly, and do not use that holdout to tune
rules. These exports are infrastructure, not a completed effectiveness study.

## Design references (not evidence of this implementation's effectiveness)

Lutz & Mikulski's [operational anomaly analysis](https://robynlutz.com/publications/tse04.pdf)
motivates tracking environmental assumptions and failure reactions explicitly.
[Frattini et al. (2023)](https://arxiv.org/abs/2309.10355) motivates separating
requirements-quality observations from their effects on engineering activities.
[NASA's FRET realizability report](https://ntrs.nasa.gov/api/citations/20220007510/downloads/TechnicalReport__FRET_Realizability_Checking.pdf)
describes a substantially stronger temporal/controller question than this
static fragment. [NIST SP 800-160 Vol. 1 Rev. 1](https://csrc.nist.gov/pubs/sp/800/160/v1/r1/final)
provides broader systems engineering context, not a compliance mapping for these rules.
The supplied Langenfeld and Frattini controlled-experiment DOI pages were not
accessible during this implementation, so no detailed claims from them underpin
the code. Future temporal model checking, full STPA and FRET/Kind2 integration
remain separate work; no speculative adapter platform has been added.
