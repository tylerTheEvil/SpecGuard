---
description: Run the 15 codified DO-178C / DO-254 / cross-domain compliance objectives and interpret results.
argument-hint: [--neo4j] (default: in-memory)
---

Run the SpecGuard compliance check against 15 codified regulatory objectives.

## Step 1 — Choose the backend

By default, run with the in-memory backend (no database needed):

```
.venv/bin/specguard comply --memory
```

If the user passes `--neo4j` in `$ARGUMENTS`, run against the live Neo4j database:

```
.venv/bin/specguard comply --neo4j
```

If `--neo4j` is requested and the `[graph]` extra is not installed, report: "Neo4j compliance requires the [graph] extra — run `pip install -e '.[graph]'`." Then fall back to `--memory` and note the fallback.

## Step 2 — Present compliance results verbatim

Present the full CLI output in a fenced code block labelled exactly:

```
SpecGuard compliance check (Layer 3, deterministic):
```

The output includes backend, objectives checked, passing count and percentage, and violation count.

## Step 3 — Analyst note (clearly separated)

Add a section headed exactly:

```
Analyst note (LLM, augmentative):
```

In this section:

1. **Objective distribution**: note how many objectives are from each standard (7 DO-178C, 5 DO-254, 3 cross-domain).
2. **Passing vs violations**: comment on the 9/15 pass rate (60%) and the violation count. Put this in context — the 168+ violations on CVA6 mostly reflect mock DAL/level/traceability metadata in the demo graph (not real CVA6 defects); say this honestly.
3. **Cross-domain objectives**: these 3 objectives (CROSS-HW-SW-1, CROSS-TIMING-1, CROSS-SAFETY-1) are the architectural novelty of the dissertation — they bind DO-178C software requirements to DO-254 hardware requirements and have no published precedent. Explain briefly what they check.
4. **Layer integration note**: if the `--memory` backend was used, note that the L1W-60, PPA-50, and PPA-60 requirements detected by the Layer 1 smell detector are also flagged as DO-178C A-3-2 violations — this demonstrates the Layer 1 ↔ Layer 3 integration.
5. **Scope honesty**: these 15 objectives are a representative subset, not a full DO-178C/DO-254 codification. Full codification (~700+ hours) is out of scope for this dissertation. Say this if the user asks.

## Hard rules

- **Never substitute your own judgment for the detector's verdict.** The compliance pass/fail verdict comes from the tool only.
- **Quote tool output verbatim and attributed** — always in a labelled code block.
- **LLM commentary is always clearly separated** and labelled as augmentative.
- **Be honest about mock metadata**: the in-memory demo graph uses synthetic DAL/level/traceability data, so violation counts reflect the demo setup, not genuine CVA6 compliance status.
- **Never describe cross-domain objectives as "detecting conflicts"** — they check binding completeness; conflict detection is Layer 2 (FSARC) + Layer 3 (SMT).
- **Never write to Neo4j** from this command — comply is read-only.
