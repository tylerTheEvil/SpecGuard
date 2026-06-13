---
description: Propose knowledge-graph edges via LLM extraction, then walk through accept/reject per item before any graph write.
argument-hint: <file-path> [queue-file]
---

Extract candidate knowledge-graph edges from requirements using LLM proposals, then review each proposal before any graph write.

## Prerequisites check

This command requires the `[llm]` extra and `ANTHROPIC_API_KEY`:

1. Check that the `[llm]` extra is installed by attempting to import: if `specguard extract` fails with "requires the [llm] extra", tell the user to run `pip install -e '.[llm]'`.
2. Check that `ANTHROPIC_API_KEY` is set. In non-interactive shells (including most Claude sessions) the key may not be inherited from `~/.zshrc`. If extraction fails with an authentication error, tell the user to set the key explicitly: `export ANTHROPIC_API_KEY=<key>` before running, or to `source ~/.zshrc` first. Do not fail silently — report the issue clearly and fall back to explaining the expected output rather than producing no output.

## Step 1 — Resolve path and queue file

Parse `$ARGUMENTS`:
- First token is the requirements file path.
- Second token (if present) is the queue JSON path; if absent, use `/tmp/sg_extract_queue.json`.

Tell the user: "Queue file: <queue-path>"

## Step 2 — Run extraction

```
.venv/bin/specguard extract <file-path> --queue <queue-path> --provider anthropic
```

Present the full output verbatim in a code block labelled "SpecGuard extract:".

The output reports how many edges were proposed and the queue file path.

## Step 3 — List the review queue

```
.venv/bin/specguard review <queue-path> list
```

Present the full output verbatim in a code block labelled "Review queue:".

Each item in the queue is shown as:
```
[N] PENDING  SOURCE -[EDGE_TYPE]-> TARGET (conf=X.XX)
      evidence: "verbatim span from the requirement text"
```

## Step 4 — Walk through proposals item by item

For each PENDING item, present it clearly:

- Item index: N
- Proposed edge: SOURCE -[EDGE_TYPE]-> TARGET
- Confidence: X.XX
- Evidence span (verbatim from the requirement text — quote it exactly)
- Your assessment: whether the evidence span actually supports the proposed edge, or whether the connection is tenuous / potentially hallucinated (note if confidence < 0.7)

Ask the user: "Accept this proposal? (yes / no)"

**Do not accept or reject proposals in batch. Present each one and wait for the user's response.**

After the user responds, run the accept or reject command:

```
.venv/bin/specguard review <queue-path> accept <N>
```
or
```
.venv/bin/specguard review <queue-path> reject <N>
```

Report the result of each action.

## Step 5 — Ask about merge to Neo4j

After all items have been reviewed, run `list` one more time to show the final state of the queue (accepted/rejected/pending counts).

Then ask the user:

"Would you like to merge all accepted edges into the live Neo4j graph now? This runs `specguard review <queue> merge-to-neo4j` and is the only LLM-originated write path — only the edges you accepted will be written. (yes / no)"

**Do not run `merge-to-neo4j` without this explicit confirmation.**

If the user says yes:

```
.venv/bin/specguard review <queue-path> merge-to-neo4j
```

Present the full output verbatim in a code block labelled "SpecGuard review merge-to-neo4j:".

## Honesty note

LLM-proposed edges are augmentative only — they are never authoritative. The LLM proposes; you review; you confirm. Only human-confirmed edges reach the graph. This is architecturally identical to the Layer 2 analyst pattern: determinism is preserved in the core; the LLM extends coverage but never bypasses the human gate.

## Hard rules

- **Never substitute your own judgment for the detector's verdict.**
- **Quote tool output verbatim and attributed** — always in a labelled code block.
- **LLM commentary is always clearly separated** and labelled as augmentative.
- **Never accept proposals on the user's behalf.** Present each proposal and wait for explicit confirmation.
- **Never run `merge-to-neo4j` without explicit user confirmation in this session.**
- Evidence spans must be quoted verbatim from the tool output — never paraphrase them.
