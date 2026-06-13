# CLAUDE.md — SpecGuard Project Context

> Read this file before working with the codebase. It encodes architectural decisions, scope boundaries, and conventions established during initial design sessions. Following it prevents reopening settled questions and overclaiming research contributions.

## Project identity

**SpecGuard** is a research prototype for a PhD dissertation in Computer Engineering (к.т.н.) at Kharkiv Aviation Institute (KhAI), group F7-503-1.

- **Author:** Anton Stryapunin
- **Supervisor:** Prof. Yevhen Brezhnyev (д.т.н.)
- **Department head:** Prof. Vyacheslav Kharchenko (член-кор. НАН України)
- **Working title:** *"Architecture of AI-agentic support for requirements engineering in the software lifecycle and FPGA components of critical UAV systems"* (pending supervisor approval; previous wording was "Models and methods")

The prototype implements a multi-layered quality gate for requirements engineering in safety-critical contexts (DO-178C / DO-254 / DO-330 TQL-5). It is **not** another linter — it is an architectural framework integrating deterministic detection, knowledge graphs, and (planned) multi-agent analysis for cross-domain (software ↔ FPGA) compliance verification.

## Core positioning — DO NOT FORGET

The dissertation contribution is **architectural**, not methodological. This affects every decision: paper framing, defense narrative, scope discussions.

**What this means in practice:**
- Smell detection itself is **NOT** the novelty (Femmer 2017, ISO/IEEE 29148 + tuning)
- Quality scoring is **NOT** the novelty (Zakeri-Nasrabadi 2024 adapted)
- Conflict detection is **NOT** the novelty (FSARC 2021 taxonomy)
- LLM analysis pattern is **NOT** the novelty (CI/CD failure analysis applied to RE)
- **The novelty is the specific architectural composition + DO-330 design + cross-domain (SW+FPGA) binding + regulatory codification methodology**

If a contributor proposes "improve the smell detector" — interesting, but not the head node. **Architecture is the trunk.**

## Three scientific novelties (working formulation)

1. **Hierarchical Multi-Agent System (HMAS) with polyglot persistence** — Coordinator + Quality/Formalization/Traceability agents over Neo4j + MongoDB + VectorDB; heterogeneous models per agent role with BYOM (Bring Your Own Model) interface.
2. **Two-layer Quality Agent pattern** — deterministic detection (Layer 1, DO-330 qualifiable) + LLM analyst (Layer 2, augmentative, not authoritative); architectural analog of CI/CD failure analysis.
3. **Codified compliance constraints with cross-domain binding** — regulatory objectives (DO-178C / DO-254) as executable Cypher patterns; **cross-domain SW↔FPGA binding** is the unique niche (no precedent in current literature).

## Repository layout

Repository was reorganized on 2026-05-01; see `CHANGELOG.md` for details.

```
specguard/                               ← project root
├── pyproject.toml                       — package metadata, deps, build config
├── CLAUDE.md / README.md / CHANGELOG.md
│
├── src/
│   └── specguard/                       ← installed package (src layout)
│       ├── __init__.py                  — public API re-exports
│       ├── core/                        — smell detection, scoring, pipeline
│       │   ├── smell_detector.py        — 11 smell types, ISO/IEEE 29148 + Femmer 2017
│       │   ├── quality_scorer.py        — completeness / consistency / verifiability
│       │   └── pipeline.py             — orchestrator (smell → score → gate)
│       ├── compliance/                  — DO-178C / DO-254 / cross-domain objectives
│       │   ├── constraint_engine.py     — ComplianceConstraint, Report, runner
│       │   ├── do178c.py               — 7 representative obj (Tables A-3, A-4, A-7)
│       │   ├── do254.py                — 5 representative obj (§6.2-6.4)
│       │   └── cross_domain.py         — 3 cross-domain obj (the unique niche)
│       ├── graph/                       — knowledge graph (was neo4j/, name conflicted)
│       │   ├── builder.py              — Cypher generation, 107 nodes / 171 rels
│       │   └── queries.py              — NetworkX-based local queries
│       ├── llm/                         — BYOM provider protocols (novelty #1 interface) + Anthropic/Mock adapters ([llm] extra)
│       ├── extraction/                  — LLM-assisted edge extraction, human-confirmed (augmentative, outside qualifiable core)
│       ├── agents/                      — HMAS skeleton: Coordinator + Quality/Formalization/Traceability agents (interface validation)
│       ├── io/                          — requirement parsers (plain text / Markdown table / CSV; NOT ReqIF)
│       ├── cli.py                       — `specguard` console command: deterministic tool surface for agent sessions
│       └── data/
│           ├── cva6_requirements.py    — 64 industrial requirements (CVA6 RISC-V)
│           └── uav_cross_domain.py     — 20 derived UAV flight-control reqs (system/HLR/HWR, CVA6-anchored)
│
├── experiments/
│   └── seeded_faults.py                — 100% recall validation (50 mutations × 5 types)
├── notebooks/
│   └── 01_specguard_demo.ipynb         — walkthrough demo for supervisor
├── scripts/
│   └── compliance_demo.py              — end-to-end compliance check demo
├── tests/                               — 34 pytest tests
├── results/                             — experiment outputs and Cypher dumps
└── docs/
    ├── neo4j_guide.md
    └── architecture.md                  — architectural overview (three novelties)
```

## Empirical results — what we show the supervisor

### Pipeline on CVA6 (industrial validation)
- **64 requirements** analyzed
- **95.3% PASS** (61), 1.5% WARN (1), 3.1% FAIL (2)
- **Real findings:** PPA-50, PPA-60 — TBD placeholders; L1W-60 — vague "some"
- Average scores: completeness 0.961, consistency 1.000, verifiability 0.777, overall 0.888
- **Verifiability is the weakest dimension** — consistent with industry experience

### Seeded faults (synthetic validation — three tiers, honest framing)
- **Sanity check (detector's own lexicon):** 100% recall on 50 mutations × 5 fault types — true *by construction*, validates implementation wiring only
- **Independent-lexicon tier** (published terms, programmatically disjoint from detector lexicons): **0% recall** — expected for a closed-lexicon detector, demonstrates the coverage limit
- **LLM blind-mutation tier** (written blind to detector internals): **28.6% recall** (14/49)
- The two non-circular tiers bound real recall; this is the "lexicon coverage" finding for Paper #3, not a defect to tune away. See `experiments/seeded_faults_independent.py`
- FPR on clean set: 12.5% (8/64 after excluding genuine pre-existing defects PPA-50/PPA-60/L1W-60 from the FP numerator)

### Compliance check (insight #7 PoC)
- 15 codified objectives (7 DO-178C + 5 DO-254 + 3 cross-domain)
- **9 passing (60%), 168 violations** on CVA6 with mock DAL/level/traceability (in-memory demo runner)
- **All 15 Cypher queries verified executable on real Neo4j** (2026.04, via `Neo4jGraphRunner` + `scripts/load_neo4j.py` with deliberately seeded compliant/violating mock metadata) — artifact: `results/compliance_neo4j_run.json`; "executable Cypher patterns" is now a verified claim
- **L1W-60, PPA-50, PPA-60 from smell detection are also classified as DO-178C A-3-2 violations** — demonstrating Layer 1 ↔ Layer 3 architectural integration

## Architectural decisions (settled — do not reopen without explicit reason)

- **Hybrid domain** — software-first sequencing, FPGA + software both in dissertation
- **CVA6 as primary HDL benchmark** — public, Thales-curated, RISC-V CPU
- **Neo4j Community Edition + Cypher** — graph layer; runs locally via Neo4j Desktop
- **Deterministic rule-based smell detection** — DO-330 qualifiable, no LLM in detection path
- **AirReq (2025) as direct comparison baseline** for smell detection
- **Seeded faults methodology** for recall validation
- **Three-layer graph architecture** concept (covered in Notion insights)
- **FSARC 7 conflict types** as Layer 2 baseline for conflict detection
- **Modular interfaces for Layer 3-4** — ARTEMIS/ALICE/SAT-LLM as plugins, not replacements
- **Compliance scope:** Option B+C hybrid (~15-25 codified obj + cross-domain focus)
- **DO-330 TQL-5 positioning** — development tool with human-in-the-loop, NOT airborne AI
- **Linguistic metrics are an optional research extension** (`src/specguard/linguistic/`), installed via `pip install -e '.[linguistic]'`. They are outside the DO-330-qualifiable core (which must remain stdlib-only) and complement smell-based assessment without replacing it. They are never required for gate decisions. Metrics: Flesch Reading Ease, Flesch-Kincaid Grade, Mean/Max Dependency Length (Barbosa et al. 2024), token count, sentence count, mean sentence length, lexical density.
- **Optional-extra quarantine pattern** — anything requiring third-party deps (Neo4j driver, LLM clients, spaCy) lives outside the stdlib-only core path behind a pyproject optional extra (`[graph]`, `[linguistic]`, `[llm]`) and degrades gracefully when not installed. Plain `pytest` must always pass with no extras and no external services; integration tests that need Neo4j use `@pytest.mark.neo4j` and skip when the DB is unreachable.
- **Seeded-fault validation must use lexicons independent of the detector** — faults injected from the detector's own word lists produce 100% recall by construction and may only be described as an implementation sanity check, never as method validation. Independent lexicons require a programmatic disjointness check; overlaps are reported, not silently used.
- **LLM-assisted edge extraction is augmentative, never authoritative** — extraction (`src/specguard/extraction/`, planned) proposes edges with evidence spans; only human-confirmed edges enter the graph. Same Layer-2 pattern as the LLM analyst.

## Anti-patterns — DO NOT do these

- **Do not overclaim "we implement ISO 29148"** — ISO defines characteristics, we use Femmer methodology to operationalize them. Use precise wording in docstrings and papers.
- **Do not attempt full DO-178C / DO-254 codification** — that is 700+ hours = a separate dissertation. Current strategy: 15-25 representative objectives, honest scope disclosure.
- **Do not describe the topology screening (`q14_potential_conflicts`) as "conflict detection"** — it is a screening filter for candidate pairs. Real conflict detection is Layer 2 (FSARC) + Layer 3 (SMT).
- **Do not use LLMs for detection** — only for analysis and explanation. Detection must remain deterministic for DO-330 qualifiability.
- **Do not propose "yet another smell tool" as a publication target** — methodology is saturated. All publishable papers must add architectural contribution + cross-domain or regulated context.
- **Do not apply Q14 / FSARC patterns without acknowledging they are screening** — overclaiming destroys defensibility.
- **Do not refactor without checking docstring attributions** — citation chains (Femmer → Veizaga → Vogelsang → Zakeri-Nasrabadi) must remain accurate after edits.

## Style and conventions

**Code:**
- Python 3.11+, modern syntax (`from __future__ import annotations`, `|` unions)
- Dataclasses for structured data (`SmellHit`, `ComplianceConstraint`, etc.)
- Docstrings with academic references (Vogelsang 2025, Femmer 2017, Zakeri-Nasrabadi 2024)
- Type hints required on public API
- Tests live in `tests/` (pytest), experiments in `experiments/` (scripts)

**Documentation:**
- Ukrainian for dissertation drafts and Notion (supervisor preference)
- English for code, docstrings, paper drafts, and this file
- **Honest attribution always** — separate "we adopted from X" from "we contribute Y"

**Commits and changes:**
- Document the **decision** (why), not just the **what**
- Pose trade-offs explicitly — "chose X over Y because ..."

## Current top-of-mind context

- Supervisor meeting was **rescheduled**, not yet rebooked
- Paper #2 (FPGA / DO-254 review) — in revision after substantial rework
- Paper #3 (SpecGuard) — planned for ICTERI 2026 (Springer CCIS, Scopus)
- Paper #4 — concept for Sensors / Electronics Q2 journal, FPGA AI verification
- Industrial seminar from Prof. Kharchenko — НВП Радій on AI in FPGA verification (industrial outreach opportunity)

## Notion references

- **Literature review with 7 strategic insights:** https://www.notion.so/351c18673187810f998ed912dbe4c5ec
- **Dissertation Plan v0.2:** page id `349c1867-3187-817d-a1ee-fdb4b9b84a8a`
- **Dissertation Work Plan:** https://www.notion.so/350c1867318781b1b3def63d1effdb63

## Patent / IP stance

- **Strategy: publish first, opportunistic patent through industrial partner** if collaboration with НВП Радій or similar materializes
- **Best patent candidates:** cross-domain compliance binding (the unique niche), specific architectural integration
- **Not patentable:** smell detection (prior art Femmer 2017), KG for requirements (prior art GDPR/BIM/OSHA precedents from Chhetri 2022, Tauqeer 2022, Yang 2023, Wang 2023)
- Without an industrial partner with IP infrastructure, patent has no economic value at this stage

## Roadmap (high-level)

**Active: evidence-hardening plan — see `docs/improvement_plan.md` (authoritative, phase-by-phase).**
Phase 1: real Neo4j execution of constraint Cypher + de-circularized seeded-fault validation + housekeeping.
Phase 2: UAV cross-domain dataset (CVA6 as HW side). Phase 3: BYOM provider + LLM-assisted edge extraction.
Phase 4: HMAS skeleton.

**Near (next month):**
- Supervisor meeting — confirm architecture-vs-method shift, approve title change to "Архітектура..."
- Paper #2 final submission
- Paper #3 outline with full literature review (after improvement plan Phases 1-2 — they are its empirical foundation)
- Update `smell_detector` docstring with honest attribution (currently overstated)

**Medium (1-3 months):**
- Implement FSARC 7 conflict types as Cypher queries (Layer 2 — concrete, demonstrable)
- Expand compliance codification to 20-25 objectives (upper bound for the dissertation)
- Run ARTEMIS preprocessing experiment
- Submit ICTERI 2026

**Long (6+ months):**
- Industrial outreach to НВП Радій
- Paper #4 (FPGA-specific)
- Master's thesis topics for KhAI students — full DO-178C / DO-254 codification (separate work)

## Running the code

```bash
# Install (once)
pip install -e ".[dev,graph,notebooks]"

# Demo notebook
jupyter notebook notebooks/01_specguard_demo.ipynb

# Validation on seeded faults
python experiments/seeded_faults.py        # 100% recall verification

# Compliance check demo (DO-178C / DO-254 / cross-domain)
python scripts/compliance_demo.py

# Graph queries (in-memory, no Neo4j required)
python -c "from specguard.graph.queries import main; main()"

# Test suite
pytest

# Unified CLI (deterministic tool surface; see README "Unified CLI" for all subcommands)
specguard assess <file|->         # Layer 1 gate table; exit 0/1/2 = all PASS / any WARN / any FAIL
specguard import <file> --dataset-tag NAME [--to-neo4j]   # MERGE-based, never clears
specguard comply --memory|--neo4j
specguard graph q6|q8|q14 | --cypher "..."                # raw Cypher is read-only
specguard review <queue.json> list|accept|reject|export|merge-to-neo4j
```

Claude session commands (`/sg-assess`, `/sg-refine`, `/sg-import`, `/sg-extract`, `/sg-comply`, `/sg-graph`) live in `.claude/commands/` and drive this CLI. **The session LLM is never the detector** — commands must run the deterministic tool, quote its output verbatim, and keep LLM commentary clearly separated; all Neo4j writes require explicit user confirmation. Demo walkthrough: `docs/session_walkthrough.md`, sample input: `examples/walkthrough_requirements.txt`.

For full graph rendering, Neo4j Desktop must be installed locally (DBMS `specguard-cva6`); set the DBMS password via the `SPECGUARD_NEO4J_PASSWORD` env var (`SPECGUARD_NEO4J_USER` / `SPECGUARD_NEO4J_URI` likewise). Cypher dump in `results/specguard_graph.cypher` — paste into Neo4j Browser.

## Tone for AI assistants working in this repo

- **Be honest about novelty.** If something is standard methodology, say so. Do not overclaim.
- **Clarify scope.** If something is a separate work or a separate dissertation in scope, state it explicitly.
- **Engineering trade-offs first.** Cost, qualifiability, maintainability are primary concerns; academic novelty is secondary.
- **Anton prefers Ukrainian for dissertation drafts and discussions; English for code, paper drafts, and this file.**
- **Anton is a working software developer.** No need to explain basic engineering. Move directly to architectural and academic substance.
- **Pushback is valued.** If an idea is weak, say so directly with reasoning. Do not just agree.
- **Check Notion for context before reopening settled questions** — the 7 strategic insights document captures rationale for major architectural decisions.