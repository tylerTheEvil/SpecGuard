# Experiments

Does a deterministic, aerospace-calibrated requirement-smell gate produce useful
signal on real Spec Kit specifications, and what does it take to get there?

## Corpus

| Set | Source | Specs (excl. fixtures) | Repos | Requirements |
|---|---|---|---|---|
| calibration | every repo in Spec Kit's community **extension** catalog (170) | 193 (62 test fixtures excluded) | 17 | 3,489 FR · 1,438 SC · 6 NFR |
| holdout | repos in the presets / integrations / workflows / bundles catalogs, not in the extension catalog (34) | 7 (5 fixtures excluded) | 1 | 230 FR · 61 SC |
| pilot | 6 synthetic specs from the SpecGuard Phase-0 pilot (one generator model) | 6 | — | 86 FR · 34 SC |

Extension authors build their extensions with Spec Kit, so the calibration set
holds real specs written through `/speckit.specify` by many people, agents and
models — the main limitation of the earlier synthetic pilot. Specs under
`tests/`, `fixtures/` or `examples/` paths are parser fixtures, not features,
and are excluded. **Bias:** the domain is developer tooling around Spec Kit.

Provenance is pinned in [`corpus_manifest.json`](corpus_manifest.json) (repo,
commit SHA, path; Spec Kit catalogs at their commit). Spec texts are not
committed (third-party content); reproduce with:

```bash
export SPECGUARD_CORPUS_CACHE=/tmp/specguard-corpus     # ~650 MB of shallow clones
python experiments/harvest.py --from-manifest
mkdir -p /tmp/prefix-core && touch /tmp/prefix-core/__init__.py
for f in smell_detector quality_scorer; do
  git show 0f4a305:src/specguard/core/$f.py > /tmp/prefix-core/$f.py
done
python experiments/run_corpus.py --prefix-core /tmp/prefix-core
```

## Configurations (ablation)

| Config | Core | Profile |
|---|---|---|
| core-prefix | SpecGuard core at `0f4a305` (before G6–G9) | `default` |
| core | vendored core with G6–G9 | `default` |
| speckit | vendored core with G6–G9 | `speckit` (P1, P2, P4, NC, P3) |

Same parser and requirements in every configuration; only the core and the
profile change.

## Results

### Requirement gates (PASS rate; macro = mean of per-repo rates)

| Set | Kind | core-prefix | core | speckit |
|---|---|---|---|---|
| calibration | FR | 79.6% | 80.5% | **94.0%** (macro 94.1%) |
| calibration | SC | 36.2% | 36.8% | **90.2%** (macro 89.1%) |
| holdout | FR | 81.7% | 82.2% | **93.9%** |
| holdout | SC | 39.3% | 41.0% | **78.7%** |

Smell hits per FR (calibration): 0.669 → 0.564 → 0.355. No requirement FAILs
under `speckit` on either set.

### Where the change comes from

1. **Core bugs (G6–G9), register-independent:** −16.2% of all core hits on the
   calibration corpus (2,988 → 2,503; missing unit 791 → 375, ambiguity
   199 → 151, weakness 36 → 15). Gate effect is small (+0.9 pp FR) because most
   removed hits were low severity — but they were noise in every report. Fixed
   upstream; zero delta on SpecGuard's own evidence.
2. **Register rules:** `any` (810 hits), entity counts (216), `different` (68).
3. **Success-criteria register (P3) is the largest effect:** under the core
   scorer 63% of SCs do not PASS, and 464 of 779 such SCs in a first pass had
   *zero* smell hits — they are predicate-style criteria ("two runs produce
   byte-identical reports") that the modal/number-based scorer cannot credit.
   With measurability classes: BINARY 871 · QUANTIFIED 436 · UNMEASURED 131.

### Spec-level verdicts (`speckit`)

| Set | PASS | WARN | FAIL |
|---|---|---|---|
| calibration | 28.5% | 65.8% | 5.7% |
| holdout | 14.3% | 85.7% | 0% |

WARN at spec level is common (one flagged requirement or SK-009 suffices) and
non-blocking by default (`fail_on: fail`). FAIL comes from structural errors:
open clarification markers (1.0% of specs), template leftovers (1.0%),
missing mandatory sections (2.6%), duplicate IDs (1.0%).

### Holdout error analysis (rules frozen before the first holdout run)

All 27 non-PASS holdout requirements, classified by the author (a human
spot-check is still due, as for the pilot):

| Class | n | Examples |
|---|---|---|
| genuine quality issue | 5 | "can … understand how issues become reviewed PRs", "well enough that the owner can understand" |
| template-style finding (FR without MUST — precise but off-template) | 10 | "No new Python dependency: …" |
| false positive | 12 | missed BINARY on negated/passive predicates ×6 ("cannot reach a passing state", "is detected from the working tree alone"); `clean repository` ×2; `per 007 FR-050` ×2; `fail safely, preserving …` ×1; "at least one" word numeral ×1 |

Precision of WARN-level flags on this held-out repo is therefore low: 5/27
genuine, 15/27 defensible under Spec Kit's own rules. The FP classes are
lexicon gaps of the kind documented in docs/checks.md; they were **not**
fixed, so that this set stays a holdout.

### Structural findings (share of calibration specs)

SK-009 unmeasured SC 46.6% · SK-008 FR without modal 11.4% · SK-011 no Edge
Cases 9.3% · SK-007 story without G/W/T 6.2% · SK-006 story without priority
4.1% · SK-013 bare marker mention 3.6% · SK-003 missing mandatory section
2.6% · SK-001 open marker 1.0% (the synthetic pilot had zero) · SK-002
template leftover 1.0% · SK-004 duplicate ID 1.0%.

### Traceability (184 calibration spec/tasks pairs)

Verdicts: PASS 140 · WARN 41 · FAIL 3. The three FAILs are genuine duplicate
task IDs (e.g. `T058`–`T063` each used for two different tasks in two phases
of one `tasks.md`). Findings: TR-003 warn 231 / info 53 (unreferenced FRs,
per-FR only where tasks cite ≥ 50% of FRs), TR-006 24 (IDs not defined in the
feature's spec — often another feature's or project's FR), TR-002 6, TR-005
110 (coverage not checkable).

### Parser and rule iterations on the calibration set (all before the holdout run)

Each was found by inspecting findings on real specs; none is a spec defect:

| Symptom | Cause | Fix |
|---|---|---|
| SK-007 on 190 stories | "**Then** …" on a continuation line of a scenario item | scenario items span wrapped lines |
| 20 trace FAILs, mostly TR-001 | requirement bold title wrapping onto the next line (49 FRs in 4 specs) not parsed; `### US1 — … (P1)` short story headings (34 in 8 specs) not parsed; task IDs `T004-002` cut to `T004`; `T052/T053 note:` read as a task | four parser fixes |
| undefined FR refs as errors | tasks cite other features' / projects' FRs legitimately | TR-001 kept for `[US#]` tags only; FR refs → TR-006 warn |
| 1,171 TR-003 warnings | tasks cite FRs sporadically (median ≈ 30% of FRs) | per-FR warn only at ≥ 50% citation, otherwise one info finding |
| 002/SC-006 and 003/SC-006 misclassified (pilot golden) | counts with two modifiers; "top 5 endpoints" read as a metric | count pattern allows 3 modifiers; rank cut-offs excluded |

Trace FAILs went 20 → 3: four parser fixes plus one deliberate severity change
(an undefined FR reference is a warning, because it is often a legitimate
cross-feature citation). The remaining three are true positives.

## Limitations

- **Holdout is one repository** (7 specs). It supports "the FR effect
  replicates", not a generalization claim. Expansion path: GitHub code search
  for `specs/*/spec.md` with `FR-001` once authenticated.
- Calibration-set numbers are in-sample: the profile rules were derived there.
- No human-annotated ground truth yet: the gate's PASS/WARN is compared across
  configurations, not against expert labels. Precision/recall against labels
  is the next evaluation step (and the SpecGuard seeded-fault tiers already
  bound lexicon recall: 0% independent-lexicon, 28.6% blind).
- Developer-tooling domain; product/UX-heavy specs may behave differently.
