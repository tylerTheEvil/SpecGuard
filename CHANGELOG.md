# Changelog

## [Unreleased]

### 2026-07-18 — Core detector/scorer fixes from Spec Kit pilot (spec-kit-integration)

Phase 2a of `docs/speckit_integration_plan.md`. Five register-independent
bugs/gaps found by running the pipeline on a spec-kit-style corpus
(`results/speckit_pilot/pilot_report.md`):

- **G1** `MISSING_UNIT`: comma-grouped numerals ("1,000") now tokenize as one
  number — previously the tail group ("000") was flagged in isolation.
- **G2** `VAGUENESS`: "how many"/"how few" interrogatives no longer flagged.
- **G3** `MISSING_UNIT`: calendar units (day/week/month/year) added to the
  unit lexicon ("12 months" no longer flagged).
- **G4** `COMPARATIVE`: noun phrases ("lower limit", "higher bound") no
  longer flagged as baseline-less comparatives.
- **G5** `MEASURABLE_PATTERNS` (scorer): fixed latent `%`-boundary bug —
  `(?:%|percent)\b` could never match "90% " because `\b` after '%' fails
  before whitespace; added minute/hour/calendar units, number-anchored
  comparators (under/within/up to/exactly/every + N), bounded comparators
  (no more/fewer/less than), comma-grouped numerals, and exact zero-counts
  as measurable-criterion indicators.

**Decision:** these are core fixes, not spec-kit profile matters — each is a
lexical collision or lexicon inconsistency wrong in any register. Register-
dependent calibration (entity counts, 'any', SC outcome-register scoring) is
deliberately deferred to the opt-in `--profile speckit` (Phase 2b).

**Verification: zero regression.** CVA6 delta is exactly zero (no gate flips,
no score changes; 95.3% PASS stands). Seeded-fault tiers identical
(100% sanity / 0% independent / 28.6% blind / FPR 12.5%). 201 tests pass
(9 new regression tests). On the spec-kit pilot corpus the default-profile
pass rate rises 0.808 → 0.925.

Also in this change-set: Spec Kit integration research plan
(`docs/speckit_integration_plan.md`) and the Phase 0 pilot — corpus,
runner, and report under `experiments/speckit_pilot/` +
`results/speckit_pilot/`; `spec-kit/` reference clone gitignored.

### 2026-05-01 — Repository reorganization (refactor/repository-structure)

Adopted `src/` layout and Python packaging best practices. No business logic changed.

**Structural changes:**
- `specguard/` (inner package) → `src/specguard/core/`
- `analizer/` (compliance module, typo corrected) → `src/specguard/compliance/`
- `neo4j/` (shadowed driver name) → `src/specguard/graph/`
  - `graph_builder.py` → `graph/builder.py`
  - `graph_queries_local.py` → `graph/queries.py`
- `data/` → `src/specguard/data/`
- `experiment_seeded_faults.py` → `experiments/seeded_faults.py`
- `01_specguard_demo_executed.ipynb` → `notebooks/01_specguard_demo.ipynb`
- `analizer/compliance_demo.py` → `scripts/compliance_demo.py`
- `experiment_results.json` → `results/experiment_results.json`
- `neo4j/NEO4J_GUIDE.md` → `docs/neo4j_guide.md`
- `neo4j/*.cypher` → `results/`

**New files:**
- `pyproject.toml` — package metadata, hatchling build, optional deps, pytest/ruff config
- `.gitignore`
- `tests/` — 34 pytest tests across core, compliance, pipeline, quality scorer
- `docs/architecture.md` — architectural overview of the three scientific novelties

**Import changes:** all `sys.path.insert` hacks removed from package source;
replaced with proper absolute imports (`specguard.core.*`, `specguard.data.*`, etc.).

**Empirical results unchanged** — 100% recall on seeded faults, 95.3% gate PASS
on CVA6, 60% compliance objectives passing — verified post-reorganization.
