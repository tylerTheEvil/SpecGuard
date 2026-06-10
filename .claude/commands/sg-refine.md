---
description: Propose, verify, and confirm rewrites for WARN/FAIL requirements — propose→verify→confirm loop.
argument-hint: <file-path> OR pasted requirement text
---

Run the SpecGuard propose-verify-confirm refinement loop for WARN and FAIL requirements.

## Step 1 — Initial assessment

Run the deterministic gate on the input first:

```
.venv/bin/specguard assess <resolved-path>
```

If `$ARGUMENTS` is not a file path, write the pasted text to `/tmp/sg_refine_input.txt` in `ID: text` format and assess that. Assign IDs (REQ-1, REQ-2, ...) if missing and tell the user.

Present the full gate table verbatim in a code block labelled "SpecGuard deterministic gate (Layer 1) — before refinement:".

If all requirements are PASS, report that and stop — no refinement needed.

## Step 2 — For each WARN or FAIL requirement (one at a time)

Process each WARN/FAIL requirement individually, in order of severity (FAIL first, then WARN).

For each requirement:

### 2a — Announce which requirement you are working on

State the requirement ID, its current gate, and the detected smells (from the gate output).

### 2b — Draft a rewrite

Draft a rewrite that:
- Fixes **all detected smells** for this requirement
- **Preserves the requirement ID exactly**
- **Preserves the original technical intent** — never change numeric values, thresholds, or referenced standards
- **Never adds invented facts** (new numbers, new components, new constraints not in the original)
- Uses "shall" (mandatory) rather than "should" or "may"
- Removes vague qualifiers (reasonably, adequate, better, faster) by replacing with measurable criteria where possible; if a concrete value cannot be inferred from the original, add a clearly marked `[SPECIFY: <what is needed>]` placeholder rather than inventing a number
- Removes TBD placeholders where possible; if the value is genuinely unknown, note it explicitly

### 2c — Verify the draft with the CLI

Run verify via stdin (the `-` path) to avoid modifying any file:

```
echo "REQUIREMENT-ID: draft text here" | .venv/bin/specguard assess - --json
```

If the draft spans multiple lines, write it to `/tmp/sg_refine_draft.txt` as `ID: text` and run:
```
.venv/bin/specguard assess /tmp/sg_refine_draft.txt --json
```

### 2d — Iterate up to 3 times

- If the draft reaches PASS: proceed to 2e.
- If WARN or FAIL remains: adjust the draft to address the remaining smells and re-verify. Count each attempt.
- After 3 failed attempts: present the best draft with its gate result and say explicitly: "This draft did not reach PASS after 3 attempts. The remaining smells are: [list]. I recommend manual domain-expert review." Do **not** silently lower the bar or accept a WARN as good enough for a FAIL requirement.

### 2e — Present before/after evidence

Present a clearly labelled diff:

```
--- BEFORE (ID: original text)
    Gate: WARN/FAIL | Smells: [list]

+++ AFTER (ID: rewritten text)
    Gate: PASS | Overall: X.XXX | Smells: 0
```

Include the gate evidence for both versions (from the actual CLI output).

### 2f — Ask for explicit acceptance

Ask the user: "Accept this rewrite for REQ-XX? (yes / no / edit)"

- **Wait for the user's explicit confirmation before proceeding to the next requirement.**
- Do NOT pre-accept or batch-accept across multiple requirements.
- If the user says "edit", apply their edit, re-verify with the CLI, and present the updated evidence.
- If the user says "no", move on to the next requirement without modifying anything.

## Step 3 — Write accepted rewrites back to the source file

**Only after the user has explicitly accepted a rewrite**, edit the source file to replace the original text with the accepted text. Preserve the `ID:` prefix and the requirement ID exactly.

If the input was pasted text (temp file), after all rewrites are accepted, present the complete revised set of requirements and ask the user to copy it to their target file.

## Step 4 — Final assessment

After processing all WARN/FAIL requirements and applying accepted rewrites, run the final gate:

```
.venv/bin/specguard assess <source-file>
```

Present the final gate table labelled "SpecGuard deterministic gate (Layer 1) — after refinement:".

## Hard rules

- **Never substitute your own judgment for the detector's verdict.** A requirement is refined only when `specguard assess` confirms PASS.
- **Quote tool output verbatim and attributed** — always in a labelled code block.
- **LLM commentary is always clearly separated** and labelled as augmentative.
- **Never write to the source file without explicit user acceptance per requirement.**
- **Never change numeric values, referenced standards, or technical parameters** in original requirements.
- **If a rewrite cannot reach PASS in 3 attempts, say so honestly.**
- **Never write to Neo4j** from this command.
