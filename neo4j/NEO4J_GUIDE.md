# SpecGuard Graph Layer — Neo4j Setup & Demo Guide

This guide walks through importing the SpecGuard knowledge graph into a
local Neo4j instance and running the demo queries.

---

## Step 1: Install and start Neo4j (if not done)

### Option A: Neo4j Desktop (easiest)
1. Download from https://neo4j.com/download/
2. Create a new local database (Neo4j 5.x)
3. Set a password
4. Start the database

### Option B: Docker
```bash
docker run \
  --name specguard-neo4j \
  --publish 7474:7474 --publish 7687:7687 \
  --env NEO4J_AUTH=neo4j/specguard \
  --volume $HOME/neo4j/data:/data \
  neo4j:5.18
```

After startup, open http://localhost:7474 in your browser and log in.

---

## Step 2: Generate the Cypher import script

From the SpecGuard project root:

```bash
python -m specguard.graph_builder
```

This produces `results/specguard_graph.cypher`. The script:
- Creates indexes on requirement IDs
- Imports 64 Requirement nodes
- Imports Category, Component, Standard, Configuration nodes
- Imports Smell nodes from the SpecGuard pipeline
- Creates BELONGS_TO, MENTIONS, REFERS_TO, APPLIES_TO, HAS_SMELL relationships

**Expected stats:** 107 nodes, 171 relationships.

---

## Step 3: Import into Neo4j

### Option A: Neo4j Browser
1. Open http://localhost:7474
2. Open `results/specguard_graph.cypher` in a text editor
3. Copy all contents
4. Paste into Neo4j Browser query bar
5. Press Ctrl+Enter (or the play button)

The first time will take a few seconds. After that you should see
"Added 107 nodes, created 171 relationships, ..."

### Option B: cypher-shell
```bash
cypher-shell -u neo4j -p specguard < results/specguard_graph.cypher
```

---

## Step 4: Run demo queries

Open `results/demo_queries.cypher`. Each query is separated by a comment
header. Copy one at a time into Neo4j Browser to see results.

**Recommended order for a supervisor demo:**

1. **Q1** — Visualize the entire graph (gives the "wow" moment — show
   the structure visually)
2. **Q15** — Dashboard summary (shows the breadth of the dataset)
3. **Q2** — Requirements about L1WTD (shows targeted retrieval)
4. **Q8** — Safety-critical with smells (shows the gate-decision use case)
5. **Q14** — Potential conflicts (shows what graph reveals that
   single-requirement analysis cannot)

---

## Step 5: Talking points for supervisor

### What this graph demonstrates

**Beyond what the smell detector alone can do:**

1. **Cross-requirement reasoning** — Q14 finds requirement pairs that
   share components, candidates for contradiction analysis. This is
   impossible at the single-requirement level.

2. **Standards traceability** — Q7 shows which external standards are
   referenced and how often. Required by DO-178C / DO-254 traceability
   matrices.

3. **Targeted impact analysis** — Q9 shows the blast radius of changing
   a component (which requirements are affected).

4. **Coverage gap detection** — Q5 identifies mandatory requirements
   that lack external anchors (no standard reference, no component
   mention) — these are suspicious because they are too generic to
   verify.

5. **Quality heat map** — Q13 shows which components have the most
   problematic requirements, useful for prioritizing rework.

### Architectural significance

This graph is **layer 1 + layer 2** of the three-layer architecture
described in the dissertation plan:

- **Layer 1**: Requirements graph (Requirement nodes + structural
  relations) — implemented now.
- **Layer 2**: Domain entities (Component, Standard, Configuration,
  Property nodes) — implemented now.
- **Layer 3**: Regulatory constraints (DO-178C / DO-254 Objective nodes
  with SATISFIES / VIOLATES relationships) — **the second scientific
  novelty** of the dissertation.

Adding layer 3 will allow Cypher queries of the form:
> "Show all DO-254 Section 6.3.3 objectives that are NOT covered by any
> mandatory requirement."

This is what makes the graph approach distinctive — codification of
regulatory knowledge as queryable artifacts, not just plain text rules
in a checklist.

### Why this beats vector databases for SpecGuard

Vector databases (Pinecone, Chroma, etc.) embed text into high-dimensional
vectors and find semantically similar items. Useful for retrieval, but
they cannot answer:

- "Are these two requirements logically contradictory?" (requires
  structural reasoning)
- "Which DO-254 objective is satisfied by this requirement?" (requires
  explicit relationships)
- "What is the impact radius of changing component X?" (requires graph
  traversal)

A property graph natively supports all of the above. This is also why
Microsoft's GraphRAG (2024) outperforms vector RAG on multi-hop
reasoning tasks.

---

## Step 6: Validate without Neo4j (optional)

If Neo4j is not available, you can run the same queries via NetworkX:

```bash
python notebooks/graph_queries_local.py
```

This produces the same semantic results as the Cypher queries, useful
for fast iteration during development.

---

## What's next (for after the demo)

1. **Manual REFINES relationships** — Add domain expert annotations
   marking which requirements refine which (e.g., L1W-30 refines L1W-10
   by specifying configurations).

2. **LLM-augmented entity extraction** — Use an LLM to extract entities
   beyond the hand-curated dictionary. The deterministic baseline stays;
   LLM additions are flagged as such for auditability.

3. **DO-254 objectives codification** — The third scientific novelty.
   Each objective from DO-254 sections 6.3.x becomes a node, requirements
   are linked via SATISFIES, and Cypher queries verify coverage.

4. **GraphRAG layer** — Combine graph queries with LLM reasoning. For
   example, given a question about a requirement, retrieve its 1-hop
   neighborhood in the graph, then pass to LLM as structured context.
