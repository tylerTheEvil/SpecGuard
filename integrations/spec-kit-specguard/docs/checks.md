# Check catalog

Every rule the gate applies, where it comes from, and the evidence behind it.
Corpus numbers refer to the calibration set (193 in-the-wild specs, 17
repositories, 4,884 requirements) unless marked *holdout*; see
[experiments/README.md](../experiments/README.md).

## 1. Requirement wording — vendored SpecGuard core

11 smell types, lexicon + regex, deterministic (`_vendor/specguard_core/smell_detector.py`).
Methodology: Femmer et al. 2017 (requirement smells); scoring adapted from
Zakeri-Nasrabadi et al. 2024; characteristics per ISO/IEC/IEEE 29148 (the
standard defines the characteristics, the lexicons operationalize them — this
is not an implementation of the standard).

| Type | Severity | Affects score |
|---|---|---|
| ambiguity (`fast`, `appropriate`, `secure`, …) | medium | verifiability |
| vagueness (`some`, `several`, `etc`, …) | medium/high | verifiability |
| subjectivity (`as appropriate`, `best practice`, …) | medium | verifiability |
| comparative without baseline (`faster`, `better`) | medium | verifiability |
| missing unit (bare numerals) | low | verifiability |
| optionality (`if possible`, `where applicable`) | high | completeness |
| placeholder (`TBD`, `TODO`; in `speckit` also `[NEEDS CLARIFICATION: …]`) | high | completeness (×2.5) |
| implicit reference (`it`, `this`, `that` in subject position) | low | completeness |
| weakness (`might`, `could`, `may want to`) | high | none (reported) |
| non-verifiable verb after a modal (`handle`, `manage`, `process`) | low | none (reported) |
| negative statement (`MUST NOT`; double negation) | low/high | none (reported) |

Gate per requirement: overall = 0.30·C + 0.25·S + 0.45·V; PASS ≥ 0.75, WARN ≥
0.50, FAIL < 0.50 (unchanged from the core).

### Core fixes found through this extension (upstream, register-independent)

Fixed in `src/specguard/core/smell_detector.py`, then vendored. Zero delta on
CVA6 (64), UAV (20), the spec-kit pilot corpus (120) and all seeded-fault tiers.
Measured effect on the calibration corpus (core before → after): 2,988 → 2,503
hits (−16.2%); missing unit 791 → 375, ambiguity 199 → 151, weakness 36 → 15.

| ID | Bug | Hits removed | Example |
|---|---|---|---|
| G6 | identifier numerals flagged as missing unit | 416 | `ADR-0015`, `FR-036`, `#17`, `7/7`, `Phase 4`, `ISO 14971` |
| G7 | hyphen-compound heads flagged as ambiguity | 48 (G7+G8) | `fail-safe`, `share-safe` (intensifiers such as `super-fast` still flagged) |
| G8 | `clean` collocations / verb use flagged as ambiguity | (above) | `clean clone`, `clean working tree`, `MUST clean the cache` |
| G9 | `could not` (past-tense inability) flagged as weak modal | 21 | "the reason it could not be loaded" |

Residual gaps seen on the *holdout* (not fixed, to keep it held out):
`per 007 FR-050` (feature number after "per"), `clean repository`.

Review follow-up (2026-09-28): G7 now exempts only the complete compounds
`fail-safe`, `thread-safe` and `share-safe`. Unknown prefixes such as
`lightning-fast` retain warnings. The corpus figures above describe the original
G6–G9 run; they have not been remeasured for this correction.

(G1–G5 were found by the earlier synthetic pilot; see SpecGuard
`results/speckit_pilot/pilot_report.md`.)

## 2. `speckit` profile (register rules, extension default)

Hit filters and success-criterion scoring for Spec Kit's product-spec idiom.
None changes a detector; `--profile default` switches them all off.

| Rule | What | Evidence (calibration hits) |
|---|---|---|
| P1 | missing-unit hit on a count of discrete entities is dropped (`up to 10 stories`, `1,000 concurrent redirect requests`) | 216 |
| P2 | vagueness hit on `any` is dropped — universal / negative-polarity quantifier (`reject any expired code`, `MUST NOT introduce any new state file`) | 810 |
| P4 | vagueness hit on `different` is dropped — distinctness (`a different repository`) | 68 |
| NC | each open `[NEEDS CLARIFICATION: …]` inside a requirement adds a high placeholder hit | — |
| P3 | success criteria scored in the outcome register (below) | 1,438 SCs |

### P3 — success-criterion measurability

Spec Kit writes success criteria as modal-free outcome statements by design
("90% of users complete checkout in under 3 minutes"); the core scorer would
rate every one of them as lacking commitment. In the outcome register the
completeness modal bonus is granted, and verifiability comes from an explicit
class:

| Class | Detected by | Verifiability base | Typical gate |
|---|---|---|---|
| QUANTIFIED | percentage, number + time/size/rate unit, comparator + number (`under 2`, `at least 3`), ratio `N/M`, entity count (not after `top/first/last`) | 1.00 | PASS |
| BINARY | absolute predicate: `every/all/each/no/none/never/always/zero/identical/byte-identical/exactly/same/unchanged`, `exits (code) N`, `passes/fails/rejects/matches/succeeds/green` | 0.85 | PASS + SK-010 info |
| UNMEASURED | neither | 0.40 | WARN + SK-009 |

Calibration distribution: BINARY 871 · QUANTIFIED 436 · UNMEASURED 131.

Known limits (deliberately not tuned away):
- false BINARY: "All users are satisfied" (an absolute quantifier over a
  subjective outcome) — hence SK-010 lists every metric-free criterion;
- missed BINARY on negated / passive predicates: "cannot reach a passing
  state", "is detected from the working tree alone" (*holdout*: 6 of 27 flags);
- word numerals are not counts: "at least one omission" (*holdout*: 1).

## 3. Structural checks (SK) — Spec Kit's own checklist, codified

Source: `templates/commands/specify.md` ("Specification Quality Checklist",
"Success Criteria Guidelines") and `templates/spec-template.md`, spec-kit
`c00dc05`. Prevalence = share of calibration specs with ≥ 1 finding.

| ID | Severity | Check | Spec Kit rule | Prevalence |
|---|---|---|---|---|
| SK-001 | error | open `[NEEDS CLARIFICATION: <question>]` | "No [NEEDS CLARIFICATION] markers remain" | 1.0% |
| SK-002 | error | unfilled template placeholder (exact template wording) | "All mandatory sections completed" | 1.0% |
| SK-003 | error | mandatory section missing (User Scenarios & Testing / Requirements / Success Criteria) | template `*(mandatory)*` | 2.6% |
| SK-004 | error | duplicate requirement ID | traceability precondition | 1.0% |
| SK-005 | error | no FR recognized | cannot gate an empty spec | 0% |
| SK-006 | warn | user story without `(Priority: P#)` or `(P#)` | template | 4.1% |
| SK-007 | warn | user story without a Given/When/Then scenario | "All acceptance scenarios are defined" | 6.2% |
| SK-008 | warn | FR/NFR without MUST/SHALL/SHOULD/MAY/WILL | template `System MUST …` | 11.4% |
| SK-009 | warn | success criterion UNMEASURED | "Success criteria are measurable" | 46.6% |
| SK-010 | info | success criterion BINARY (no metric) | SC guideline 1 | 95.3% |
| SK-011 | info | no Edge Cases section | "Edge cases are identified" | 9.3% |
| SK-012 | info | gap in ID sequence | — | 0.5% |
| SK-013 | info | bare `[NEEDS CLARIFICATION]` mention (no question) | — | 3.6% |

Markers are counted outside fenced code and HTML comments. The payload form is
required for SK-001 because the literal string is often a *mention* ("No open
`[NEEDS CLARIFICATION]` markers") in real specs.

Not checked (reported in every gate output): user value focus, non-technical
audience, absence of implementation details, bounded scope, ambiguity beyond
the lexicons, coverage of primary flows.

## 4. Traceability checks (TR) — `spec.md` ↔ `tasks.md`

Only written links: `[US#]` tags and FR/SC/NFR IDs in task text. Severities
set from 184 in-the-wild spec/tasks pairs (PASS 140 · WARN 41 · FAIL 3, all
three FAILs genuine duplicate task IDs).

| ID | Severity | Check | Why this severity |
|---|---|---|---|
| TR-001 | error | task tagged `[US#]` for a story the spec does not define | story tags are feature-local by convention |
| TR-002 | warn | user story without a `[US#]` task (only if tasks use story tags) | |
| TR-003 | warn / info | FR no task references | per-FR warn only when tasks cite ≥ 50% of FRs (systematic convention); otherwise one info finding — tasks cite FRs sporadically in most projects (median ≈ 30%) |
| TR-004 | error | duplicate task ID (`T004-002` hierarchical IDs supported) | IDs are identifiers |
| TR-005 | info | coverage not checkable (no tags / no FR references / no tasks) | |
| TR-006 | warn | task mentions an FR/SC/NFR ID this spec does not define | often a legitimate citation of another feature's or project's FR |
