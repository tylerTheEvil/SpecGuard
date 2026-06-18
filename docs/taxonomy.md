# Checkability taxonomy

> Dissertation **Contribution #2** — *a method of codifying compliance
> objectives*. This document defines the classification vocabulary; the
> machine-readable source of truth is `taxonomy/checkability_taxonomy.csv`,
> validated by `specguard taxonomy validate`.

The taxonomy answers one question for every regulatory objective: **how can it
be verified?** It classifies each objective by a *semantic class*, derives a
*checkability zone* from that class, and — when the objective is machine- or
screen-checkable — records the *topological template* and *decision rule* used
to codify it.

This is **screening, not proof.** Where the codified check is a graph pattern,
it verifies the *existence/consistency of asserted evidence metadata*, not the
*validity of the evidence content* (see the trust-boundary note below).

## Checkability zones

| Zone | Meaning |
|------|---------|
| `machine` | The codified subclaim is **fully decided** by the graph *given trusted evidence metadata*. |
| `screened` | The machine check is a **necessary-but-not-sufficient proxy** that can miss; residual judgement is human. |
| `human` | There is **no machine proxy** at all; the objective is verified by human review. |

The zone is **derived from the semantic class** (the loader/validator enforces
this via `zone_for_class`):

| Semantic class | Zone |
|----------------|------|
| `structural`, `structural-consistency`, `traceability`, `numerical-consistency`, `coverage` | `machine` |
| `hybrid` | `screened` |
| `not-machine-checkable` | `human` |

### The zone classification line (the calibration finding)

> A row is `machine` when the codified subclaim is fully decided by the graph
> **given trusted evidence metadata**; `screened` when the machine check is only
> a necessary-but-not-sufficient proxy that can miss; `human` when there is no
> machine proxy at all.

"Existence is machine, validity is human" objectives — **A3-3, A7-1, A7-3,
6.3.1, 6.3.2** — stay `machine` *for the existence subclaim*, with a
trust-boundary note. They are **not** `hybrid`, because the graph fully decides
the existence subclaim. `hybrid` is reserved for **heuristic** proxies (the
canonical example is **A3-2**: "unambiguous/accurate" screened by smell
detection, which is necessary-not-sufficient).

## Topological templates

The graph shapes a codified objective compiles to:

| ID | Name | Shape |
|----|------|-------|
| `T1-mandatory-edge` | Mandatory edge | A node of a given type/filter must have a required incoming/outgoing edge to a target type. |
| `T2-disjunctive` | Disjunctive obligation | `T1` composed with a guard clause: `(edge A) OR (condition AND edge B)`. |
| `T3-coreference-consistency` | Coreference consistency | Two artifacts referencing the same entity must carry a mutual-consistency edge (detects its **absence**). |
| `T4-numerical-aggregation` | Numerical aggregation | An aggregate over children must satisfy a numeric relation against a parent (e.g. `SUM(child) <= parent`). |
| `T5-conjunctive-cross-domain` | Conjunctive cross-domain | A node must have required edges from **both** domains (SW **and** HW). |
| `T6-proxy-screen` | Proxy screen | A deterministic necessary-condition proxy stands in for a non-decidable predicate (`hybrid`/`screened`). |

## Decision rules

The human classification heuristics (the classification itself is
human-authored in the CSV; these are the rationale vocabulary):

| Rule | Trigger | → class | → template |
|------|---------|---------|-----------|
| **DR1** | Asserts a trace/derivation link between two artifact types | `traceability` | `T1` |
| **DR2** | Asserts *all X have some Y* (completeness over a population) | `coverage` | `T1` |
| **DR3** | Asserts a numeric/unit relation that must hold | `numerical-consistency` | `T4` |
| **DR4** | Two artifacts referencing the same entity must agree | `structural-consistency` | `T3` |
| **DR5** | Quality predicate (accurate/correct/adequate) with **no** machine proxy | `not-machine-checkable` | — (human) |
| **DR6** | Quality predicate **with** a deterministic necessary-condition proxy | `hybrid` | `T6` |
| **DR7** | Disjunctive/conjunctive composition of the above | (per parts) | `T2` / `T5` |

## Trust boundary

The graph checks **that asserted evidence metadata exists and is internally
consistent — not that the evidence is valid.** Concretely:

- **A7-3** checks that a `VERIFIES` edge carries `coverage_type='MC/DC'` — i.e.
  that MC/DC is *asserted*. It does **not** check that MC/DC was *achieved*;
  that is the job of a qualified coverage analyzer.
- **A7-1** checks that a test *exists* for each requirement, not that the test
  *procedure is correct*.
- **A3-3** checks that a performance/timing/memory HLR is *linked* to a hardware
  characteristic, not that the constraint value is actually *compatible*.

These objectives are kept `machine` **for the existence subclaim** under the
explicit assumption of trusted evidence metadata. The validity subclaim is human.

## DO-254 section numbering — reconstruction notice

> **DO-254 has no Annex-A-style objective table.** The section numbers used for
> the DO-254 rows (`6.2.1`, `6.2.2`, `6.3.1`, `6.3.2`, `6.4.1`) are **our
> reconstruction** for cross-referencing, marked with `*` in the CSV
> `table_section` and `notes_disputed` fields. They **must be verified against
> the standard text** before any external use. The DO-178C objective references
> (Tables A-3, A-4, A-7) are the real table identifiers; the *paraphrases* are
> ours and are **not** verbatim objective text.

## CLI + reproducibility

```bash
specguard taxonomy validate          # exit 0 clean / 1 invalid / 2 unreadable; --json
specguard taxonomy stats             # counts per standard / zone / class / template; --json

# Figure (needs the [viz] extra; never imported by the core):
pip install -e ".[viz]"
python scripts/coverage_map.py --calibration   # writes results/coverage_map.{png,csv}
```

The loader/validator are **stdlib-only** and run in the CI `core` job with no
extras, so the taxonomy is continuously FK-checked against the real
`ComplianceConstraint` symbols. The coverage-map figure carries a **CALIBRATION
SUBSET** stamp whenever it is built from the 15 seed objectives — those were
*selected for codifiability*, so the figure is a calibration artifact, **not** a
representative coverage result.
