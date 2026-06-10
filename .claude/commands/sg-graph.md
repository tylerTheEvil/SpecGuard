---
description: Run named graph queries (q6/q8/q14) or translate a natural-language question to read-only Cypher.
argument-hint: q6 | q8 | q14 | <natural language question about the graph>
---

Query the SpecGuard knowledge graph — named NetworkX queries or read-only Cypher.

## Step 1 — Interpret the argument

`$ARGUMENTS` is one of:
- `q6` — run the named query q6 (requirements mentioning 2+ components)
- `q8` — run the named query q8 (safety-critical requirements with smells)
- `q14` — run the named query q14 (requirement pairs sharing 2+ components — conflict screening)
- A natural-language question about the graph (e.g., "which requirements mention the CSR component?", "how many smell nodes are in the graph?")

## Step 2a — Named queries (q6, q8, q14)

Run:
```
.venv/bin/specguard graph <named>
```

Present the full output verbatim in a code block labelled "SpecGuard graph query <named>:".

**Special rule for q14**: the results must be described as "conflict candidates screened by shared-component topology", never as "conflicts detected". q14 is a screening filter that identifies requirement pairs sharing 2+ components — it returns candidates for further conflict analysis (Layer 2 FSARC + Layer 3 SMT). Describing its output as "conflicts" overclaims and is architecturally incorrect.

## Step 2b — Natural-language questions

Translate the question to a READ-ONLY Cypher query. Only `MATCH` and `RETURN` are allowed — no `CREATE`, `MERGE`, `DELETE`, `SET`, or write operations.

Run:
```
.venv/bin/specguard graph --cypher "YOUR CYPHER HERE"
```

If the CLI refuses the query with "Refused: ...", that means the query contains a write operation. Do **not** attempt to work around the refusal by rephrasing into a write. Report: "The query was refused because it contains a write operation. SpecGuard's graph command is read-only. To write to the graph, use `/sg-import` (for requirements) or `/sg-extract` followed by `/sg-extract` review (for LLM-proposed edges)."

Note: the `--cypher` flag requires Neo4j to be running and the `[graph]` extra installed. If the connection fails, fall back to named queries (q6/q8/q14) which use the in-memory NetworkX graph and need no database.

Present the full output verbatim in a code block labelled "SpecGuard graph query (Cypher):".

## Step 3 — Interpret results

After presenting the verbatim output, add a section headed:

```
Analyst note (LLM, augmentative):
```

Interpret the results in plain language:
- For q6: identify which requirements are most cross-cutting (most components), and what that implies for change-impact analysis.
- For q8: explain why smell-bearing safety-critical requirements are the highest priority for refinement.
- For q14: describe the results as **conflict candidates screened** — explain that each pair shares component mentions and therefore warrants human review for potential conflicts, but is NOT confirmed as a conflict. Recommend Layer 2 FSARC analysis for each candidate.
- For Cypher results: interpret the returned data in the context of the question asked.

## Hard rules

- **Never substitute your own judgment for the detector's verdict.** Graph results are tool output.
- **Quote tool output verbatim and attributed** — always in a labelled code block.
- **LLM commentary is always clearly separated** and labelled as augmentative.
- **q14 results are conflict candidates screened, never "conflicts detected".** This is a hard anti-pattern per the project's CLAUDE.md.
- **Never issue write Cypher.** If the CLI refuses a query, report the refusal and do not try to work around it.
- **Never write to Neo4j** from this command — all graph operations here are read-only.
