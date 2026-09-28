# spec-kit-specguard — Implementation Plan

> Status: **v0.1 implemented** (2026-09-28) — phases 1–9 below done; final
> experiment numbers in `experiments/README.md` supersede the first-pass
> numbers quoted in §4 (prototype parser). Staged inside the
> SpecGuard repository under `integrations/spec-kit-specguard/`; designed to be
> split into its own repository (`spec-kit-specguard`) without code changes.
>
> Relation to `docs/speckit_integration_plan.md` (SpecGuard repo, 2026-07-18):
> this plan **supersedes Phases 1, 2b and 4** of that document for the extension
> itself (parser, `speckit` profile, extension package). Phase 3 (graph schema,
> commit↔task trace, SDD-TRACE Cypher constraints) stays in the SpecGuard core
> roadmap and is **out of scope** here — the extension stays stdlib-only and
> graph-free.

## 1. Goal and positioning

A Spec Kit extension that adds the **deterministic Layer 1** Spec Kit lacks: a
reproducible, model-free quality gate over `spec.md` (and a deterministic
spec↔tasks traceability check), wired into Spec Kit's hook system and usable
as a plain CLI in CI.

Honest positioning (mirrors the SpecGuard CLAUDE.md discipline):

- Smell detection, scoring and the SC-measurability check are **not** novel —
  Femmer 2017 lexicon methodology, Zakeri-Nasrabadi 2024 scoring, Spec Kit's
  own written quality rules. The extension is an **application case study** of
  the two-layer Quality Agent pattern (novelty #2): Spec Kit's
  `/speckit.checklist` / `/speckit.analyze` are the LLM Layer 2; this extension
  supplies Layer 1 underneath. It is portability evidence, not a new novelty.
- Structural checks are a **codification of Spec Kit's own checklist**
  (`templates/commands/specify.md` → "Specification Quality Checklist"): the
  mechanically checkable subset is enforced deterministically, the rest is
  explicitly reported as *not checked*. Same architectural move as codifying
  DO-178C objectives (novelty #3), applied to a new rulebook.
- Scores are **local text heuristics, not proofs** of completeness,
  consistency or verifiability (same framing as the in-progress SpecGuard
  scorer docstring revision).

## 2. Spec Kit extension mechanics (verified against spec-kit `c00dc05`, v1.0.13.dev0)

| Mechanism | What we use |
|---|---|
| `extension.yml` (schema 1.0) | id `specguard`; commands `speckit.specguard.{gate,trace}`; config template; hooks |
| Command files (`commands/*.md`) | Markdown prompts executed by the agent; `scripts: py:` in frontmatter → `{SCRIPT}` rendered as `<resolved python> .specify/extensions/specguard/scripts/python/...` (Spec Kit resolves the interpreter: project `.venv` → `python3` → `python`; the `py` variant is always a fallback in `select_script_variant`) |
| Hooks | `after_specify` (optional), `before_plan` (**mandatory**), `after_clarify` (optional), `after_tasks` (optional, trace) |
| Feature resolution | Mirror core `get_feature_paths`: explicit arg → `SPECIFY_FEATURE_DIRECTORY` → `.specify/feature.json` → error. **Read-only** — never persists `feature.json`. |
| Config | `.specify/extensions/specguard/specguard-config.yml` + `specguard-config.local.yml` + env `SPECKIT_SPECGUARD_*` (Spec Kit's documented layering) |
| Install | `specify extension add --dev <dir>` (dev), ZIP release / community catalog later; `.extensionignore` drops tests/experiments/tools and the plan from the installed copy (`docs/checks.md` ships — reports link to it) |

**Blocking semantics — honest limit.** A mandatory `before_plan` hook makes the
agent *run* the gate and wait; Spec Kit has no machine-enforced "halt on
non-zero exit" for hooks. Our command prompt instructs the agent to stop on
FAIL, but that is prompt-level enforcement. **Hard** enforcement is the same
CLI in CI (exit codes 0/1/2, `--fail-on`), documented in the README.

## 3. Landscape (community catalog, 175 extensions, 2026-09-25)

| Extension | Mechanism | Overlap |
|---|---|---|
| `ears` | LLM prompt applies an EARS/ambiguity rubric | Same target (requirement wording), but **the model is the detector** — non-deterministic, not repeatable in CI |
| `gates` | Deterministic shell gates | Code formatting/tests/task completion, **not** requirement text |
| `critique`, `red-team`, `spec-validate` | LLM review / human quiz | Layer-2-style review, no deterministic layer |
| `ci-guard` | Spec presence / drift | No requirement-quality analysis |

No catalog extension performs **deterministic requirement-quality detection**
on `spec.md`. That is the niche.

## 4. Experiments (details: `experiments/README.md`, results in `experiments/results/`)

### E1 — core SpecGuard, default profile, in-the-wild corpus

Corpus: every repository in the Spec Kit community extension catalog
(170 repos, shallow clone) → `specs/**/spec.md` containing `FR-###`.
**187 specs, 4,356 requirements (3,090 FR + 1,266 SC), 24 repositories.**
Authors dogfood Spec Kit to build their extensions, so the specs come from
many people, agents and models — addressing the pilot's main limitation
(single synthetic generator). Corpus bias: developer-tooling domain.

| | PASS | WARN | FAIL | smells/req |
|---|---|---|---|---|
| FR (default profile) | 80.0% | 20.0% | 0.0% | 0.66 |
| SC (default profile) | **38.5%** | 60.3% | 1.2% | 0.44 |
| pilot (synthetic, post-2a), all | 92.5% | 7.5% | 0% | — |

Findings:

1. **New mechanical core bugs (G-class, register-independent):**
   - **G6** identifier numerals flagged as `missing_unit`: `ADR-0015`,
     `FR-036`, `SC-001`, `#17`, `Phase 4`, `Pass 0`, `ISO 14971`, `7/7`
     (≈350 of 699 missing-unit hits);
   - **G7** hyphen-compound heads flagged as ambiguity: `fail-safe`,
     `share-safe`;
   - **G8** technical collocations: `clean clone`, `clean git status`,
     `clean exit`;
   - **G9** `could not` (past-tense ability) flagged as weak modal.
2. **Register items at scale (P-class):** `any` ×711 (pilot P2 confirmed —
   universal/negative-polarity quantifier), entity counts ×151 (P1),
   `different` ×56 as distinctness ("a different repository") → new **P4**.
3. **SC register is the dominant effect.** 464 of 779 non-PASS SCs have
   *zero* smell hits: they are predicate-style criteria ("two runs produce
   byte-identical reports", "never blocks waiting for input") — verifiable,
   but carrying no metric and no modal, so the core scorer rates them WARN.
4. **`[NEEDS CLARIFICATION]` markers do survive in the wild** — 9 specs,
   open markers in 5 (pilot saw zero). But the literal string is often a
   *meta-mention* ("No open `[NEEDS CLARIFICATION]` markers") → the check
   must require the payload form `[NEEDS CLARIFICATION: <question>]`.
5. **Spec Kit's own guidance contains a measurability tension:** `specify.md`
   recommends replacing "API response time is under 200ms" by "Users see
   results **instantly**" (technology-agnostic but unmeasurable), and lists
   "user-friendly messages with appropriate fallbacks" as a reasonable
   default. A deterministic gate surfaces exactly this trade-off.
6. Parser robustness: dominant form `- **FR-001**: text`; variants seen:
   wrapped continuation lines, `- **FR-020 — Title.** text`, unbolded
   `- FR-001: text` (test fixtures), FR mentions inside tables (references,
   not definitions). 70% of `tasks.md` reference `FR-###` explicitly.

### E2 — rule simulation (same corpus, fixture specs excluded)

| | default | simulated profile |
|---|---|---|
| FR PASS | 79.3% | **94.7%** |
| SC PASS | 36.6% | **93.9%** |

SC measurability classes: QUANTIFIED 349 / BINARY 794 / UNMEASURED 66.
**Caveat (in-sample):** rules were derived by inspecting this corpus, so E2
is calibration, not evaluation → E3.

### E3 — held-out evaluation (run after rules are frozen)

Holdout: repositories from the *presets / integrations / workflows / bundles*
catalogs that are **not** in the extension catalog (34 repos → 12 spec files,
of which 7 real specs from 1 repo after excluding test fixtures). Small —
reported as a sanity check, not as a generalization claim. Plus the 6-spec
synthetic pilot corpus (golden regression). Expansion path: GitHub code search
(`path:specs filename:spec.md FR-001`) once authenticated.

**Outcome (frozen rules):** FR PASS 82.2% (core) → 93.9% (speckit), replicating
calibration (94.3%); SC 41.0% → 78.7% (calibration 90.2%). Error analysis of
the 27 held-out flags: 5 genuine, 10 template-style, 12 false positives
(lexicon gaps, not fixed to keep the set held out).

## 5. Architecture

```
spec.md ──► parse_spec ──► SpecDocument(FR/SC/NFR reqs, stories, scenarios, sections, markers)
                               │
          ┌────────────────────┼─────────────────────────┐
          ▼                    ▼                         ▼
   per-requirement      structure checks (SK-*)    trace checks (TR-*)
   assess:                codified Spec Kit          spec ↔ tasks.md
   vendored core          checklist subset           (US/FR coverage,
   smell_detector ─►                                  dangling refs, IDs)
   profile filter (P1/P2/P4,
   NEEDS-CLARIFICATION → PLACEHOLDER)
   ─► scorer (FR: core; SC: outcome register)
          └────────────────────┬─────────────────────────┘
                               ▼
                 Verdict (PASS/WARN/FAIL) + findings
                               ▼
                 report: markdown (agent/human) | json (CI/tools)
                 exit code 0/1/2 (+ --fail-on threshold)
```

Principles:
- **Deterministic, stdlib-only, Python ≥ 3.9** (Spec Kit may pick the user
  project's `.venv` interpreter — any version, no extra packages).
- **LLM is never the detector.** Command prompts: run the script, quote the
  report verbatim, then (clearly separated) optional rewrite suggestions that
  never change the verdict (augmentative Layer 2). Rewrites are applied only
  on explicit user confirmation.
- **Read-only by default.** The only write is the optional report file inside
  the feature directory (`specguard-report.md`/`.json`, config-controlled).

### Key decisions (trade-offs stated)

1. **Vendor the SpecGuard core, don't depend on it.** The extension ships a
   byte-exact copy of `smell_detector.py` + `quality_scorer.py` under
   `_vendor/specguard_core/` with `VENDOR.json` (source repo, commit, SHA-256
   per file); `tools/sync_vendor.py` refreshes it; a test enforces the lock and,
   when run inside the SpecGuard monorepo, equality with upstream.
   *Chosen over* `pip`/`uvx` dependency because (a) the interpreter is the
   user's project venv — installing into it is intrusive, (b) offline/CI
   friendliness, (c) configuration identification: the exact detector version
   in use is pinned and auditable (DO-330-style tool configuration management),
   which a floating git dependency is not. Cost: sync discipline, mitigated by
   the lock test.
2. **G-class fixes go into the SpecGuard core, not the profile** (pilot
   precedent, Phase 2a): they are register-independent bugs. Each fix gets a
   regression test and a **CVA6 + seeded-fault zero-delta check**; published
   numbers are re-stamped only if they move. Only `smell_detector.py` is
   touched (the scorer has in-flight docstring edits on another branch).
3. **P-class rules live in the extension profile** (`--profile speckit`,
   default for the extension; `--profile default` = raw core for comparison).
   Every suppression is itemized in `docs/checks.md` with its corpus evidence.
4. **SC outcome register with explicit measurability classes** instead of a
   tuned number: `QUANTIFIED` (metric present) → full verifiability;
   `BINARY` (deterministic predicate, no metric: *every/never/zero/identical/
   exit code N/…*) → PASS but reported as info "no metric — Spec Kit guideline
   asks for time/percentage/count/rate"; `UNMEASURED` → verifiability 0.4 →
   WARN. Transparent and auditable; known false-negative: "All users are
   satisfied" classifies BINARY (lexicon limit, documented).
5. **`[NEEDS CLARIFICATION: …]` inside a requirement → PLACEHOLDER hit**
   (profile-scoped; the aerospace core keeps TBD/TODO only). Open markers
   anywhere in the spec → SK-001 error → FAIL (Spec Kit: "No [NEEDS
   CLARIFICATION] markers remain"). Bare mentions → info.

## 6. Check catalog (v0.1)

Per-requirement (FR, SC, NFR): 11 core smell types via vendored core + profile
filter; gate thresholds unchanged (0.75 / 0.50).

Structural — codified from Spec Kit's quality checklist / template:

| ID | Check | Severity | Source rule |
|---|---|---|---|
| SK-001 | Open `[NEEDS CLARIFICATION: …]` marker | error | "No [NEEDS CLARIFICATION] markers remain" |
| SK-002 | Unfilled template placeholder (`[FEATURE NAME]`, `[DATE]`, `[Brief Title]`, `[initial state]`, …) | error | "All mandatory sections completed" |
| SK-003 | Mandatory section missing (User Scenarios & Testing / Requirements / Success Criteria) | error | template `*(mandatory)*` |
| SK-004 | Duplicate requirement ID | error | ID uniqueness (traceability precondition) |
| SK-005 | No FR parsed | error | cannot gate an empty/unrecognized spec |
| SK-006 | User story without `(Priority: P#)` | warn | template |
| SK-007 | User story without Given/When/Then scenario | warn | "All acceptance scenarios are defined" |
| SK-008 | FR without normative keyword (MUST/SHALL/SHOULD/MAY) | warn | template `System MUST …` |
| SK-009 | SC unmeasured | warn | "Success criteria are measurable" |
| SK-010 | SC binary predicate without metric | info | SC guideline 1 (metric) |
| SK-011 | Edge Cases section missing | info | "Edge cases are identified" |
| SK-012 | Requirement ID sequence gap | info | — |
| SK-013 | Bare `[NEEDS CLARIFICATION]` mention (no payload) | info | — |

Reported as **not checked deterministically** (LLM/human territory):
"focused on user value", "written for non-technical stakeholders",
"scope clearly bounded", "no implementation details" (v0.2 candidate: info-level
technology lexicon), "requirements unambiguous" beyond the smell lexicons.

Traceability (spec ↔ tasks.md), `trace` command:

| ID | Check | Severity |
|---|---|---|
| TR-001 | Task tagged `[US#]` for a story the spec does not define | error |
| TR-002 | User story with no task tagged `[US#]` | warn |
| TR-003 | FR never referenced by any task | warn per FR if tasks cite ≥ 50% of FRs, else one info |
| TR-004 | Duplicate task ID | error |
| TR-005 | Coverage not checkable from written links (no `[US#]` tags / no FR refs / no tasks) | info |
| TR-006 | Task mentions an FR/SC/NFR ID the spec does not define | warn |

Revised after running on 184 real spec/tasks pairs (see experiments/README.md):
the first draft made every undefined ID an error and warned per unreferenced FR,
which produced 20 FAILs and 1,171 warnings, mostly from legitimate cross-feature
citations and sporadic FR citing. The first draft's TR-005 ("P1 story open while
later phases are done") was dropped: it judges progress, not traceability.

## 7. Implementation phases

| # | Deliverable | Tests |
|---|---|---|
| 1 | Core G6–G9 in `src/specguard/core/smell_detector.py` + CVA6/seeded-fault zero-delta check | regression tests in `tests/test_smell_detector.py` |
| 2 | Extension skeleton: manifest, commands, config template, `.extensionignore`, vendored core + `VENDOR.json` + sync tool | manifest schema tests; vendor lock test |
| 3 | `parse_spec` / `parse_tasks` (tolerant; wrapped lines; variants from E1) | fixture-driven parser tests incl. drifted formats |
| 4 | `profile` + `assess` (P1/P2/P4, NEEDS-CLARIFICATION hits, SC classes) | unit tests per rule; pilot-corpus golden snapshot |
| 5 | `structure` (SK-*), `trace` (TR-*), verdict aggregation | one fixture per check (positive + negative) |
| 6 | CLI (`gate`, `trace`, `--format md|json`, `--fail-on`, feature resolution), config loader | CLI/exit-code/env/config tests |
| 7 | E2E: install into a real `specify init` project with the pinned spec-kit clone; run rendered command script | `@e2e` test, skipped when `specify` unavailable |
| 8 | Experiments E1–E3 via the real implementation; results + report | reproducible scripts, pinned manifest |
| 9 | README (install, hooks, CI snippet), CHANGELOG, `docs/checks.md` | — |

## 8. Non-goals (v0.1)

- No graph/Neo4j, no commit↔task trace (SpecGuard core Phase 3).
- No LLM calls from scripts; no auto-edits of `spec.md`.
- No `plan.md` checks, no constitution checks (other extensions cover them).
- No claim that PASS means "good spec" — PASS means "no deterministic finding".

## 9. Split into a separate repository

The directory is self-contained (own `pyproject.toml` for dev/test, own tests,
vendored core). Split with
`git subtree split --prefix=integrations/spec-kit-specguard -b spec-kit-specguard`,
then point `VENDOR.json.source` at the SpecGuard release tag. The monorepo-only
upstream-equality test auto-skips outside the monorepo.
