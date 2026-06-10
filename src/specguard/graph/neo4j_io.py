"""Merge-based Neo4j write/read helpers for the session use-case.

The existing loaders (:mod:`scripts.load_neo4j`, the UAV loader) **clear** the
whole database before loading — acceptable for the fully-reproducible demo
graphs, unacceptable once an engineer brings their own requirements into the
same DBMS. This module adds the non-destructive alternatives the unified CLI
needs and leaves the clear-and-load loaders untouched.

Neo4j Community Edition constraint (documented decision)
--------------------------------------------------------
Neo4j CE supports exactly **one database per DBMS**. We therefore cannot give
each engineer/demo dataset its own physical database. Coexistence is achieved
**by node property** instead: every node written via :func:`merge_graph` is
stamped with a ``dataset`` property equal to the caller-supplied tag, so the
CVA6 demo graph, the UAV graph, and an engineer's imported set live side by
side in one database and are separable by ``WHERE n.dataset = $tag``. MERGE
matches on ``(label, node_id)`` so re-importing the same tag is idempotent and
importing a second tag never removes the first.

Quarantine / optional-dependency contract
------------------------------------------
The ``neo4j`` driver lives in the ``[graph]`` extra, outside the stdlib-only
qualifiable core. Every ``neo4j`` import here is lazy and guarded (mirroring
:mod:`specguard.compliance.neo4j_runner`), so ``import specguard`` and the CLI
module load with no extras installed; the helpful ImportError only surfaces
when a write/read is actually attempted without the driver.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from specguard.compliance.neo4j_runner import Neo4jConfig, Neo4jGraphRunner

if TYPE_CHECKING:  # pragma: no cover - typing only
    from specguard.graph.builder import RequirementGraph


# Write-clause keywords refused by run_readonly_cypher. This is *defense in
# depth* for the conversational session use-case (so a session-issued query
# cannot accidentally mutate the graph through the read path), NOT a security
# boundary — a determined caller can always use the write helpers directly.
_WRITE_CLAUSE_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH|CALL\s*\{)\b",
    re.IGNORECASE,
)


def _resolve_runner(config: Neo4jConfig | None) -> Neo4jGraphRunner:
    """Build a connected runner. Raises the driver's ImportError if no extra."""
    runner = Neo4jGraphRunner(config)
    runner.connect()
    return runner


def merge_graph(
    graph: RequirementGraph,
    *,
    dataset_tag: str,
    config: Neo4jConfig | None = None,
) -> dict[str, int]:
    """MERGE a built graph into Neo4j, stamping nodes with a ``dataset`` tag.

    Nodes are matched on ``(label, node_id)`` and their properties updated with
    ``SET n += props``; relationships are matched on endpoint ``node_id`` and
    MERGEd by type. The function **never clears anything** — it is purely
    additive/idempotent. Every created or updated node receives
    ``n.dataset = dataset_tag`` so multiple datasets coexist in the single
    Neo4j CE database (see module docstring for the rationale).

    Single-valued-``dataset`` caveat: because ``dataset`` is one scalar
    property, a node MERGEd by two datasets (e.g. a shared ``Component`` both
    import sets MENTION) ends up tagged with the *last* writer's tag. This does
    not delete anything — it only attributes a shared entity to one dataset.
    The meaningful coexistence guarantee is per-``Requirement`` (those are
    dataset-disjoint by id) and "nothing is ever removed"; if multi-membership
    of shared entities is later required, switch this to a list property or a
    join node.

    Args:
        graph: a :class:`RequirementGraph` from ``build_graph``.
        dataset_tag: non-empty coexistence tag (e.g. ``"cva6"``, an engineer's
            project name). Whitespace-only tags are rejected.
        config: optional :class:`Neo4jConfig`; defaults to env-configured.

    Returns:
        Counts dict: ``{"nodes_merged": N, "relationships_merged": M, "dataset": tag}``.

    Raises:
        ValueError: if ``dataset_tag`` is empty/whitespace.
        ImportError: if the ``neo4j`` driver is not installed.
    """
    if not dataset_tag or not dataset_tag.strip():
        raise ValueError("dataset_tag must be a non-empty, non-whitespace string.")
    tag = dataset_tag.strip()

    runner = _resolve_runner(config)
    try:
        for node in graph.nodes:
            props = dict(node.properties)
            props["dataset"] = tag
            # Requirement nodes also expose an `id` alias (constraint queries
            # match on r.id) — mirror the load_neo4j convention.
            if node.label == "Requirement":
                props.setdefault("id", node.properties.get("req_id", node.node_id))
            runner(
                f"MERGE (n:{node.label} {{node_id: $node_id}}) SET n += $props",
                {"node_id": node.node_id, "props": props},
            )

        for rel in graph.relationships:
            runner(
                f"""
                MATCH (a:{rel.from_label} {{node_id: $from_id}})
                MATCH (b:{rel.to_label} {{node_id: $to_id}})
                MERGE (a)-[r:{rel.rel_type}]->(b)
                SET r += $props
                """,
                {
                    "from_id": rel.from_id,
                    "to_id": rel.to_id,
                    "props": dict(rel.properties),
                },
            )

        return {
            "nodes_merged": len(graph.nodes),
            "relationships_merged": len(graph.relationships),
            "dataset": tag,
        }
    finally:
        runner.close()


def merge_accepted_edges(
    edges: list[dict[str, Any]],
    *,
    config: Neo4jConfig | None = None,
) -> dict[str, int]:
    """MERGE human-accepted LLM-proposed edges into the live graph.

    Consumes the dicts produced by
    :func:`specguard.extraction.review.export_accepted_edges` (each carrying
    ``from_label``/``from_id``/``to_label``/``to_id``/``rel_type`` plus a
    ``properties`` map with provenance — ``source``, ``confidence``,
    ``evidence_span``, ``human_confirmed``). The provenance, including
    ``human_confirmed=True``, is written onto the relationship so the
    LLM-then-human origin is auditable in the graph.

    This is the **only** LLM-originated write path in the system, and it is
    human-gated *by construction*: ``export_accepted_edges`` emits ACCEPTED
    items exclusively, so anything reaching this function already passed an
    explicit human decision.

    Endpoint nodes are MERGEd (not just matched) so an accepted edge to a
    target the deterministic builder never created still lands rather than
    silently no-op'ing; the target carries no ``dataset`` tag because it
    originates from extraction, not a dataset import.

    Returns:
        ``{"edges_merged": N}``.

    Raises:
        ImportError: if the ``neo4j`` driver is not installed.
    """
    runner = _resolve_runner(config)
    try:
        merged = 0
        for edge in edges:
            runner(
                f"""
                MERGE (a:{edge['from_label']} {{node_id: $from_id}})
                MERGE (b:{edge['to_label']} {{node_id: $to_id}})
                MERGE (a)-[r:{edge['rel_type']}]->(b)
                SET r += $props
                """,
                {
                    "from_id": edge["from_id"],
                    "to_id": edge["to_id"],
                    "props": dict(edge.get("properties", {})),
                },
            )
            merged += 1
        return {"edges_merged": merged}
    finally:
        runner.close()


def run_readonly_cypher(
    query: str,
    *,
    params: dict[str, Any] | None = None,
    config: Neo4jConfig | None = None,
) -> list[dict[str, Any]]:
    """Execute a read-only Cypher query, refusing anything that can mutate.

    Rejects queries containing write clauses (CREATE, MERGE, DELETE, DETACH,
    SET, REMOVE, DROP, LOAD CSV, FOREACH, or a ``CALL { ... }`` subquery block)
    via a case-insensitive keyword scan. This is **defense in depth** for the
    session use-case — it stops an accidental mutating query issued through the
    read path — **not a security boundary**: the keyword scan is naive (e.g. a
    write keyword inside a string literal would also be refused, and a truly
    adversarial caller would just use the write helpers).

    Args:
        query: a Cypher read query.
        params: optional bound parameters.
        config: optional :class:`Neo4jConfig`.

    Returns:
        Result rows as dicts.

    Raises:
        ValueError: if the query contains a write clause.
        ImportError: if the ``neo4j`` driver is not installed.
    """
    match = _WRITE_CLAUSE_RE.search(query)
    if match:
        raise ValueError(
            f"Refused: query contains a write clause ({match.group(0).strip()!r}). "
            "run_readonly_cypher only executes read queries; use merge_graph / "
            "merge_accepted_edges for writes."
        )

    runner = _resolve_runner(config)
    try:
        return runner(query, params or {})
    finally:
        runner.close()
