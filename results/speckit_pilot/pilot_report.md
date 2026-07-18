# Spec Kit Integration Pilot — Phase 0 Report

**Date:** 2026-07-18 · **Plan:** `docs/speckit_integration_plan.md` (Phase 0)
**Verdict: GO** — with Phase 2 reshaped (see §6). The predicted FP storm did
not materialize; instead the pilot exposed one latent core scorer bug, four
mechanical detector gaps, and one real register difference (Success Criteria).

## 1. Setup

- **Spec-kit reference:** clone at `spec-kit/`, commit `57cc518` (v0.13.1.dev0,
  2026-07-17). Integration surface verified: extension system with
  `before_/after_*` hooks, mandatory-blocking semantics.
- **Corpus:** 6 feature specs, 120 requirements (86 FR + 34 SC), in
  `experiments/speckit_pilot/specs/`. Domains: photo albums (spec-kit's
  canonical example), URL shortener, log-analyzer CLI, cart discounts,
  sensor telemetry, notification preferences.
- **Generation methodology:** each spec written by an LLM agent (Claude
  Opus 4.8) faithfully executing spec-kit's `spec-template.md` +
  `specify.md` instructions — the same generation process the real
  `/speckit.specify` command drives. Agents were instructed to write
  *naturally*: neither polished nor deliberately smelly.
- **Pilot scope:** FR-### and SC-### bullets only (user stories and
  acceptance scenarios wait for the Phase 1 parser).
- **Runner:** `experiments/speckit_pilot/run_pilot.py`; raw outputs
  `pilot_default.json` / `pilot_speckit.json` in this directory.

```
.venv/bin/python experiments/speckit_pilot/run_pilot.py --profile default --json results/speckit_pilot/pilot_default.json
.venv/bin/python experiments/speckit_pilot/run_pilot.py --profile speckit --json results/speckit_pilot/pilot_speckit.json
```

## 2. Headline numbers

| | PASS | WARN | FAIL | pass rate | smells/req | avg V |
|---|---|---|---|---|---|---|
| **default — ALL** | 97 | 23 | 0 | 0.808 | 0.17 | 0.67 |
| **default — FR only** | 78 | 8 | 0 | **0.907** | 0.17 | 0.68 |
| **default — SC only** | 19 | 15 | 0 | **0.559** | 0.18 | 0.63 |
| **calibrated (sim) — ALL** | 117 | 3 | 0 | **0.975** | 0.07 | 0.80 |

Reference: CVA6 (human-written, hardware) under the same default profile:
95.3% PASS. **FRs in spec-kit register score nearly identically to CVA6
(90.7%) with no calibration at all.** The entire mismatch concentrates in
Success Criteria (55.9%) — and, as §4 shows, almost none of it comes from
smell detectors.

## 3. Where the 23 default-profile WARNs come from

- **12 of 23 have zero smell hits — all SCs.** Pure scorer mechanics, not
  detection: spec-kit Success Criteria are *modal-free outcome statements by
  design* ("90% of users complete...", per spec-kit's own Success Criteria
  Guidelines, which explicitly forbid imperative/technical phrasing), so they
  lose both modal bonuses; and their quantifications are invisible to
  `MEASURABLE_PATTERNS` (see G5).
- **11 have smell hits** — classified below.

### Hit-by-hit classification (19 hits total, default profile)

| Hits | Detector / trigger | Example context | Verdict | Rule |
|---|---|---|---|---|
| 6 | negative_statement `must not` (low) | "MUST NOT permanently delete…" | Acceptable — prohibitions are testable; informational only (this smell affects no score by design) | keep |
| 4 | vagueness `any` (med) | "redirect **any** visitor of an active short link" | Contextual FP — universal quantifier in product register; precise & testable | **P2** |
| 3 | missing_unit `000` (low) | "1**,000** concurrent redirect requests" | Mechanical FP — comma-grouped numeral tokenizes as "000" | **G1** |
| 2 | missing_unit `500`, `5` (low) | "album of up to **500** photos", "top **5** endpoints" | Contextual FP — counts of discrete entities are unit-less by nature | **P1** |
| 1 | missing_unit `2` (low) | "no more than **2** false alerts" | Contextual FP — count with explicit comparator | **P1** |
| 1 | missing_unit `12` (low) | "for at least **12** months" | Mechanical FP — calendar units absent from unit lexicon (min/hours present) | **G3** |
| 1 | vagueness `many` (high) | "MUST report how **many** lines were skipped" | Mechanical FP — "how many" interrogative collision | **G2** |
| 1 | comparative `lower` (med) | "an upper limit, a **lower** limit, or both" | Mechanical FP — noun phrase, not a baseline-less comparative | **G4** |
| 1 | comparative `larger` (med) | "into a **larger** single-photo view" | Residual FP — no clean mechanical rule; stays flagged | keep |
| 1 | ambiguity `appropriate` (med) | "show an **appropriate** empty state" | **TRUE POSITIVE** — undefined acceptance criterion | keep |

The detectors feared in the integration plan (`IMPLICIT_REFERENCE` on
"the system", `NON_VERIFIABLE` on "handle/manage/process") fired **zero**
times. The plan's central risk — an FP storm from aerospace-tuned lexicons —
**did not materialize.**

## 4. Root causes: two distinct groups

### G — general core bugs/gaps (register-independent; fix in core, not profile)

- **G1** Comma-grouped numerals ("1,000") break MISSING_UNIT tokenization → "000" flagged.
- **G2** "how many" interrogative collides with VAGUENESS `many`.
- **G3** Calendar units (day/week/month/year) missing from the unit lexicon while min/hours are present — inconsistent lexicons.
- **G4** "lower/upper limit|bound|threshold" noun phrases flagged as baseline-less comparatives.
- **G5** **Latent scorer bug:** in `MEASURABLE_PATTERNS`, `(?:%|percent)\b` — the trailing `\b` after `%` can never match before whitespace, so "90%" is *never* recognized as a measurable criterion. Also missing: under/within/no-more-than comparators; minute/hour units. Invisible on CVA6 (hardware units dominate); exposed immediately by product-style SCs.

These are worth fixing regardless of the spec-kit integration — the pilot
already paid for itself here.

### P — genuine register differences (profile-scoped, `--profile speckit`)

- **P1** Counts of discrete entities ("1000 concurrent users") are unit-less by nature in product specs → MISSING_UNIT suppressed for count-of-noun patterns.
- **P2** `any` is the universal quantifier in product specs ("reject any expired code" is precise) → VAGUENESS suppressed; in aerospace register it often masks unspecified subsets, so this stays profile-scoped.
- **P3** Success Criteria are a distinct *outcome register*: modal-free is correct style (completeness bonus granted), but **measurability becomes the dominant verifiability factor** — an unmeasurable SC scores V=0.4 → WARN. First-draft P3 granted modal credit without this guard and let a deliberately unmeasurable probe SC ("Users are satisfied…") PASS at 0.835; the guard was added and the probe now WARNs at 0.70. This preserves spec-kit's own checklist demand ("Success criteria are measurable") as a deterministic check.

## 5. Calibrated result

3 flags on 120 requirements, 0 FAIL:

1. `001/FR-014` — "**appropriate** empty state" → WARN. Genuine catch.
2. `001/FR-009` — "**larger** single-photo view" → WARN. Documented residual FP.
3. `003/SC-006` — operator task-completion criterion with no quantified threshold → WARN. Defensible: nudges toward a measurable bound (e.g., "…in under N minutes / on first attempt").

A near-silent gate on well-formed specs that still catches genuine
subjectivity and unmeasurable success criteria is exactly the desired Layer-1
behavior.

## 6. Consequences for the integration plan

1. **Phase 2 reshaped** into 2a (core fixes G1–G5, with CVA6 regression check —
   expected effect: near-zero on CVA6 numbers, must be verified and reported)
   and 2b (a *slim* `--profile speckit`: P1, P2, and the SC outcome-register
   scoring mode P3 keyed on requirement kind, which the Phase 1 parser
   provides naturally).
2. **The gate's SC value proposition sharpened:** deterministic enforcement of
   "success criteria are measurable" — a check spec-kit itself specifies but
   can only enforce via LLM self-review.
3. **New corpus finding:** all 6 generation runs produced **zero
   `[NEEDS CLARIFICATION]` markers** — the template's "max 3, prefer informed
   defaults" guidance drives markers to zero and pushes ambiguity into the
   Assumptions section. The PLACEHOLDER-channel synergy assumed in the plan is
   therefore weak in practice; Assumptions-section coverage may deserve a
   check of its own (candidate: flag FRs whose precision depends on an
   assumption never echoed in the FR).

## 7. Phase 2a post-fix verification (added 2026-07-18, same day)

G1–G5 were implemented in `src/specguard/core/` (smell_detector.py,
quality_scorer.py) with regression tests. Verification results:

**Zero regression on all existing evidence:**
- CVA6: **exactly zero delta** — no gate flips, no score changes, no
  smell-count changes on any of the 64 requirements. Published numbers
  (95.3% PASS, avg 0.961/1.000/0.777/0.888) stand unchanged.
- Seeded faults: 100% sanity / 0% independent / 28.6% blind / FPR 12.5% —
  all identical; result JSONs byte-identical.
- Full test suite: 201 passed (was 192), 32 skipped.

**Pilot corpus, default profile, after core fixes** (`pilot_default_post2a.json`):

| | PASS | WARN | FAIL | pass rate |
|---|---|---|---|---|
| pre-2a default | 97 | 23 | 0 | 0.808 |
| **post-2a default** | **111** | **9** | **0** | **0.925** |
| post-2a default, SC only | 31 | 3 | 0 | 0.912 (was 0.559) |

The remaining default-vs-calibrated gap (9 WARN vs 3 WARN) consists purely of
the P-class register items deferred to Phase 2b: `any` ×4, entity-count
MISSING_UNIT ×6 (now correctly triggering on "1,000"/"6,000" as whole tokens),
plus the residual FP and the two genuine catches.

**Note for Phase 2b:** the P1 suppression regex in the pilot runner does not
yet handle comma-grouped numerals (it matched the old "000"-artifact hits,
not the corrected "1,000" tokens); the real profile implementation must
account for this. Gate outcomes were unaffected (low-severity hits), so the
117/3/0 calibrated simulation is unchanged.

## 8. Limitations (honest)

- **Single generator, strong model.** All specs generated by one model
  (Opus 4.8) at high effort; real spec-kit runs use varied agents/models, and
  weaker generators plausibly produce smellier specs — the pilot's low smell
  yield is a *floor-setting* observation, not a yield estimate. Varying the
  generator model is a Phase 5 research question (RQ1).
- **Synthetic corpus** (though produced by the real generation process); no
  human-authored or in-the-wild spec-kit specs included. 6 specs / 120
  requirements is calibration-scale, not evaluation-scale.
- **Profile simulated in the runner**, not yet implemented in
  `src/specguard/`; the FP classifications in §3 are the author-model's
  judgments and should be spot-checked by a human before the profile is
  frozen (they are deliberately itemized above to make that review cheap).
- Gate thresholds (0.75/0.50) untouched; calibration limited to hit filtering
  and the SC register — deliberately minimal intervention.
