---
description: Parse requirements, build the knowledge graph, and optionally MERGE into Neo4j (always confirms before writing).
argument-hint: <file-path> [dataset-tag]
---

Import requirements into the SpecGuard knowledge graph with a dataset tag.

## Step 1 — Resolve path and dataset tag

Parse `$ARGUMENTS`:
- First token is the requirements file path.
- Second token (if present) is the dataset tag; if absent, derive the tag from the filename stem (e.g., `reqs.txt` → `reqs`, `my-project.csv` → `my-project`) and tell the user which tag you derived: "Using dataset tag: <tag> (derived from filename — pass a second argument to override)."

The dataset tag is a non-empty string that identifies this import in Neo4j. Multiple imports coexist by the `dataset` node property — Neo4j Community Edition is a single-database DBMS, so coexistence is by property, not separate databases.

## Step 2 — Dry run (always first)

Run the import without `--to-neo4j`:

```
.venv/bin/specguard import <file-path> --dataset-tag <tag>
```

Present the full output verbatim in a code block labelled "SpecGuard import (dry run):".

The output includes:
- Dataset tag
- Total node and relationship counts
- Breakdown by label and by relationship type
- Confirmation that it is a dry run

## Step 3 — Ask before writing to Neo4j

After presenting the dry run, ask the user:

"Ready to MERGE this graph into the live Neo4j database? This will add nodes/relationships with dataset='<tag>' — existing data from other datasets is never cleared (MERGE-based, no DELETE). (yes / no)"

**Do not proceed to Step 4 unless the user explicitly says yes in this session.**

## Step 4 — Live MERGE (only after confirmation)

Run with `--to-neo4j`:

```
.venv/bin/specguard import <file-path> --dataset-tag <tag> --to-neo4j
```

Present the full output verbatim in a code block labelled "SpecGuard import (MERGED to Neo4j):".

The output includes the MERGED node and relationship counts and confirms the dataset tag that was applied.

Note for the user: if this command fails with an ImportError about the `neo4j` driver, the `[graph]` extra is not installed — run `pip install -e '.[graph]'` from the repo root.

## Hard rules

- **Always run the dry run first.** Never run with `--to-neo4j` as the first action.
- **Never run with `--to-neo4j` without explicit user confirmation in this session.**
- **Never clear the database** — the `--to-neo4j` flag uses MERGE, not DELETE.
- **Quote tool output verbatim and attributed** — always in a labelled code block.
- **LLM commentary is always clearly separated** from tool output.
- Datasets coexist by the `dataset` property; tell the user this if they ask about overwriting.
