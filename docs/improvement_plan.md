# SpecGuard Improvement Plan — Evidence Hardening & Extensions

> Created 2026-06-10 after an external review of the repository. Tracks the
> work needed to close the gaps between current claims and current evidence,
> plus two planned extensions (LLM-assisted edge extraction, HMAS skeleton).
> Execute phase by phase; later phases depend on earlier ones.

## Motivating findings (review summary)

1. **Seeded-fault recall is circular.** `experiments/seeded_faults.py` injects
   faults using the detector's own lexicon vocabulary, so 100% recall is true
   by construction. It validates the implementation, not the method.
2. **Cross-domain objectives run only on mock data.** CVA6 is hardware-only;
   the three CROSS-* objectives execute against synthetic DAL/level/
   traceability metadata. The unique niche is asserted, not demonstrated.
3. **The constraint Cypher has never executed as Cypher.** The demo's
   in-memory runner dispatches by `objective_id` semantics; the query strings
   are unvalidated against a real Neo4j instance.
4. **HMAS (novelty #1) has no code artifact** — it exists only in
   `docs/architecture.md`.
5. **Graph population cost is the real adoption barrier** — `MENTIONS` /
   `DERIVES_FROM` / `MITIGATES` edges are hand-built; industrial requirements
   live in DOORS/Polarion/Jama.

## Phase 1 — Make existing claims true

### 1a. Execute the Cypher for real

- `Neo4jGraphRunner` in `src/specguard/compliance/neo4j_runner.py`,
  conforming to the existing `GraphRunner` callable interface
  (`(cypher_query, params) -> list[dict]`). Depends only on the `neo4j`
  driver, already in the `[graph]` extra — outside the stdlib-only core path.
- Integration tests in `tests/test_neo4j_integration.py` behind a
  `@pytest.mark.neo4j` marker that **skips when Neo4j is unreachable**
  (plain `pytest` must keep passing without a database).
- Test flow: load `results/specguard_graph.cypher` (enriched with the mock
  DAL/level/traceability metadata the compliance demo uses) into the local
  DBMS, execute all 15 constraint queries, assert they parse and return
  sane shapes.
- Fix any Cypher syntax/semantic errors found (Neo4j 5.x `EXISTS {}` and
  pattern-comprehension syntax are the likely suspects).
- Capture a full run to `results/compliance_neo4j_run.json` — the artifact
  that makes "executable Cypher patterns" a verified statement.

**Done when:** all 15 queries execute on real Neo4j; results JSON committed;
pytest passes with and without the database running.

### 1b. De-circularize the seeded-fault validation

- Independent fault lexicon in `experiments/independent_lexicon.py`, sourced
  from published word lists (Femmer et al. 2017 JSS; AirReq 2025 examples;
  Berry et al. ambiguity handbook). **Programmatic disjointness check**
  against the detector's lexicons; unavoidable overlaps reported explicitly,
  never silently used.
- Re-run the mutation experiment with the independent lexicon. Recall below
  100% is the expected and *more credible* outcome; it feeds an honest
  "lexicon coverage" limitations subsection in Paper #3.
- Add precision and FPR to the report: run the detector over mutated + clean
  sets; **exclude known-TBD requirements from the FPR denominator** (they are
  true positives, not false ones).
- Reframe the original experiment's docstring as an implementation sanity
  check ("100% by construction on detector-lexicon faults").
- Optional second tier: LLM-generated blind mutations (prompted with smell
  *definitions* only, never lexicons), hand spot-checked, recall reported
  separately.

**Done when:** independent-lexicon recall/precision/FPR are in
`results/seeded_faults_independent.json`; old experiment reframed; README
results section updated to the honest numbers.

### 1c. Housekeeping

- `datetime.utcnow()` → `datetime.now(UTC)` in `constraint_engine.py`.
- Remove stray `Archive.zip`; add to `.gitignore`.
- README title: keep the old wording until supervisor approval, with a
  footnote that the title change to "Architecture..." is pending.

## Phase 2 — Real cross-domain dataset (UAV flight-control slice)

- New module `src/specguard/data/uav_cross_domain.py`: ~20–25 paired
  requirements for a UAV flight-control function.
- **HW side anchored in CVA6** (the FPGA-hosted processor of the flight
  controller) so the existing dataset becomes the HWR layer.
- **SW side derived from public material** (PX4/ArduPilot architecture docs
  or a published UAV case study), derivation cited in the module docstring.
- Content: 4–5 system-level requirements with explicit timing budgets,
  decomposed into HLR + HWR; 3–4 shared interfaces (memory-mapped registers,
  interrupt, DMA); 2–3 hazards from a mini-FHA with dual-domain mitigation.
- **Deliberately seed both violations and compliant pairs** (one timing
  overrun, one missing CONSISTENT_WITH, one single-domain hazard mitigation)
  so the CROSS-* checks demonstrate discrimination, not just firing.
- Experiment script + real Neo4j run (via 1a) →
  `results/cross_domain_run.json`.

**Done when:** the three CROSS-* objectives produce correct pass/violation
results on the derived dataset via real Neo4j execution.

## Phase 3 — BYOM interface + LLM-assisted edge extraction

### 3a. BYOM model provider protocol

- `src/specguard/llm/provider.py`: a plain `Protocol`
  (`complete(prompt, *, system=None) -> str`), one or two concrete adapters
  behind a new `[llm]` optional extra. No agent-framework dependency.
- This *is* the BYOM interface of novelty #1 — shared by Phase 3b and
  Phase 4.

### 3b. Extraction subpackage

- `src/specguard/extraction/` — optional extra, **outside the qualifiable
  core** (same quarantine pattern as `linguistic/`).
- LLM proposes candidate edges (`MENTIONS`, `DERIVES_FROM`, `MITIGATES`) as
  structured JSON: edge type, endpoints, confidence, and a quoted **evidence
  span** from the requirement text.
- Proposals go to a review queue (JSON file + minimal accept/reject CLI);
  only human-confirmed edges merge into the graph builder. The LLM is never
  authoritative — architecturally identical to the Layer 2 analyst pattern.
- **Validation experiment with existing ground truth:** run extraction blind
  over the 64 CVA6 requirements, measure precision/recall of proposed edges
  against the 171 hand-built relationships →
  `results/edge_extraction_eval.json`. Quantifies how much graph-population
  labor the pattern saves (the adoption-cost answer).
- Scope guard: the review CLI stays deliberately crude. No UI work.

## Phase 4 — HMAS skeleton

- `src/specguard/agents/`: `Coordinator` + `QualityAgent` (Layer 1 pipeline
  + optional LLM analyst via BYOM), `FormalizationAgent` (graph queries),
  `TraceabilityAgent` (compliance engine).
- Plain Python, deterministic orchestration, LLM strictly optional.
- Goal is interface validation for novelty #1, **not** a multi-agent runtime.
- Deliverable: demo script — Coordinator dispatches CVA6 through all three
  agents and merges a combined report.

## Phase 5 — Agentic session integration (Claude as operator console)

**Goal:** an engineer opens a Claude session, points at a folder of
requirements (or pastes text), and runs the SpecGuard workflows
conversationally — assess, refine, import, graph queries, compliance —
while every verdict stays deterministic and every graph write stays
human-confirmed. This is the concrete realization of the HMAS
*interaction layer*: the session host plays Coordinator-with-a-human.

**Positioning honesty:** this is engineering, not a fourth novelty.
Its dissertation value is (a) operationalizing the automation-boundary
claim end-to-end, (b) extending automation to the refinement stage in
the defensible propose→verify→confirm shape, and (c) serving as the
instrument for the future effort-measurement user study.

### The invariant that must survive integration

**The session LLM is never the detector.** Commands and skill text must
enforce: always run the deterministic tool; present gate output verbatim
and attributed; LLM commentary clearly separated as annotation; all
graph writes flow through the review queue or explicit confirmation.
In code this invariant is structural; in a chat session it is only as
strong as the command instructions — so they state it as hard rules.

### 5a. Unified CLI (deterministic tool surface)

A `specguard` console entry point (pyproject `[project.scripts]`)
wrapping the existing machinery. The CLI is deliberately LLM-free —
all LLM work (rewrite drafting, edge proposing) happens in the session
or via the BYOM extraction module:

- `specguard assess <path|->` — parse requirements, run the Layer 1
  pipeline, report gates (human-readable + `--json`). Reading stdin
  (`-`) is what enables the session refinement loop.
- `specguard import <path> [--dataset-tag NAME] [--to-neo4j]` — parse,
  build graph, load. MERGE-based with a `dataset` node property so
  engineer imports coexist with the CVA6/UAV demo graphs (today's
  loaders clear-and-load the whole DB — unacceptable once engineers
  bring their own data).
- `specguard comply [--dataset cva6|uav|TAG] [--neo4j|--memory]` —
  compliance run; NetworkX in-memory fallback when the DB is down
  (same degradation pattern as everywhere else).
- `specguard graph <named-query|--cypher QUERY>` — read-only by
  default; a small named-query library (q6/q8/q14 + per-dataset
  variants); raw Cypher allowed read-only.
- `specguard extract <path>` / `specguard review ...` — wraps the
  existing extraction + review-queue CLI; adds the missing
  `review merge-to-neo4j` step that MERGEs **accepted** edges into the
  live graph (the only LLM-originated write path, and it is
  human-gated by construction).
- Input parser: plain text (`ID: text` per line), Markdown table, CSV.
  Explicitly NOT ReqIF/DOORS — that is a separate work (rabbit hole).

### 5b. Claude command set (`.claude/` in this repo)

Skill/commands with the guard rules baked in:

- `/sg-assess <path|pasted text>` — run `specguard assess`, show gate
  table verbatim, then (clearly separated) plain-language annotation.
- `/sg-refine` — for each FAIL/WARN requirement: draft a rewrite,
  re-run `specguard assess -` on the draft, iterate until PASS or
  stuck, present diff + before/after gate evidence, ask the engineer
  to accept. Accepted text is written back to the source file. (This
  is the propose→verify→confirm extension of automation into the
  refinement stage.)
- `/sg-import` — parse + import with dataset tag; confirm before any
  Neo4j write; report node/edge counts.
- `/sg-extract` — propose edges → review queue → walk the engineer
  through accept/reject → `review merge-to-neo4j` only on confirmation.
- `/sg-comply`, `/sg-graph` — compliance and graph Q&A over the live
  Neo4j (read-only unless explicitly confirmed).

### 5c. Neo4j interaction notes

Available already: `Neo4jGraphRunner` (env-configured), loaders,
integration-test patterns. Needed: MERGE import + dataset tags (5a),
accepted-edge write path (5a), read-only guard for session-issued
Cypher. Constraint to document: Neo4j CE = one database per DBMS, so
dataset coexistence is by node property, not by database.

### 5d. Validation & demo

- Parser + CLI smoke tests (subprocess) in plain pytest; Neo4j-marked
  tests for MERGE import and accepted-edge writes.
- `examples/` folder with a small sample requirements file (with
  seeded defects) for the walkthrough.
- A scripted end-to-end session transcript in `docs/` (assess → refine
  → import → extract → comply) — defense/Радій demo material.

### Stage 2 (deferred): MCP server

Promote the same CLI surface to typed MCP tools
(`assess_requirements`, `query_graph`, `propose_edges`,
`check_compliance`) once the workflows stabilize. Wins: structured
results instead of parsed stdout, host-agnosticism (any MCP client —
keeps the artifact vendor-neutral). Deliberately NOT first: tool
schemas are costly to iterate while workflows are still settling.

## Phase 6 — Novelty deepening (literature-checked)

Four directions that upgrade the contributions from "instances" to
"methods/properties," each stress-tested against prior art on 2026-06-10.
**Full analysis, surviving claims, landmine papers, differentiations, and
citation backbone: `docs/novelty_deepening.md` (authoritative for this
phase).** Summary:

- **6.1 Regulatory codification methodology** — checkability taxonomy over
  all DO-178C+DO-254 objectives, graph-pattern templates per class,
  quantitative coverage map, graph meta-model. Key differentiation target:
  RACK/ARCOS (software-only evidence curation). Cross-domain SW↔FPGA niche
  independently re-confirmed unoccupied.
- **6.2 Non-interference property + GSN assurance case** — formalize and
  property-test "no information flow from ModelProvider outputs to
  deterministic verdicts"; GSN case arguing TQL-5 qualifiability. Key
  complement: Liu et al. DASC 2025 (admissibility without mechanism).
- **6.3 Semantic-drift guard for LLM rewrites** — deterministic invariants
  (ID, numerics/units, entities, modal strength) checked before any
  /sg-refine draft is shown + drift-frequency experiment. Cleanest gap;
  one open check: AirReq's semantic-preservation stance.
- **6.4 Flagship experiment: CVA6 vs RISC-V ISA specs** — NL-level
  cross-document consistency against the governing standard; the documented
  WLRL deviation is the built-in ground-truth case to recover.

Priority by value/effort: 6.3 (days) → 6.1 (spine) → 6.2 (defense) → 6.4
(flagship). Strategic option for the supervisor meeting: merge novelties
#1+#2 into "the qualification boundary as a first-class architectural
element."

## Status

| Phase | Item | Status |
|-------|------|--------|
| 1a | Neo4j runner + integration test + results artifact | **done 2026-06-10** — all 15 queries executed clean on Neo4j 2026.04; no Cypher bugs; 21 integration tests |
| 1b | Independent lexicon + honest metrics | **done 2026-06-10** — independent tier 0% recall, LLM blind tier 28.6%, FPR 12.5% (8/64) |
| 1b-tier2 | Blind mutations dataset (LLM, lexicon-blind) | **done 2026-06-10** — 50 mutations, `experiments/data/blind_mutations.json` |
| 1c | Housekeeping | **done 2026-06-10** |
| 2 | UAV cross-domain dataset | **done 2026-06-10** — 20 paired reqs (6 system + 7 HLR + 7 HWR), CVA6-anchored, PX4/ArduPilot-derived; all 3 CROSS-* objectives discriminate correctly on real Neo4j |
| 3a | BYOM provider protocol | **done 2026-06-10** — `specguard.llm`: ModelProvider + StructuredModelProvider protocols, Anthropic + Mock providers, `[llm]` extra |
| 3b | Edge extraction + eval | **done 2026-06-10** — `specguard.extraction` with evidence-span hallucination guard + human review CLI. **Live eval run 2026-06-10** (claude-opus-4-8, 64 reqs): MENTIONS **recall 1.000, precision 0.664** (75/75 truth edges recovered, 38 extra proposals, 0 guard rejections). Caveat for Paper #3: ground truth is the hand-built graph, so the 38 "false positives" may include genuinely correct edges the manual build missed — human adjudication of those 38 would tighten the precision figure (eval JSON stores counts only; add pair-level logging before the adjudication run) |
| 4 | HMAS skeleton | **done 2026-06-10** — `specguard.agents`: Coordinator + Quality/Formalization/Traceability agents, per-role BYOM mapping, determinism invariant tested; polyglot persistence remains future work |
| 5a | Unified `specguard` CLI (parser, assess/import/comply/graph/extract, MERGE + dataset tags, accepted-edge Neo4j write) | **done 2026-06-10** — `src/specguard/cli.py` + `io/parsers.py` + `graph/neo4j_io.py`; exit codes 0/1/2 on gates; 40 new tests (203 total) |
| 5b | Claude command set with detector-invariant guard rules | **done 2026-06-10** — `.claude/commands/sg-{assess,refine,import,extract,comply,graph}.md`, each with a Hard-rules section |
| 5c | Neo4j session interactions (read-only guard, coexistence docs) | **done 2026-06-10** — `run_readonly_cypher` write-refusal, MERGE-only writes, dataset-tag coexistence (tested) |
| 5d | Examples + CLI tests + scripted demo transcript | **done 2026-06-10** — `examples/walkthrough_requirements.txt` (5 PASS/4 WARN/2 FAIL), `docs/session_walkthrough.md` with genuine outputs incl. live extraction |
| 5-S2 | MCP server over the CLI surface | deferred until workflows stabilize |
| 6.1 | Codification methodology + coverage map + meta-model | pending — see `docs/novelty_deepening.md` |
| 6.2 | Non-interference property + GSN assurance case | pending |
| 6.3 | Semantic-drift guard for LLM rewrites + experiment | pending — blocked only on AirReq overlap check |
| 6.4 | CVA6 vs RISC-V ISA cross-document experiment | pending (flagship, largest effort) |

### Phase 1 outcome note (for Paper #3)

The de-circularized validation produced the key honest finding: recall is
100% on the detector's own lexicon (by construction), **0%** on a strictly
disjoint published-term lexicon (expected for any closed-lexicon matcher),
and **28.6%** on LLM-written blind mutations. The blind tier is the most
realistic estimate; the spread quantifies the lexicon-coverage limitation
and motivates the Layer 2 LLM-analyst architecture (augmentative detection
of out-of-lexicon phrasings) — turning a weakness into the architectural
argument.
