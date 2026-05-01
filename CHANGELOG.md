# Changelog

## [Unreleased]

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
