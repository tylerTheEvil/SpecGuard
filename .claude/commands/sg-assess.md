---
description: Run the SpecGuard Layer 1 deterministic gate on a file or pasted requirements text.
argument-hint: <file-path> OR pasted requirement text
---

Assess requirements quality using the SpecGuard Layer 1 deterministic pipeline.

## Step 1 — Resolve the input

If `$ARGUMENTS` is a file path that exists on disk, use it directly. Otherwise treat `$ARGUMENTS` as pasted requirement text: write it to a temp file `/tmp/sg_assess_input.txt` in `ID: text` format, one requirement per line. If requirements in the pasted text lack IDs, assign them REQ-1, REQ-2, ... and tell the user which IDs you assigned.

## Step 2 — Run the deterministic gate

Run the following command from the repo root (the venv binary ensures the correct environment regardless of shell PATH):

```
.venv/bin/specguard assess <resolved-path>
```

If you need to use a temp file, run:
```
.venv/bin/specguard assess /tmp/sg_assess_input.txt
```

Capture both stdout and the exit code.

## Step 3 — Present gate output verbatim

Present the full CLI output in a fenced code block, labelled exactly as shown:

```
SpecGuard deterministic gate (Layer 1):
```

Include the full table (ID / GATE / OVERALL / SMELLS / TOP TRIGGERS) and the summary line unchanged. Do not edit, reorder, or summarise the table.

## Step 4 — State the exit code meaning

After the code block, state: "Exit code: N — " followed by:
- 0: all requirements PASS
- 1: at least one WARN, no FAIL
- 2: at least one FAIL
- 3: parse error (fix the input format and retry)

## Step 5 — Analyst note (clearly separated)

Add a section headed exactly:

```
Analyst note (LLM, augmentative):
```

In this section, in plain language: identify which requirements need attention, name the specific smells detected per requirement, and explain why each smell is a quality concern in a safety-critical (DO-178C / DO-254) context. Keep it factual — do not invent smells or gate verdicts that differ from Step 3.

## Hard rules

- **Never substitute your own judgment for the detector's verdict.** If the CLI says PASS, the gate is PASS. If it says FAIL, the gate is FAIL. You may explain but never override.
- **Quote tool output verbatim and attributed** — always in a labelled code block.
- **LLM commentary is always clearly separated** and labelled as augmentative.
- **Never write to Neo4j** from this command.
