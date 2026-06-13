"""Local Graph Queries (NetworkX-based).

Mirrors the Cypher demo queries using NetworkX for local validation.
This module is useful for:

1. Validating graph structure before importing into Neo4j
2. Running same analyses without requiring a Neo4j installation
3. Reproducing query results in publications (NetworkX is widely cited)

Each query function corresponds 1:1 to a Cypher query in demo_queries.cypher,
so results can be cross-checked.
"""

from __future__ import annotations

from collections import defaultdict

import networkx as nx

from specguard.core import assess_dataset
from specguard.data.cva6_requirements import get_all_requirements
from specguard.graph.builder import RequirementGraph, build_graph


def graph_to_networkx(rg: RequirementGraph) -> nx.MultiDiGraph:
    """Convert RequirementGraph to a NetworkX directed multigraph."""
    g = nx.MultiDiGraph()
    for node in rg.nodes:
        # Use composite key (label, node_id) to avoid clashes between labels
        key = (node.label, node.node_id)
        g.add_node(key, label=node.label, **node.properties)
    for rel in rg.relationships:
        from_key = (rel.from_label, rel.from_id)
        to_key = (rel.to_label, rel.to_id)
        g.add_edge(from_key, to_key, type=rel.rel_type, **rel.properties)
    return g


def _filter_nodes_by_label(g: nx.MultiDiGraph, label: str) -> list:
    return [n for n, attrs in g.nodes(data=True) if attrs.get("label") == label]


def q2_requirements_mentioning_l1wtd(g: nx.MultiDiGraph) -> list[dict]:
    """Q2: Requirements that MENTIONS the L1WTD component."""
    target = ("Component", "L1WTD")
    if target not in g:
        return []
    results = []
    for predecessor in g.predecessors(target):
        for _, _, data in g.in_edges(target, data=True):
            if data.get("type") == "MENTIONS":
                attrs = g.nodes[predecessor]
                if attrs.get("label") == "Requirement":
                    results.append(
                        {
                            "id": attrs.get("req_id"),
                            "modal_strength": attrs.get("modal_strength"),
                            "text": attrs.get("text", "")[:80] + "...",
                        }
                    )
                break
    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return sorted(unique, key=lambda x: x["id"])


def q4_smell_distribution(g: nx.MultiDiGraph) -> dict:
    """Q4: Smell distribution by category and severity."""
    distribution: dict = defaultdict(lambda: defaultdict(int))
    for u, v, data in g.edges(data=True):
        if data.get("type") != "HAS_SMELL":
            continue
        req_attrs = g.nodes[u]
        smell_attrs = g.nodes[v]
        category = req_attrs.get("category", "?")
        severity = smell_attrs.get("severity", "?")
        distribution[category][severity] += 1
    # Convert to plain dict
    return {k: dict(v) for k, v in distribution.items()}


def q5_mandatory_without_external_anchors(g: nx.MultiDiGraph) -> list[dict]:
    """Q5: Mandatory requirements that don't reference any standard or component."""
    results = []
    for req_node in _filter_nodes_by_label(g, "Requirement"):
        attrs = g.nodes[req_node]
        if attrs.get("modal_strength") != "mandatory":
            continue
        has_std = False
        has_comp = False
        for _, target, data in g.out_edges(req_node, data=True):
            target_label = g.nodes[target].get("label")
            rel_type = data.get("type")
            if rel_type == "REFERS_TO" and target_label == "Standard":
                has_std = True
            if rel_type == "MENTIONS" and target_label == "Component":
                has_comp = True
        if not has_std and not has_comp:
            results.append(
                {"id": attrs.get("req_id"), "text": attrs.get("text", "")[:120]}
            )
    return results


def q6_cross_cutting_requirements(g: nx.MultiDiGraph) -> list[dict]:
    """Q6: Requirements that mention 2+ components."""
    results = []
    for req_node in _filter_nodes_by_label(g, "Requirement"):
        components = []
        for _, target, data in g.out_edges(req_node, data=True):
            if data.get("type") == "MENTIONS" and g.nodes[target].get("label") == "Component":
                components.append(g.nodes[target].get("name"))
        if len(components) >= 2:
            results.append(
                {
                    "id": g.nodes[req_node].get("req_id"),
                    "components": components,
                    "count": len(components),
                }
            )
    return sorted(results, key=lambda x: -x["count"])


def q7_standards_coverage(g: nx.MultiDiGraph) -> list[dict]:
    """Q7: Reference count for each standard."""
    counts = defaultdict(list)
    for u, v, data in g.edges(data=True):
        if data.get("type") == "REFERS_TO" and g.nodes[v].get("label") == "Standard":
            counts[g.nodes[v].get("name")].append(g.nodes[u].get("req_id"))
    results = [
        {"standard": std, "count": len(reqs), "referencing": reqs}
        for std, reqs in counts.items()
    ]
    return sorted(results, key=lambda x: -x["count"])


def q8_safety_critical_with_smells(g: nx.MultiDiGraph) -> list[dict]:
    """Q8: Safety-critical requirements with quality smells."""
    results = []
    for req_node in _filter_nodes_by_label(g, "Requirement"):
        attrs = g.nodes[req_node]
        if not attrs.get("safety_critical"):
            continue
        smells = []
        for _, target, data in g.out_edges(req_node, data=True):
            if data.get("type") == "HAS_SMELL":
                s = g.nodes[target]
                smells.append(
                    {
                        "type": s.get("smell_type"),
                        "severity": s.get("severity"),
                        "trigger": s.get("trigger"),
                    }
                )
        if smells:
            results.append({"id": attrs.get("req_id"), "smells": smells})
    return results


def q14_potential_conflicts(g: nx.MultiDiGraph) -> list[dict]:
    """Q14: Pairs of requirements sharing 2+ components — conflict candidates."""
    # Build req -> set of components
    req_components: dict = {}
    for req_node in _filter_nodes_by_label(g, "Requirement"):
        comps = set()
        for _, target, data in g.out_edges(req_node, data=True):
            if data.get("type") == "MENTIONS" and g.nodes[target].get("label") == "Component":
                comps.add(g.nodes[target].get("name"))
        req_components[req_node] = comps

    results = []
    req_nodes = list(req_components.keys())
    for i, ra in enumerate(req_nodes):
        for rb in req_nodes[i + 1 :]:
            shared = req_components[ra] & req_components[rb]
            if len(shared) >= 2:
                results.append(
                    {
                        "req_a": g.nodes[ra].get("req_id"),
                        "req_b": g.nodes[rb].get("req_id"),
                        "shared": list(shared),
                        "count": len(shared),
                    }
                )
    return sorted(results, key=lambda x: -x["count"])[:15]


def q15_dashboard(g: nx.MultiDiGraph) -> list[dict]:
    """Q15: Dashboard — per-category requirement summary."""
    by_cat: dict = defaultdict(
        lambda: {"total": 0, "safety_critical": 0, "mandatory": 0, "recommended": 0}
    )
    for req_node in _filter_nodes_by_label(g, "Requirement"):
        attrs = g.nodes[req_node]
        cat = attrs.get("category", "?")
        by_cat[cat]["total"] += 1
        if attrs.get("safety_critical"):
            by_cat[cat]["safety_critical"] += 1
        strength = attrs.get("modal_strength")
        if strength == "mandatory":
            by_cat[cat]["mandatory"] += 1
        elif strength == "recommended":
            by_cat[cat]["recommended"] += 1
    return [{"category": k, **v} for k, v in sorted(by_cat.items(), key=lambda x: -x[1]["total"])]


def main() -> None:
    print("=" * 70)
    print("SPECGUARD — LOCAL GRAPH QUERIES (NetworkX)")
    print("=" * 70)
    print()

    # Build graph
    requirements = get_all_requirements()
    smell_results = assess_dataset(requirements)
    rg = build_graph(requirements, smell_results)
    g = graph_to_networkx(rg)

    print(f"Loaded graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    print()

    # Q2
    print("Q2. Requirements mentioning L1WTD:")
    for r in q2_requirements_mentioning_l1wtd(g):
        print(f"  [{r['id']:8s}] ({r['modal_strength']:12s}) {r['text']}")
    print()

    # Q4
    print("Q4. Smell distribution by category and severity:")
    for cat, sev_dict in q4_smell_distribution(g).items():
        print(f"  {cat}: {dict(sev_dict)}")
    print()

    # Q5
    print("Q5. Mandatory requirements without external standard or component anchors:")
    q5 = q5_mandatory_without_external_anchors(g)
    for r in q5[:5]:
        print(f"  [{r['id']:8s}] {r['text']}")
    print(f"  ... ({len(q5)} total)")
    print()

    # Q6
    print("Q6. Cross-cutting requirements (mention 2+ components):")
    for r in q6_cross_cutting_requirements(g)[:8]:
        print(f"  [{r['id']:8s}] components={r['components']}")
    print()

    # Q7
    print("Q7. Standards coverage:")
    for r in q7_standards_coverage(g)[:8]:
        print(f"  {r['standard']:15s}: {r['count']:2d} references")
    print()

    # Q8 — critical findings
    print("Q8. Safety-critical requirements with quality smells:")
    q8 = q8_safety_critical_with_smells(g)
    if q8:
        for r in q8:
            print(f"  [{r['id']}]")
            for s in r["smells"]:
                print(f"    └─ {s['type']}/{s['severity']} '{s['trigger']}'")
    else:
        print("  (none — all flagged requirements are non-safety-critical)")
    print()

    # Q14
    print("Q14. Potential conflict candidates (req pairs sharing 2+ components):")
    q14 = q14_potential_conflicts(g)
    for r in q14[:5]:
        print(f"  {r['req_a']} <-> {r['req_b']}: shared={r['shared']}")
    if len(q14) > 5:
        print(f"  ... ({len(q14)} total)")
    print()

    # Q15
    print("Q15. Dashboard — per-category summary:")
    print(f"  {'category':15s} {'total':>5s} {'safety':>7s} {'mandat':>7s} {'recomm':>7s}")
    for r in q15_dashboard(g):
        print(
            f"  {r['category']:15s} "
            f"{r['total']:5d} "
            f"{r['safety_critical']:7d} "
            f"{r['mandatory']:7d} "
            f"{r['recommended']:7d}"
        )


if __name__ == "__main__":
    main()
