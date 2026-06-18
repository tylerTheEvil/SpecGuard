"""Graph layer: knowledge graph construction and query.

The builder (Cypher generation) is stdlib-only and imported eagerly. The
NetworkX-backed query helpers in :mod:`specguard.graph.queries` require the
optional ``[graph]`` extra, so they are exposed lazily (PEP 562): importing
this package — or :mod:`specguard.agents`, which only needs the builder —
never imports ``networkx``. Accessing a query symbol triggers the import (and
a clear ``ImportError`` if the extra is missing). This keeps the documented
"plain pytest passes with no extras" invariant true.
"""

from specguard.graph.builder import (
    GraphNode,
    GraphRelationship,
    RequirementGraph,
    build_graph,
    graph_to_cypher,
)

# Symbols that live in queries.py and pull in networkx — loaded on demand.
_QUERY_EXPORTS = frozenset(
    {
        "graph_to_networkx",
        "q2_requirements_mentioning_l1wtd",
        "q4_smell_distribution",
        "q5_mandatory_without_external_anchors",
        "q6_cross_cutting_requirements",
        "q7_standards_coverage",
        "q8_safety_critical_with_smells",
        "q14_potential_conflicts",
        "q15_dashboard",
    }
)

__all__ = [
    "GraphNode",
    "GraphRelationship",
    "RequirementGraph",
    "build_graph",
    "graph_to_cypher",
    *sorted(_QUERY_EXPORTS),
]


def __getattr__(name: str):  # PEP 562 — lazy import so networkx stays optional
    if name in _QUERY_EXPORTS:
        from specguard.graph import queries

        return getattr(queries, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
