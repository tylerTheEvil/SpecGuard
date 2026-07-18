# SpecGuard × GitHub Spec Kit — Integration Research & Plan

> Status: **research + plan, not implemented**. Written 2026-07-18 against spec-kit
> v0.13.1.dev0 (clone at `spec-kit/`, reference only — do not commit the clone).
> Decision review: this document proposes; nothing here is settled until pilot
> (Phase 0) results are in.

## 1. What Spec Kit is and where it is weak

GitHub Spec Kit (MIT, `specify-cli` 0.13.x) implements Spec-Driven Development:
an agent-executed pipeline `constitution → specify → clarify → plan → tasks →
[analyze] → implement → [converge]`, producing structured artifacts per feature
under `specs/[###-feature-name]/`:

- **spec.md** — user stories (`US1..`, priorities P1-P3), functional requirements
  (`- **FR-001**: System MUST ...`), success criteria (`SC-###`), Given/When/Then
  acceptance scenarios, `[NEEDS CLARIFICATION: ...]` placeholders.
- **tasks.md** — tasks `- [ ] T012 [P] [US1] Create model in src/models/x.py`
  with phases, user-story tags, explicit file paths, `[X]` completion marks.
- plan.md / research.md / data-model.md / contracts/ / checklists/.

**Quality mechanisms are entirely LLM-driven.** `/speckit.checklist` generates
"unit tests for the spec" (LLM-authored, LLM/human-checked); `/speckit.analyze`
does cross-artifact consistency analysis (LLM, read-only). There is **no
deterministic validator anywhere in the pipeline** — no repeatable, auditable
gate whose verdict is independent of a model.

**Traceability stops at tasks.md.** The chain `FR → US → T### → planned file
path` exists as markdown conventions, but nothing links tasks to commits or to
actual code, nothing persists the trace beyond the markdown files, and nothing
can *query* it ("which FRs have no completed task?" is unanswerable without
re-reading everything through an LLM). The bundled `git` extension auto-commits
**per phase** (after specify/plan/tasks/implement), not per task — so even commit
granularity does not align with tasks out of the box.

These two gaps are exactly SpecGuard's two strengths. The fit is genuine.

## 2. Why the integration is worth doing (honest assessment)

### 2.1 For the tool
1. **Deterministic gate for LLM-generated specs.** LLM-generated requirements
   are a prime target for smell detection: placeholders (`[NEEDS CLARIFICATION]`
   is spec-kit's institutionalized TBD), vague quantifiers, non-verifiable verbs,
   missing units in success criteria. A `specguard assess` gate with exit codes
   0/1/2 slots directly into spec-kit's hook system as a **blocking pre-plan
   check** — machine-checkable, repeatable, no model in the loop.
2. **Queryable traceability graph.** Importing spec.md + tasks.md + git history
   into the knowledge graph makes the SDD trace persistent and queryable:
   `Feature → UserStory → Task → Commit → File`, with FR coverage as executable
   Cypher — the same pattern as the existing DO-178C A3-1 traceability
   constraint, applied to SDD artifacts.
3. **The two-layer pattern already exists in spec-kit — half of it.**
   `/speckit.analyze` and `/speckit.checklist` *are* an LLM analyst layer.
   Spec-kit is missing the deterministic Layer 1 underneath. SpecGuard supplies
   precisely the missing layer. This is the cleanest possible external validation
   of the dissertation's two-layer Quality Agent thesis.

### 2.2 For the dissertation
The working title is *"Architecture of AI-agentic support for requirements
engineering in the software lifecycle..."* — Spec Kit **is** the mainstream
AI-agentic software lifecycle. Integration gives:

- A **second validation context** beyond CVA6/UAV (generality/portability
  evidence for the architecture claim).
- A live instantiation of **novelty #2** (two-layer pattern: deterministic gate
  under spec-kit's LLM analysis) and **novelty #3** (codified constraints:
  trace-coverage objectives as executable Cypher over a new artifact domain).
- A new empirical angle for Paper #3: *smell density of LLM-generated specs*,
  and *deterministic-vs-LLM finding complementarity* (what does the gate catch
  that `/speckit.analyze` misses, and vice versa).

**Scope discipline:** this is an *application case study* supporting novelties
#2 and #3. It is **not** a fourth novelty and must not be framed as one. It also
must not displace Phase-priority work (Paper #2 final, Paper #3 outline).

### 2.3 Risks and counterarguments (do not skip)

| Risk | Severity | Mitigation |
|---|---|---|
| **Lexicon/style mismatch → FP storm.** ~~Spec-kit FRs read "System MUST [capability]" — `IMPLICIT_REFERENCE` / `NON_VERIFIABLE` will fire on nearly every FR.~~ **RESOLVED by Phase 0 pilot (2026-07-18): the FP storm did not materialize** — feared detectors fired zero times; FR pass rate 90.7% uncalibrated (≈CVA6's 95.3%). Actual mismatch: the *scorer* under-rates spec-kit Success Criteria (modal-free outcome register + latent measurable-pattern bugs). See `results/speckit_pilot/pilot_report.md`. | ~~High~~ → resolved | Phase 2 reshaped: core fixes (G1–G5) + slim SC-aware profile (P1–P3). |
| Known recall limits (0% independent-lexicon, 28.6% blind). The gate will miss much; spec-kit users may over-trust it. | Medium | Position as Layer 1 of two layers, never as sufficient. Placeholder/vagueness/missing-unit classes — the ones generated specs actually exhibit — are the detector's strong suit. |
| Spec-kit is a fast-moving target (0.13.x; extension API `schema_version: "1.0"`). | Medium | Pin to a tagged release; integrate **only** via the documented extension API + CLI, never by patching core templates. Parser must be tolerant of heading/format drift. |
| FR→Task mapping is **indirect** in spec-kit (tasks tag user stories, not FRs). Deterministic FR-coverage queries need an FR→Task or FR→US edge that the artifacts don't fully encode. | Medium | Two channels: (a) deterministic US→Task from `[US#]` tags + FR→US where spec structure implies it; (b) LLM-**proposed**, human-confirmed FR→Task edges through the existing extraction review queue — the augmentative-never-authoritative pattern, reused as-is. |
| Per-task commit linkage requires cooperation (commit-message convention or hook) that vanilla spec-kit doesn't provide. | Medium | Deterministic reconciliation: intersect task file paths with commit diffs + optional `T###` commit-message convention; ship an optional post-commit hook. Report unlinked commits/tasks explicitly rather than guessing. |
| Scope creep into "SpecGuard becomes a spec-kit plugin project." | Medium | Everything lands as (a) small additions to existing SpecGuard modules and (b) one thin extension package under `integrations/`. No spec-kit fork, no upstream PRs required to function. |
| Namespace: spec-kit already bundles a `speckit.assess.*` extension (idea triage — unrelated). | Low | Use `speckit.specguard.*` namespace throughout. |

**Verdict: worth doing**, conditional on the Phase 0 pilot showing the gate
produces useful signal (not FP noise) on real generated specs after profile
calibration.

## 3. Integration architecture

### 3.1 Mechanism: a spec-kit *extension*, not a fork

Spec-kit v0.13 has a first-class extension system (`extensions/RFC-EXTENSION-SYSTEM.md`):
`extension.yml` manifest, namespaced commands (`speckit.<id>.<cmd>` as markdown
prompt templates), **hooks on every workflow event** (`before_/after_` ×
specify/clarify/plan/tasks/checklist/analyze/implement/converge) with
mandatory-blocking semantics, config files, and installation via
`specify extension add --from <zip>`. The bundled `git` extension demonstrates
the exact shape we need (hooks everywhere, scripts, config).

We ship **one extension** living in the SpecGuard repo:

```
integrations/spec-kit/specguard-extension/
├── extension.yml
├── README.md
├── config-template.yml            # gate strictness, profile, neo4j on/off
├── commands/
│   ├── speckit.specguard.gate.md      # run `specguard assess --profile speckit` on spec.md
│   ├── speckit.specguard.import.md    # import spec into graph, dataset-tag = feature dir
│   ├── speckit.specguard.trace.md     # sync tasks/commits/files into graph
│   └── speckit.specguard.audit.md     # run SDD-TRACE coverage queries, print report
└── scripts/bash/                  # thin wrappers around the specguard CLI
```

Hook wiring (defaults; all configurable):

| Event | Command | Mode | Purpose |
|---|---|---|---|
| `after_specify` | `speckit.specguard.gate` | optional | early feedback while spec is cheap to fix |
| `before_plan` | `speckit.specguard.gate` | **mandatory** | the actual quality gate — exit 2 (FAIL) blocks planning |
| `after_tasks` | `speckit.specguard.import` + `trace` | optional | persist Feature/US/FR/SC/Task nodes |
| `after_implement` | `speckit.specguard.trace` | optional | reconcile commits ↔ tasks ↔ files |
| `after_analyze` | `speckit.specguard.audit` | optional | deterministic counterpart next to LLM analysis |

The extension's command templates follow the same discipline as our existing
`/sg-*` session commands: **run the deterministic CLI, quote its output
verbatim, keep LLM commentary separated, confirm before any Neo4j write.**

Zero-code secondary channel: a project constitution principle ("SpecGuard gate
must pass before planning") makes `/speckit.plan`'s Constitution Check enforce
the gate socially even where hooks are disabled.

### 3.2 SpecGuard-side additions

**(a) Parser — `src/specguard/io/speckit.py`** (stdlib-only, stays in
qualifiable core path):
- `parse_spec_md(text) -> SpecKitSpec`: FR-### bullets, SC-### bullets, user
  stories with priority + acceptance scenarios, `[NEEDS CLARIFICATION]` markers
  (mapped onto the PLACEHOLDER smell channel), assumptions, edge cases.
- `parse_tasks_md(text) -> list[SpecKitTask]`: `T###`, `[P]`, `[US#]`,
  completion `[X]`, file paths, phase, `depends on T###` annotations.
- Registered in `parse_requirements` auto-detection (sniff: `### Functional
  Requirements` + `**FR-` bullets). FRs and SCs become `Requirement` objects
  (SCs matter: "under 2 minutes" vs missing-unit/vague checks apply).

**(b) Assessment profile — `--profile {default,speckit}`** on `assess`:
a named reweighting of smell severities/detectors for product-style FR prose.
Calibrated in Phase 0, documented like the seeded-fault tiers (what was
suppressed and why — this is a finding, not a hack).

**(c) Graph schema extension — `graph/builder.py`:**

New node labels: `Feature`, `UserStory`, `Task`, `Commit`, `File`,
`SuccessCriterion`. New relationships:

```
(Feature)-[:HAS_STORY]->(UserStory)
(Feature)-[:HAS_REQ]->(Requirement)          # FR-### ; also HAS_CRITERION → SuccessCriterion
(Task)-[:IMPLEMENTS_STORY]->(UserStory)      # deterministic, from [US#] tag
(Task)-[:PLANS_FILE]->(File)                 # deterministic, from task file paths
(Task)-[:DEPENDS_ON]->(Task)                 # deterministic, from "depends on"
(Commit)-[:COMPLETES]->(Task)                # reconciled (see trace)
(Commit)-[:TOUCHES]->(File)                  # deterministic, from git diff
(Requirement)-[:REALIZED_BY]->(Task)         # LLM-proposed, human-confirmed ONLY
```

Dataset tag = `speckit-<feature-dir>` (e.g. `speckit-001-photo-albums`) —
existing MERGE/coexistence semantics apply unchanged; never clears.

**(d) `specguard trace` subcommand** (stdlib + `git` via subprocess; deterministic):
- `trace sync <feature-dir>`: parse tasks.md; `git log` since branch point;
  link `Commit-[:COMPLETES]->Task` by (1) `T###` references in commit messages,
  (2) file-path intersection between task's planned files and commit diff.
  **Ambiguous or unlinkable items are reported, never guessed.**
- `trace report <feature-dir>`: coverage table — per FR / US / Task: planned,
  tasked, completed, committed; orphan commits; unstarted P1 stories.
- Optional `trace install-hook`: git post-commit hook appending to a local
  trace journal (JSONL) for exact per-commit capture; `sync` remains the
  source of truth and works without the hook.

**(e) SDD-TRACE constraint family — `compliance/sdd_trace.py`:**
~6 coverage objectives in the existing `ComplianceConstraint` shape (executable
Cypher + memory-runner equivalents), e.g.:

- `SDD-TRACE-1` — every FR reaches ≥1 Task (via US or confirmed REALIZED_BY)
- `SDD-TRACE-2` — every P1 UserStory has ≥1 completed Task
- `SDD-TRACE-3` — every completed Task has ≥1 Commit
- `SDD-TRACE-4` — every planned File is touched by some Commit
- `SDD-TRACE-5` — no orphan Commits on the feature branch (no task linkage)
- `SDD-TRACE-6` — no `[NEEDS CLARIFICATION]` markers remain at implement time

These are deliberately the same architectural move as DO-178C A3-1: a
traceability objective codified as a graph pattern. That parallel *is* the
paper narrative.

**(f) FR→Task extraction (optional, reuses existing machinery):** the
`extract` command gains a mode proposing `REALIZED_BY` edges from FR text ×
task descriptions, flowing through the **existing review queue**
(propose → human accept/reject → merge). No new pattern, no authority for the LLM.

### 3.3 What we do NOT do
- No fork of spec-kit; no patches to its core command templates.
- No LLM in the gate or in `trace sync` — detection and reconciliation stay
  deterministic (DO-330 posture preserved; the extension's only LLM use is the
  already-quarantined extraction path).
- No auto-write to Neo4j from hooks without confirmation — same rule as `/sg-*`.
- No claim of "requirements-to-code traceability" beyond what the reconciliation
  actually establishes; unlinked = reported unlinked.

## 4. Plan of work (phased, gated)

**Phase 0 — Pilot & calibration (go/no-go). ~1-2 days. ✅ DONE 2026-07-18 — GO.**
Corpus: 6 specs / 120 requirements (86 FR + 34 SC) generated via the real
spec-kit template + instructions (`experiments/speckit_pilot/`). Findings
(full report: `results/speckit_pilot/pilot_report.md`):
- **No FP storm** — feared detectors silent; FR pass rate 90.7% uncalibrated.
- Real mismatch is in the **scorer on Success Criteria** (55.9% pass): SCs are
  modal-free outcome statements by spec-kit design, and a latent core bug
  makes `90%` never match `MEASURABLE_PATTERNS` (`\b` after `%`).
- Hit classification: 1 TP / 19 hits; 18 FPs decompose into **general core
  bugs G1–G5** (comma numerals, "how many", calendar units, noun-phrase
  comparatives, measurable-pattern gaps) + **register differences P1–P3**.
- Calibrated simulation: 117 PASS / 3 WARN / 0 FAIL — remaining flags are 1
  genuine catch, 1 documented residual FP, 1 unmeasurable SC (desired catch).
- Corpus finding: zero `[NEEDS CLARIFICATION]` markers across all 6 runs —
  ambiguity migrates to Assumptions; the PLACEHOLDER synergy is weak.
Housekeeping done: `spec-kit/` gitignored; clone pinned by SHA `57cc518`.

**Phase 1 — Parser. ~1 day.**
`io/speckit.py` (spec.md + tasks.md), auto-detect registration, tests following
`test_parsers.py` conventions (fixtures from real generated artifacts, including
malformed/drifted variants). Must expose requirement *kind* (FR vs SC) — the
Phase 2b SC register depends on it.

**Phase 2a — Core detector/scorer fixes (register-independent). ~0.5-1 day.**
Fix G1–G5 from the pilot in `src/specguard/core/` (they are bugs, not
profile matters): comma-grouped numerals, "how many" collision, calendar
units, comparative noun phrases, `MEASURABLE_PATTERNS` `%`-boundary bug +
missing comparators/time units. **Rerun the CVA6 baseline and report the
delta** — expected near-zero, must be verified, and published numbers
(95.3% PASS etc.) re-stamped if they move.

**Phase 2b — `--profile speckit`. ~1 day.**
Slim profile on `assess` (CLI + Python API): P1 (entity counts unit-less),
P2 (`any` universal quantifier), P3 (SC outcome register: completeness modal
granted, verifiability dominated by measurability — unmeasurable SC ⇒ WARN).
Human spot-check of the pilot's FP classifications before freezing. Honest
docs of every suppression, mirroring the seeded-fault-tier discipline.

**Phase 3 — Graph schema + trace. ~2-3 days.**
Builder extension (new labels/rels), `specguard trace sync|report`
(git-log reconciliation, journal-optional), SDD-TRACE constraints with
memory-runner + Neo4j-runner parity, `@pytest.mark.neo4j` integration tests.

**Phase 4 — The extension package. ~1-2 days.**
`integrations/spec-kit/specguard-extension/` per §3.1; end-to-end walkthrough
(`docs/speckit_walkthrough.md`): init a toy project, install extension, run
specify→gate(FAIL)→fix→gate(PASS)→plan→tasks→import→implement→trace→audit.
Verify mandatory-hook blocking on exit 2 actually halts `/speckit.plan`.

**Phase 5 — Evaluation & paper material. ~2-3 days.**
- RQ1: smell density of LLM-generated specs (calibrated profile) vs CVA6 human
  baseline.
- RQ2: complementarity — findings by deterministic gate vs `/speckit.analyze`
  on the same specs (overlap/unique sets).
- RQ3: trace completeness after implementing 1-2 real toy features
  (SDD-TRACE pass rates; % commits linked deterministically).
Artifacts in `results/`; feeds Paper #3 (ICTERI) as the generality case study.

Total: ~8-12 working days, independently useful after each phase. Phases 0-2
deliver standalone value (gate on any spec-kit project) even if 3-5 slip.

## 5. Dissertation positioning (one paragraph to reuse)

Spec Kit integration demonstrates that the SpecGuard architecture — deterministic
Layer-1 gate, knowledge-graph traceability, codified constraints as executable
graph patterns, LLM strictly augmentative — transfers from the safety-critical
DO-178C/DO-254 context to mainstream AI-agentic development workflows without
structural change: spec-kit's LLM-driven `analyze`/`checklist` occupy the
Layer-2 analyst role, SpecGuard supplies the missing deterministic Layer 1, and
the SDD-TRACE constraint family shows the codified-compliance method applied to
a new artifact domain. This supports novelties #2 and #3 as *architectural*
claims (portability evidence); it introduces no new novelty and is framed as a
validation case study.
