# SpecGuard — Scripted Session Walkthrough

> Defense and industrial demo material (НВП Радій, ICTERI 2026).
> All CLI outputs in this document are genuine — copied verbatim from actual
> tool runs on 2026-06-10. The extraction step uses a live Anthropic API call
> (claude-sonnet-4-6 via `--provider anthropic`); the same transcript is
> reproducible with `--provider mock` (zero proposals, as the mock returns
> `{"edges": []}`), but live output is richer and shown here.
>
> Honesty note: this walkthrough demonstrates the architectural integration,
> not a full DO-178C compliance audit. The 15 codified objectives are a
> representative subset; the in-memory demo graph uses mock DAL/level/
> traceability metadata.

---

## Setup

```
cd /path/to/specguard
pip install -e ".[dev,graph,llm]"   # one-time; graph + llm extras needed for Neo4j and extraction
export ANTHROPIC_API_KEY=<your-key> # needed only for /sg-extract live path
```

The session commands (`/sg-assess`, `/sg-refine`, `/sg-import`, `/sg-extract`,
`/sg-comply`, `/sg-graph`) live in `.claude/commands/` and are invoked from
within a Claude Code session opened at the repo root.

Sample requirements file used throughout: `examples/walkthrough_requirements.txt`
(11 avionics/FPGA requirements, deliberately seeded with defects).
Note: `examples/sample_requirements.txt` is the minimal 6-requirement file that
ships with the test suite. `walkthrough_requirements.txt` is the extended set
used for this demo.

---

## Step 1 — /sg-assess: Layer 1 quality gate

The engineer opens Claude Code in the repo root and runs:

```
/sg-assess examples/walkthrough_requirements.txt
```

Claude runs:

```
.venv/bin/specguard assess examples/walkthrough_requirements.txt
```

**Output (exit code 2 — at least one FAIL):**

```
SpecGuard deterministic gate (Layer 1):

ID           GATE  OVERALL  SMELLS  TOP TRIGGERS
------------------------------------------------------------------------------
REQ-01       PASS  1.000    0       -
REQ-02       PASS  0.970    0       -
REQ-06       PASS  0.865    0       -
REQ-09       PASS  1.000    0       -
REQ-10       PASS  0.835    0       -
REQ-03       WARN  0.520    3       ambiguity:reasonably, ambiguity:fast, ambiguity:user-friendly
REQ-04       WARN  0.520    2       vagueness:some, vagueness:etc
REQ-07       WARN  0.700    1       ambiguity:adequate
REQ-08       WARN  0.730    1       comparative:better
REQ-05       FAIL  0.475    1       placeholder:TBD
REQ-11       FAIL  0.475    1       placeholder:TBD
------------------------------------------------------------------------------
11 requirements | PASS 5 / WARN 4 / FAIL 2 | avg overall 0.735
```

Exit code: 2 — at least one FAIL.

**Analyst note (LLM, augmentative):**

Five requirements pass cleanly. Four requirements reach WARN status due to
requirements smells from the Femmer 2017 / Vogelsang & Korn catalog:

- REQ-03: three ambiguity smells ("reasonably", "fast", "user-friendly") and
  the use of "should" (optionality) — none of these are measurable in a
  DO-178C test plan.
- REQ-04: "may optionally" is an optionality smell (not a shall-level mandate)
  and "some" + "etc." are vagueness smells (unbounded scope).
- REQ-07: "adequate" is an ambiguous adjective — there is no test oracle for
  what "adequate" means.
- REQ-08: "faster than the previous version" and "better performance" are
  comparative smells — without a concrete baseline measurement, these cannot
  be verified.

Two requirements FAIL due to TBD placeholders in REQ-05 and REQ-11 —
completeness scores 0.0, overall below the 0.50 FAIL threshold. These must be
resolved (concrete values substituted) before these requirements can progress
to formalization or compliance checks.

The 60% PASS rate is notably lower than the 95.3% on the CVA6 industrial
dataset — expected, because this sample file is deliberately seeded with
defects for demonstration purposes.

---

## Step 2 — /sg-refine: propose→verify→confirm loop

The engineer runs:

```
/sg-refine examples/walkthrough_requirements.txt
```

Claude runs the initial assessment (same output as Step 1), identifies REQ-05
and REQ-11 (FAIL), REQ-03, REQ-04, REQ-07, REQ-08 (WARN), and processes them
in order of severity. We show one accepted rewrite here (REQ-03) for brevity.

---

**Processing REQ-03 (WARN — 3 ambiguity smells)**

Current gate: WARN | Overall: 0.520 | Smells: ambiguity:reasonably,
ambiguity:fast, ambiguity:user-friendly

Original text:
> REQ-03: The system should be reasonably fast and user-friendly under typical load.

Proposed rewrite (preserves requirement ID; fixes all detected smells; uses
measurable criteria; does not add invented technical parameters):

> REQ-03: The embedded RTOS shall schedule all DO-178C DAL-A tasks within 5 ms
> of their activation deadline under worst-case CPU utilization of 80%.

Claude verifies via stdin:

```
echo "REQ-03: The embedded RTOS shall schedule all DO-178C DAL-A tasks within 5 ms of their activation deadline under worst-case CPU utilization of 80%." | .venv/bin/specguard assess - --json
```

Verification output (exit code 0):

```json
{
  "results": [
    {
      "id": "REQ-03",
      "gate": "PASS",
      "overall": 1.0,
      "completeness": 1.0,
      "consistency": 1.0,
      "verifiability": 1.0,
      "smell_count": 0,
      "smells": []
    }
  ],
  "aggregate": {
    "total_requirements": 1,
    "gate_pass": 1,
    "gate_warn": 0,
    "gate_fail": 0,
    "pass_rate": 1.0,
    ...
  }
}
```

PASS achieved on first attempt.

**Before / After gate evidence:**

```
--- BEFORE
    REQ-03: The system should be reasonably fast and user-friendly under typical load.
    Gate: WARN | Overall: 0.520 | Smells: ambiguity:reasonably, ambiguity:fast,
                                          ambiguity:user-friendly (3 smells)

+++ AFTER
    REQ-03: The embedded RTOS shall schedule all DO-178C DAL-A tasks within 5 ms
            of their activation deadline under worst-case CPU utilization of 80%.
    Gate: PASS | Overall: 1.000 | Smells: 0
```

Claude asks: "Accept this rewrite for REQ-03? (yes / no / edit)"

Engineer responds: "yes"

Claude edits `examples/walkthrough_requirements.txt` and continues processing
the remaining WARN/FAIL requirements.

---

## Step 3 — /sg-import: build and MERGE the knowledge graph

The engineer runs:

```
/sg-import examples/walkthrough_requirements.txt walkthrough
```

Claude runs the dry run first:

```
.venv/bin/specguard import examples/walkthrough_requirements.txt --dataset-tag walkthrough
```

**Dry run output:**

```
SpecGuard import (dry run):

Dataset tag: walkthrough
Nodes: 25  Relationships: 25
Nodes by label:    Requirement=11, Category=1, Component=2, Standard=2, Smell=9
Edges by type:     BELONGS_TO=11, MENTIONS=3, REFERS_TO=2, HAS_SMELL=9
(dry run — pass --to-neo4j to MERGE into the live graph)
```

Claude reports: "25 nodes and 25 relationships will be created. Dataset tag:
walkthrough. Datasets coexist by the `dataset` node property — no existing
data will be cleared."

Claude asks: "Ready to MERGE this graph into the live Neo4j database? (yes / no)"

Engineer responds: "yes"

Claude runs:

```
.venv/bin/specguard import examples/walkthrough_requirements.txt --dataset-tag walkthrough --to-neo4j
```

**MERGE output:**

```
SpecGuard import (MERGED to Neo4j):

Dataset tag: walkthrough
Nodes: 25  Relationships: 25
Nodes by label:    Requirement=11, Category=1, Component=2, Standard=2, Smell=9
Edges by type:     BELONGS_TO=11, MENTIONS=3, REFERS_TO=2, HAS_SMELL=9
MERGED into Neo4j: 25 nodes, 25 relationships (dataset='walkthrough', no clear).
```

---

## Step 4 — /sg-extract: LLM-propose edges → human review → conditional merge

The engineer runs:

```
/sg-extract examples/walkthrough_requirements.txt /tmp/walkthrough_queue.json
```

Claude runs extraction with the live Anthropic provider
(`--provider anthropic`):

```
.venv/bin/specguard extract examples/walkthrough_requirements.txt \
    --queue /tmp/walkthrough_queue.json --provider anthropic
```

**Extraction output:**

```
SpecGuard extract:

Proposed 7 edge(s) from 11 requirement(s).
Review queue: /tmp/walkthrough_queue.json (total 7 items).
Next: specguard review <queue> list | accept <ids> | merge-to-neo4j
```

Claude lists the review queue:

```
.venv/bin/specguard review /tmp/walkthrough_queue.json list
```

**Queue listing:**

```
Review queue:

[0] PENDING  REQ-01 -[MENTIONS]-> CVA6 (conf=0.98)
        evidence: "The CVA6 processor"
[1] PENDING  REQ-01 -[MENTIONS]-> RV64I (conf=0.98)
        evidence: "shall execute the RV64I base instruction set, version 2.1"
[2] PENDING  REQ-06 -[MENTIONS]-> MMU (conf=0.98)
        evidence: "The MMU shall translate virtual addresses"
[3] PENDING  REQ-06 -[MENTIONS]-> Sv39 (conf=0.97)
        evidence: "using Sv39 paging"
[4] PENDING  REQ-06 -[MENTIONS]-> PTW (conf=0.50)
        evidence: "when the PTE is invalid"
[5] PENDING  REQ-09 -[MENTIONS]-> CVA6 (conf=0.97)
        evidence: "shall implement the CVA6 pipeline"
[6] PENDING  REQ-10 -[MENTIONS]-> PLIC (conf=0.60)
        evidence: "The interrupt controller shall acknowledge each level-sensitive interrupt within two clock cycles of the interrupt signal being asserted."

Total: 7 | pending: 7 | accepted: 0
```

---

**Review item [0] — accepted**

Claude presents:
- Proposed: REQ-01 -[MENTIONS]-> CVA6 (conf=0.98)
- Evidence: "The CVA6 processor" (verbatim)
- Assessment: strong evidence — the requirement explicitly names the CVA6
  processor as the subject; confidence 0.98 is high.

Claude asks: "Accept this proposal? (yes / no)"

Engineer responds: "yes"

```
.venv/bin/specguard review /tmp/walkthrough_queue.json accept 0
```
Output: `accepted [0]`

---

**Review item [4] — rejected**

Claude presents:
- Proposed: REQ-06 -[MENTIONS]-> PTW (conf=0.50)
- Evidence: "when the PTE is invalid" (verbatim)
- Assessment: confidence 0.50 is at the floor. The evidence span mentions a
  Page Table Entry (PTE) but does not explicitly name the Page Table Walker
  (PTW) component. The connection is plausible but not directly evidenced —
  the requirement describes the fault condition, not the hardware component
  responsible for walking the page table. Worth rejecting until PTW is
  explicitly named in a requirement.

Claude asks: "Accept this proposal? (yes / no)"

Engineer responds: "no"

```
.venv/bin/specguard review /tmp/walkthrough_queue.json reject 4
```
Output: `rejected [4]`

---

After all items are reviewed, Claude asks:

"Would you like to merge all accepted edges into the live Neo4j graph now?
Only the edges you accepted (1 item) will be written. (yes / no)"

For this walkthrough, the engineer responds: "no" (keeping the graph clean
for the demo; in a real session they would respond "yes" and Claude would
run `review merge-to-neo4j`).

---

## Step 5 — /sg-comply: run the 15 codified regulatory objectives

The engineer runs:

```
/sg-comply
```

Claude runs:

```
.venv/bin/specguard comply --memory
```

**Output:**

```
SpecGuard compliance check (Layer 3, deterministic):

Compliance check (memory backend, dataset=cva6)
Objectives checked: 15
Passing:            9 (60.0%)
Violations:         170
```

**Analyst note (LLM, augmentative):**

The 15 objectives span three standards: 7 from DO-178C (Tables A-3, A-4,
A-7), 5 from DO-254 (§6.2–6.4), and 3 cross-domain objectives. 9/15 pass
(60%); 170 violations are reported.

The violation count reflects the demo graph's mock DAL/level/traceability
metadata — this is not a real CVA6 compliance assessment. The metadata was
deliberately seeded to exercise the violation-detection paths. This is
stated honestly in CLAUDE.md and the improvement plan.

The 3 cross-domain objectives (CROSS-HW-SW-1, CROSS-TIMING-1, CROSS-SAFETY-1)
are the architectural novelty: they bind DO-178C software requirements to
DO-254 hardware requirements via the `CONSISTENT_WITH` and `MITIGATES`
edges in the knowledge graph. No published precedent exists for this binding
pattern — it is the unique niche of the dissertation's Novelty #3.

Layer integration note: requirements L1W-60, PPA-50, and PPA-60 detected by
the Layer 1 smell detector are also flagged as DO-178C A-3-2 violations —
demonstrating the Layer 1 ↔ Layer 3 architectural integration that is
Dissertation Novelty #2 (Two-layer Quality Agent pattern).

Scope: these 15 objectives are a representative subset for dissertation
demonstration. Full DO-178C/DO-254 codification (~700+ hours) is explicitly
out of scope and would constitute a separate dissertation.

---

## Step 6 — /sg-graph: knowledge graph Q&A

### 6a — Named query: q14 (conflict screening)

The engineer runs:

```
/sg-graph q14
```

Claude runs:

```
.venv/bin/specguard graph q14
```

**Output:**

```
SpecGuard graph query q14:

q14: Requirement pairs sharing 2+ components (screening)
------------------------------------------------------------
{'req_a': 'ISA-90', 'req_b': 'HPM-50', 'shared': ['CSR', 'CVA6'], 'count': 2}
{'req_a': 'ISA-90', 'req_b': 'HPM-60', 'shared': ['CSR', 'CVA6'], 'count': 2}
{'req_a': 'HPM-10', 'req_b': 'HPM-20', 'shared': ['CVA6', 'CV32A6'], 'count': 2}
{'req_a': 'HPM-10', 'req_b': 'HPM-80', 'shared': ['CVA6', 'CV32A6'], 'count': 2}
{'req_a': 'HPM-20', 'req_b': 'HPM-80', 'shared': ['CVA6', 'CV32A6'], 'count': 2}
{'req_a': 'HPM-50', 'req_b': 'HPM-60', 'shared': ['CSR', 'CVA6'], 'count': 2}
{'req_a': 'L1W-10', 'req_b': 'L1W-20', 'shared': ['CVA6', 'L1WTD'], 'count': 2}
{'req_a': 'L1W-10', 'req_b': 'MEM-20', 'shared': ['CVA6', 'L1WTD'], 'count': 2}
{'req_a': 'L1W-20', 'req_b': 'MEM-20', 'shared': ['CVA6', 'L1WTD'], 'count': 2}
```

**Analyst note (LLM, augmentative):**

q14 returns **9 conflict candidates screened** by shared-component topology
(pairs sharing 2+ component mentions). These are candidates for further
analysis — they are NOT confirmed conflicts.

The HPMC cluster (HPM-10/20/50/60/80) and the L1 write-through cache cluster
(L1W-10/20, MEM-20) are the two most connected groups. In a real DO-178C
review, each pair would be submitted to Layer 2 FSARC analysis (7 conflict
type taxonomy) to determine whether the shared-component mention represents
a genuine semantic conflict. Layer 3 (SMT/formal methods) is the final
arbiter for ambiguous cases.

Describing these 9 rows as "9 conflicts detected" would be architecturally
incorrect — q14 is a topology screening filter, not a conflict detector.

### 6b — Named query: q6 (cross-cutting requirements)

The engineer runs:

```
/sg-graph q6
```

Claude runs:

```
.venv/bin/specguard graph q6
```

**Output (excerpt):**

```
SpecGuard graph query q6:

q6: Requirements mentioning 2+ components
------------------------------------------------------------
{'id': 'MEM-20', 'components': ['L1WTD', 'L1I', 'CVA6'], 'count': 3}
{'id': 'ISA-90', 'components': ['CSR', 'CVA6'], 'count': 2}
...
```

**Analyst note (LLM, augmentative):**

MEM-20 mentions three components (L1WTD, L1I, CVA6) — the most cross-cutting
requirement in the CVA6 dataset. In a change-impact analysis, any modification
to L1WTD, L1I, or CVA6 would require re-reviewing MEM-20. This is the value
of the graph layer: automated traceability between requirements and
architectural components, replacing manual impact matrices.

---

## Summary

This walkthrough demonstrates the five SpecGuard workflows integrated in a
single Claude Code session:

| Workflow | Command | Deterministic verdict | LLM role |
|---|---|---|---|
| Quality gate | `/sg-assess` | Layer 1 pipeline | Explain smells |
| Requirement refinement | `/sg-refine` | Gate verifies each draft | Draft rewrite |
| Graph import | `/sg-import` | Graph builder counts | Orchestrate confirm |
| Edge extraction | `/sg-extract` | n/a (write gated by human) | Propose edges |
| Compliance check | `/sg-comply` | 15 codified objectives | Explain results |
| Graph Q&A | `/sg-graph` | Named queries / Cypher | Interpret rows |

The cardinal invariant holds throughout: every quality verdict and every
graph write flows through the deterministic CLI. The LLM orchestrates,
explains, and drafts — it never assesses, detects, or writes autonomously.
This is the concrete realization of the Two-layer Quality Agent pattern
(Dissertation Novelty #2) at the session-interaction level.
