# SpecGuard Prototype

Research prototype for the dissertation: *"Models and methods for AI-agentic
support of requirements engineering in the software lifecycle and FPGA
components of critical UAVs"*.

> Note: a title change to *"Architecture of AI-agentic support..."* is pending
> supervisor approval; the wording above is kept until then.

**Author:** Anton Stryapunin, KhAI, gr. F7-503-1
**Supervisor:** Prof. Yevhen Brezhnyev

[![CI](https://github.com/tylerTheEvil/SpecGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/tylerTheEvil/SpecGuard/actions/workflows/ci.yml)
[![Experiments](https://github.com/tylerTheEvil/SpecGuard/actions/workflows/experiments.yml/badge.svg)](https://github.com/tylerTheEvil/SpecGuard/actions/workflows/experiments.yml)

---

## Installation

```bash
pip install -e ".[dev,graph,notebooks]"
```

Optional extras (all degrade gracefully when absent — the stdlib-only core never
needs them): `graph` (Neo4j + NetworkX), `llm` (Anthropic BYOM adapter),
`linguistic` (spaCy + textstat), `viz` (matplotlib, coverage map), `notebooks`.

## Quick start

```python
from specguard import assess_requirement

result = assess_requirement("REQ-1", "The system shall respond within 100 ms.")
print(result.summary())
```

Or open the demo notebooks:

```bash
jupyter notebook notebooks/01_specguard_demo.ipynb       # core pipeline walkthrough
jupyter notebook notebooks/02_llm_scenarios_demo.ipynb   # BYOM / LLM analyst / extraction / HMAS
```

The LLM notebook auto-detects `ANTHROPIC_API_KEY`: with a key it makes ~10 small
live API calls; without one every cell still runs on a deterministic
`MockProvider`.

Run the compliance demo:

```bash
python scripts/compliance_demo.py
```

Run the seeded faults validation:

```bash
python experiments/seeded_faults.py
```

Run the extended analysis with linguistic metrics:

```bash
# Install the linguistic extra first (one-time)
pip install -e ".[linguistic]"
python -m spacy download en_core_web_sm

# Run full analysis — writes results/full_analysis_with_linguistic.json
python experiments/run_full_analysis.py
```

**Linguistic metrics reference:**

| Metric | Range | What it measures |
|--------|-------|-----------------|
| Flesch Reading Ease | 0–100 (higher = easier) | Classical readability; CVA6 expected ~25–50 |
| Flesch-Kincaid Grade | US grade level (≥0) | Reading level; CVA6 expected ~12–16 |
| Mean Dependency Length | ≥0 (tokens) | Syntactic complexity; CVA6 expected ~3–5 |
| Max Dependency Length | ≥0 (tokens) | Longest arc in the sentence parse |
| Token count | ≥0 | Requirement length |
| Sentence count | ≥0 | Number of sentences |
| Mean sentence length | ≥0 (tokens/sent) | Average sentence complexity |
| Lexical density | 0–1 | Content words / total tokens; CVA6 expected ~0.50–0.70 |

### LLM-assisted edge extraction (optional)

Hand-building the knowledge graph's `MENTIONS` / `DERIVES_FROM` / `MITIGATES`
edges is the real adoption barrier for industrial requirement sets. SpecGuard
provides an optional, human-in-the-loop extractor: an LLM *proposes* candidate
edges (each with a confidence and a verbatim evidence span from the
requirement text); a human *confirms* them before any edge enters the graph.

```bash
# Install the LLM extra first (one-time)
pip install -e ".[llm]"
export ANTHROPIC_API_KEY=...   # any BYOM provider works; Anthropic is the bundled adapter

# Offline smoke run (no API key needed) — writes results/edge_extraction_eval.json
python experiments/edge_extraction_eval.py --provider mock

# Live blind eval against the hand-built CVA6 ground truth
python experiments/edge_extraction_eval.py --provider anthropic [--model claude-opus-4-8]
```

Review flow (proposals → human confirmation → export):

```bash
# proposals are persisted to a JSON review queue, then:
python -m specguard.extraction.review queue.json list --pending
python -m specguard.extraction.review queue.json accept 0 3 7
python -m specguard.extraction.review queue.json reject 1
python -m specguard.extraction.review queue.json export accepted_edges.json
```

The BYOM (Bring Your Own Model) provider interface lives in
`src/specguard/llm/` (a minimal `ModelProvider` protocol plus an optional
structured-output capability and a provider-agnostic fallback). It is the
concrete artifact behind dissertation novelty #1.

**Honesty note:** extraction is *augmentative* and sits outside the
DO-330-qualifiable deterministic core — the LLM is never authoritative (only
human-accepted edges are ever exported; there is no auto-accept), exactly the
Layer 2 analyst pattern used elsewhere in SpecGuard.

### Unified CLI

After `pip install -e .` a single `specguard` console command exposes the
deterministic tool surface (the LLM-free entry point an agent session drives).
Every subcommand supports `--json` for tooling; `assess` exits `0`/`1`/`2`
(all PASS / any WARN / any FAIL) so a script can branch on the worst gate.
Input parsers accept plain text (`ID: text` per line), Markdown tables, and CSV
(`--format auto` by default; `-` reads stdin).

```bash
specguard assess reqs.txt                       # Layer 1 gate table (text/MD/CSV/stdin)
specguard assess - --json                        # machine-readable; stdin input
specguard import reqs.csv --dataset-tag myproj   # build graph, report counts (dry run)
specguard import reqs.csv --dataset-tag myproj --to-neo4j   # MERGE (never clears; dataset-tagged)
specguard comply --memory                        # 15 codified objectives, no DB needed
specguard comply --neo4j                         # same, against live Neo4j ([graph] extra)
specguard graph q6                               # named NetworkX queries (q6/q8/q14)
specguard graph --cypher "MATCH (n) RETURN count(n)"   # read-only Cypher (writes refused)
specguard extract reqs.txt --queue q.json        # LLM-propose edges -> review queue ([llm] extra)
specguard review q.json list                     # list/accept/reject/export proposals
specguard review q.json merge-to-neo4j           # MERGE accepted edges (only LLM-originated write)
specguard taxonomy validate                      # validate the checkability taxonomy (stdlib-only, FK-checked)
specguard taxonomy stats                         # counts per standard / zone / class / template
```

### Checkability taxonomy (Contribution #2)

The 15 codified objectives are generalised into a machine-readable
**checkability taxonomy** (`taxonomy/checkability_taxonomy.csv`) that classifies
each objective by *how it can be verified* — semantic class → checkability zone
(`machine` / `screened` / `human`) → topological template + decision rule. The
stdlib-only loader/validator FK-checks every row against the real
`ComplianceConstraint` symbols and runs in CI with no extras. See
[`docs/taxonomy.md`](docs/taxonomy.md). The coverage-map figure
(`scripts/coverage_map.py`, `[viz]` extra) carries a **CALIBRATION SUBSET** stamp
— the 15 seed objectives were selected for codifiability, so it is not a
representative coverage result.

Neo4j Community Edition is one database per DBMS, so imported datasets coexist
by a `dataset` node property (not separate databases); `import --to-neo4j` and
`review merge-to-neo4j` are MERGE-based and never clear existing data.

---

## Project structure

```
specguard/
├── src/specguard/               # Package source (src layout)
│   ├── core/                    # Smell detection, scoring, pipeline
│   ├── compliance/              # DO-178C / DO-254 / cross-domain objectives
│   ├── graph/                   # Knowledge graph builder and queries
│   ├── taxonomy/                # Checkability taxonomy loader/validator (stdlib-only)
│   └── data/                    # CVA6 requirements dataset
├── taxonomy/                    # checkability_taxonomy.csv (human-editable source of truth)
├── experiments/                 # Validation experiments (seeded faults)
├── notebooks/                   # Demo notebooks
├── scripts/                     # Runnable demos (compliance_demo.py)
├── results/                     # Experiment outputs and Cypher dumps
├── docs/                        # Supplementary documentation
├── .github/workflows/           # CI gate + experiments demonstration pipeline
└── tests/                       # pytest test suite
```

---

## Continuous integration & demonstration

Two GitHub Actions pipelines (`.github/workflows/`):

- **`ci.yml` — the gate** (every push / PR): ruff lint, a stdlib-only core +
  wheel-build guard, the `pytest` matrix on Python 3.11 / 3.12 / 3.13, an
  isolated linguistic-extra job, and a real `neo4j:5-community` service
  container that **continuously verifies the 15 compliance Cypher queries on a
  live database**. The core job also runs `specguard taxonomy validate`, so the
  checkability taxonomy is FK-checked against the real `ComplianceConstraint`
  symbols with no extras installed.
- **`experiments.yml` — the demonstration** (runs only after CI succeeds):
  executes the experiments — seeded faults (both tiers), compliance,
  edge-extraction (offline mock), the HMAS demo, taxonomy stats + coverage map —
  each as an independent step so one failure never masks the rest. It publishes
  a per-experiment **status table + evidence dashboard** to the run summary and
  uploads `results/` as an artifact. An opt-in live-LLM eval is gated behind a
  manual trigger and the `ANTHROPIC_API_KEY` secret (never runs automatically).

---

## Methodology references

1. **Vogelsang & Korn (ICSE-NIER 2025)** — Requirements smell catalog and
   their impact on LLM-based traceability tasks.
2. **Veizaga et al. (IEEE TSE 2023)** — *Paska + Rimay CNL*: 89% precision
   and recall on industrial smell detection in 13 financial systems.
3. **Zakeri-Nasrabadi et al. (Neural Computing & Applications 2024)** —
   Mathematical model for quantitative testability scoring on 1000 industrial
   requirements.
4. **AirReq (IEEE REW 2025)** — Direct competitor / baseline: requirements
   smell detection for commercial aircraft systems (12 smell types, LLM + RAG).

---

## Dataset

**CVA6 Requirements Specification, Revision 1.0.1**

- Industrial-grade open-source RISC-V CPU specification
- Curator: Jerome Quevremont (Thales)
- Maintainer: OpenHW Group
- License: Apache-2.0 WITH SHL-2.1
- Source: https://docs.openhwgroup.org/projects/cva6-user-manual/02_cva6_requirements/cva6_requirements_specification.html

**Statistics:** 64 requirements across 9 categories (ISA, Privileges, Cache,
Performance, etc.). 12 requirements are tagged as safety-critical context.

---

## Latest results

**Pipeline run on 64 CVA6 requirements:**

| Metric | Value |
|--------|-------|
| Average overall quality | 0.888 |
| Gate PASS | 61 (95.3%) |
| Gate WARN | 1 |
| Gate FAIL | 2 (3.1%) |
| Smells detected | 9 |
| Smells per requirement | 0.14 |

**Sanity check — seeded faults from the detector's own lexicon (50 mutations):**
100% recall across all five fault types. This is true *by construction* — the
faults are injected using the detector's own trigger words — so it validates the
implementation wiring, not the method. See `experiments/seeded_faults.py`.

**Method validation — independent-lexicon faults (50 mutations):** faults
injected with published terms (INCOSE GtWR, Femmer 2017, Berry & Kamsties, ISO
29148) programmatically verified *disjoint* from the detector's lexicons.
Recall below 100% is the expected, credible measure of lexicon coverage.

| Fault type | Recall (independent) | Recall (LLM blind) |
|------------|----------------------|--------------------|
| Ambiguity | 0% (0/10) | 50% (5/10) |
| Vagueness | 0% (0/10) | 20% (2/10) |
| Optionality | 0% (0/10) | 30% (3/10) |
| Comparative | 0% (0/10) | 10% (1/10) |
| Placeholder | 0% (0/10) | 33% (3/9) |
| **Overall** | **0% (0/50)** | **28.6% (14/49)** |

The 0% on the strictly-disjoint lexicon and 28.6% on LLM-written blind mutations
together bound the detector's real recall: its closed lexicon does not
generalise beyond its own vocabulary. This is the honest "lexicon coverage"
finding for Paper #3, not a defect to tune away. See
`experiments/seeded_faults_independent.py` and
`results/seeded_faults_independent.json`.

**False-positive rate on clean dataset:** 12.5% — 11 of 64 requirements are
flagged; 3 of those (PPA-50, PPA-60 TBD placeholders, L1W-60 vague "some") are
genuine pre-existing defects excluded from the FP numerator, leaving 8/64 false
positives.

---

## Comparison with original prototype

The original `ai_hdl_pipeline_demo.ipynb` used a single LLM prompt to evaluate
quality. SpecGuard uses an explicit, rule-based smell catalog with a
quantitative scoring model. Differences:

| Aspect | Original prototype | SpecGuard |
|--------|-------------------|-----------|
| Quality criteria | Implicit (LLM judgment) | Explicit catalog (ISO/IEEE 29148) |
| Output | Free-form text | Structured scores in [0,1] |
| Determinism | No | Yes |
| Auditable rules | No | Yes |
| Baseline metrics | None | Recall, FPR |
| DO-330 qualifiable | No (black box LLM) | In principle yes |

This is a deliberate design choice: the graph layer adds LLM-augmented reasoning
*on top of* the deterministic smell foundation (Layer 2, augmentative and never
authoritative), so auditable results are preserved.

---

## Status & roadmap

**Done** (see `docs/improvement_plan.md` for the phase-by-phase record):

- **Graph layer** — Neo4j knowledge graph + NetworkX queries; all 15 compliance
  Cypher patterns verified executable on a live database (now continuously, in CI).
- **Regulatory codification** — 7 DO-178C + 5 DO-254 + 3 cross-domain objectives
  as executable graph constraints, plus the machine-readable **checkability
  taxonomy** (Contribution #2) generalising them.
- **LLM augmentation** — BYOM provider interface + human-gated edge extraction
  (Layer 2 analyst pattern); the session LLM is never the detector.
- **De-circularised validation** — honest three-tier recall (own-lexicon 100% by
  construction; independent-lexicon 0%; LLM-blind 28.6%) — the lexicon-coverage
  finding, not a defect to tune away.
- **HMAS skeleton** + a CI/CD demonstration platform.

**Next** (candidate directions in `docs/novelty_deepening.md`):

1. **Quantify the two-layer value-add** — measure recall recovered by the Layer 2
   LLM analyst over the deterministic baseline, with the augmentative invariant
   verified numerically.
2. **Cross-domain binding as a measured result** — show defects the SW↔FPGA
   binding catches that single-domain analysis structurally cannot.
3. **DO-330 qualification skeleton + GSN assurance case**.
4. **Cross-dataset validation** — extend beyond CVA6 (e.g. via NVP "Radiy"
   collaboration) for external validity.
