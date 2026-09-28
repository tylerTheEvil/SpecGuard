# Changelog

## [Unreleased]

### 2026-09-28 — Spec Kit extension (`integrations/spec-kit-specguard/`)

A Spec Kit extension packaging SpecGuard Layer 1 as a deterministic gate:
`speckit.specguard.gate` (smells + success-criteria measurability + structural
checks codified from Spec Kit's own specification checklist) and
`speckit.specguard.trace` (spec↔tasks links), hooked `before_plan`
(mandatory) and after specify/clarify/tasks (optional). Staged here, designed
to split into its own repository. Plan and decisions:
`integrations/spec-kit-specguard/docs/implementation_plan.md`; supersedes
Phases 1, 2b and 4 of `docs/speckit_integration_plan.md`.

**Decision — vendor, don't depend:** the extension ships a byte-exact,
SHA-256-locked copy of `smell_detector.py` + `quality_scorer.py`
(`_vendor/specguard_core/VENDOR.json` pins commit 9af1cdf,
`tools/sync_vendor.py`, drift test) instead of pip-depending on SpecGuard:
Spec Kit runs scripts with the user project's interpreter (any venv, no
extras), and a pinned copy identifies the exact detector version in use
(tool configuration management).

**Evidence:** 193 in-the-wild specs (calibration) + a held-out set evaluated
once with frozen rules. FR PASS 80.5% (core) → 94.0% (`speckit` profile),
held-out 93.9%; SC 36.8% → 90.2%, held-out 78.7%. Held-out error analysis
(27 flags: 5 genuine, 10 template-style, 12 false positives) is reported, not
tuned away. Verified end-to-end on spec-kit 1.0.13.dev0 (Claude, Copilot,
Gemini integrations); Python ≥ 3.9.

### 2026-09-28 — Core detector fixes G6–G9 from in-the-wild Spec Kit specs

Found by running the core on 193 real Spec Kit specs (17 repositories from
the Spec Kit extension catalog; corpus and runner land with the Spec Kit
extension in `integrations/spec-kit-specguard/experiments/`). Register-
independent lexical collisions in `smell_detector.py`:

- **G6** `MISSING_UNIT`: identifier numerals are names, not quantities —
  hyphenated IDs (`FR-036`, `ADR-0015`, `SHA-256`), `#17`, ratio tails (`7/7`),
  numbers after ordinal labels (`Phase 4`, `Pass 0`, `ISO 14971`).
- **G7** `AMBIGUITY`: hyphen-compound heads (`fail-safe`, `thread-safe`) are
  technical terms; intensifier prefixes (`super-fast`) still flagged.
- **G8** `AMBIGUITY`: `clean` collocations (`clean clone`, `clean working
  tree`, `clean exit`) and verb use (`MUST clean the cache`).
- **G9** `WEAKNESS`: `could not` is past-tense inability, not a softened modal.

**Decision:** core fixes, not Spec Kit profile rules — each is wrong in any
register (an identifier is never a quantity; `fail-safe` is a term of art).
Register-dependent calibration (`any`, entity counts, success-criteria
scoring) stays in the extension's `speckit` profile.

**Verification: zero regression.** CVA6, UAV (20) and the pilot corpus (120):
byte-identical per-requirement results (hits, positions, scores, gates).
Seeded-fault result files unchanged (100% / 0% / 28.6%, FPR 12.5%). 256 tests
pass (12 new). On the in-the-wild corpus: −16.2% core hits (2,988 → 2,503;
missing unit 791 → 375).

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
