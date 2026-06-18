"""Graph Builder for SpecGuard.

Constructs a property graph representation of CVA6 requirements suitable for
Neo4j import. The output is a Cypher script that creates:

- Layer 1: Requirements graph (Requirement nodes + structural relations)
- Layer 2: Domain entities (Component, Standard, Configuration, Property nodes)
- Layer 3 (placeholder): Regulatory constraints (Objective nodes — to be added)

Design rationale:

The graph is built deterministically from the CVA6 dataset and SpecGuard
smell-detection results. Entity extraction uses pattern matching against
known acronyms and capitalized identifiers from the specification — not
LLM-based extraction. This keeps the graph reproducible and auditable.

In a later phase, LLM-assisted entity extraction can be added on top of
this deterministic foundation. The deterministic core is what is auditable
for DO-330 tool qualification; the LLM augmentation operates within the
boundaries set by the deterministic schema.

Reference precedents for graph-based requirement representation:
- AssertionForge (Bai et al., ICLAD 2025) — KG for hardware specs
- LocAgent (Chen et al., 2025) — graph-based code reasoning
- Microsoft GraphRAG (Edge et al., 2024) — entity-relationship KG for LLM
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from specguard.core import assess_dataset
from specguard.data.cva6_requirements import Requirement, get_all_requirements

# ============================================================================
# Entity extraction patterns
# ============================================================================

# CVA6 components — extracted by reading the specification
KNOWN_COMPONENTS = {
    "CVA6": {"full_name": "CORE-V Application class processor 6-stage", "optional": False},
    "CV64A6": {"full_name": "CVA6 64-bit configuration", "optional": False},
    "CV32A6": {"full_name": "CVA6 32-bit configuration", "optional": False},
    "L1WTD": {"full_name": "L1 write-through data cache", "optional": False},
    "L1I": {"full_name": "L1 instruction cache", "optional": False},
    "FPU": {"full_name": "Floating Point Unit", "optional": True},
    "MMU": {"full_name": "Memory Management Unit", "optional": True},
    "PMP": {"full_name": "Physical Memory Protection", "optional": True},
    "TLB": {"full_name": "Translation Lookaside Buffer", "optional": False},
    "PTW": {"full_name": "Page Table Walk", "optional": False},
    "CSR": {"full_name": "Control and Status Register", "optional": False},
    "TRI": {"full_name": "Transaction-Response Interface", "optional": False},
    "DTM": {"full_name": "Debug Transport Module", "optional": False},
    "CLINT": {"full_name": "Core-Local Interruptor", "optional": True},
    "PLIC": {"full_name": "Platform-Level Interrupt Controller", "optional": True},
}

# External standards referenced in requirements
KNOWN_STANDARDS = {
    "RV64I": "RISC-V 64-bit base ISA",
    "RV32I": "RISC-V 32-bit base ISA",
    "RVunpriv": "RISC-V User-Level ISA",
    "RVpriv": "RISC-V Privileged Architecture",
    "RVdbg": "RISC-V External Debug Support",
    "RVcompat": "RISC-V Architectural Compatibility Test",
    "AXI": "AXI Specification",
    "AXI5": "AXI5 Specification",
    "OpenPiton": "OpenPiton coherence system",
    "CV-X-IF": "Core-V eXtension interface",
    "FENCE.T": "Fence-T custom instruction",
    "RVcmo": "RISC-V Cache Management Operation",
    "Sv39": "RISC-V Sv39 virtual memory",
    "Sv32": "RISC-V Sv32 virtual memory",
}

# Configurations
KNOWN_CONFIGS = {
    "CV32A60X": "CVA6 32-bit ASIC config without MMU",
    "CV32A60AX": "CVA6 32-bit ASIC config with Sv32 MMU",
    "CV32A65X": "CVA6 32-bit dual-issue config",
    "cv32a6_imac_sv32": "CVA6 32-bit IMAC ISA with Sv32",
    "cv64a6_imacfd_sv39": "CVA6 64-bit IMACFD ISA with Sv39",
}


@dataclass
class GraphNode:
    """A node in the requirements graph."""

    label: str  # Neo4j node label (e.g., 'Requirement')
    node_id: str  # unique identifier within label
    properties: dict = field(default_factory=dict)


@dataclass
class GraphRelationship:
    """A directed relationship between two nodes."""

    from_label: str
    from_id: str
    to_label: str
    to_id: str
    rel_type: str
    properties: dict = field(default_factory=dict)


@dataclass
class RequirementGraph:
    """Container for the complete graph."""

    nodes: list[GraphNode] = field(default_factory=list)
    relationships: list[GraphRelationship] = field(default_factory=list)

    def stats(self) -> dict:
        node_counts: dict = {}
        for n in self.nodes:
            node_counts[n.label] = node_counts.get(n.label, 0) + 1

        rel_counts: dict = {}
        for r in self.relationships:
            rel_counts[r.rel_type] = rel_counts.get(r.rel_type, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_relationships": len(self.relationships),
            "nodes_by_label": node_counts,
            "relationships_by_type": rel_counts,
        }


# ============================================================================
# Entity extraction
# ============================================================================


def extract_components(text: str) -> set[str]:
    """Find component references in requirement text.

    Uses word-boundary matching against known component dictionary to
    keep extraction deterministic and auditable.
    """
    found = set()
    for component in KNOWN_COMPONENTS:
        if re.search(r"\b" + re.escape(component) + r"\b", text):
            found.add(component)
    return found


def extract_standards(text: str) -> set[str]:
    """Find external standard references in requirement text."""
    found = set()
    for std in KNOWN_STANDARDS:
        if re.search(r"\b" + re.escape(std) + r"\b", text):
            found.add(std)
    # Bracket-style references e.g. [RVpriv] are also captured by above
    return found


def extract_configurations(text: str) -> set[str]:
    """Find configuration references."""
    found = set()
    for cfg in KNOWN_CONFIGS:
        if re.search(r"\b" + re.escape(cfg) + r"\b", text):
            found.add(cfg)
    return found


def determine_modal_strength(text: str) -> str:
    """Determine the modal strength of a requirement."""
    text_lower = text.lower()
    if " shall " in f" {text_lower} ":
        return "mandatory"
    if " should " in f" {text_lower} ":
        return "recommended"
    if " may " in f" {text_lower} ":
        return "optional"
    if " must " in f" {text_lower} ":
        return "mandatory"
    return "unspecified"


# ============================================================================
# Graph construction
# ============================================================================


def build_graph(
    requirements: list[Requirement],
    smell_results: list | None = None,
) -> RequirementGraph:
    """Build the property graph from CVA6 requirements + smell detection.

    Args:
        requirements: list of Requirement objects from CVA6 dataset
        smell_results: optional list of AssessmentResult from SpecGuard pipeline

    Returns:
        RequirementGraph with nodes and relationships
    """
    graph = RequirementGraph()

    # ---- Layer 1: Requirement and Category nodes ----
    categories_seen = set()
    for req in requirements:
        # Requirement node
        graph.nodes.append(
            GraphNode(
                label="Requirement",
                node_id=req.req_id,
                properties={
                    "req_id": req.req_id,
                    "text": req.text,
                    "category": req.category,
                    "parent_section": req.parent_section,
                    "safety_critical": req.safety_critical_context,
                    "modal_strength": determine_modal_strength(req.text),
                    "token_count": len(req.text.split()),
                    "notes": req.notes,
                },
            )
        )

        # Category node (deduplicated)
        if req.category not in categories_seen:
            graph.nodes.append(
                GraphNode(
                    label="Category",
                    node_id=req.category,
                    properties={"name": req.category},
                )
            )
            categories_seen.add(req.category)

        graph.relationships.append(
            GraphRelationship(
                from_label="Requirement",
                from_id=req.req_id,
                to_label="Category",
                to_id=req.category,
                rel_type="BELONGS_TO",
            )
        )

    # ---- Layer 2: Component, Standard, Configuration nodes + MENTIONS edges ----
    components_added = set()
    standards_added = set()
    configs_added = set()

    for req in requirements:
        # Components
        for comp in extract_components(req.text):
            if comp not in components_added:
                graph.nodes.append(
                    GraphNode(
                        label="Component",
                        node_id=comp,
                        properties={
                            "name": comp,
                            "full_name": KNOWN_COMPONENTS[comp]["full_name"],
                            "optional": KNOWN_COMPONENTS[comp]["optional"],
                        },
                    )
                )
                components_added.add(comp)

            graph.relationships.append(
                GraphRelationship(
                    from_label="Requirement",
                    from_id=req.req_id,
                    to_label="Component",
                    to_id=comp,
                    rel_type="MENTIONS",
                )
            )

        # Standards
        for std in extract_standards(req.text):
            if std not in standards_added:
                graph.nodes.append(
                    GraphNode(
                        label="Standard",
                        node_id=std,
                        properties={"name": std, "description": KNOWN_STANDARDS[std]},
                    )
                )
                standards_added.add(std)

            graph.relationships.append(
                GraphRelationship(
                    from_label="Requirement",
                    from_id=req.req_id,
                    to_label="Standard",
                    to_id=std,
                    rel_type="REFERS_TO",
                )
            )

        # Configurations
        for cfg in extract_configurations(req.text):
            if cfg not in configs_added:
                graph.nodes.append(
                    GraphNode(
                        label="Configuration",
                        node_id=cfg,
                        properties={"name": cfg, "description": KNOWN_CONFIGS[cfg]},
                    )
                )
                configs_added.add(cfg)

            graph.relationships.append(
                GraphRelationship(
                    from_label="Requirement",
                    from_id=req.req_id,
                    to_label="Configuration",
                    to_id=cfg,
                    rel_type="APPLIES_TO",
                )
            )

    # ---- Smell nodes from SpecGuard pipeline output ----
    if smell_results:
        smell_counter = 0
        for result in smell_results:
            for hit in result.smell_report.hits:
                smell_counter += 1
                smell_id = f"smell_{smell_counter}"
                graph.nodes.append(
                    GraphNode(
                        label="Smell",
                        node_id=smell_id,
                        properties={
                            "smell_type": hit.smell_type.value,
                            "trigger": hit.trigger,
                            "severity": hit.severity,
                            "position": hit.position,
                            "explanation": hit.explanation,
                        },
                    )
                )
                graph.relationships.append(
                    GraphRelationship(
                        from_label="Requirement",
                        from_id=result.requirement_id,
                        to_label="Smell",
                        to_id=smell_id,
                        rel_type="HAS_SMELL",
                    )
                )

    # ---- Heuristic structural relations: REFINES via parent_section ----
    # If a requirement is within a parent section that itself has a "general"
    # statement requirement, we can hint a REFINES relation. For CVA6 this is
    # a soft heuristic — placeholder for richer LLM-assisted detection later.

    # Group requirements by parent_section
    by_section: dict = {}
    for req in requirements:
        by_section.setdefault(req.parent_section, []).append(req)

    return graph


# ============================================================================
# Cypher serialization
# ============================================================================


def _escape_cypher_string(value: str) -> str:
    """Escape special characters for safe inclusion in Cypher string literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", "")


def _format_property_value(value) -> str:
    """Format a Python value for Cypher property syntax."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    return f"'{_escape_cypher_string(str(value))}'"


def _format_properties(props: dict) -> str:
    """Format a properties dict as Cypher map literal."""
    if not props:
        return ""
    parts = [f"{k}: {_format_property_value(v)}" for k, v in props.items()]
    return "{" + ", ".join(parts) + "}"


def graph_to_cypher(graph: RequirementGraph) -> str:
    """Generate a complete Cypher import script.

    Output is a single .cypher file that can be executed in Neo4j Browser
    or via cypher-shell. Uses MERGE for idempotency — running the script
    twice produces the same graph.
    """
    lines: list[str] = []

    lines.append("// =========================================================")
    lines.append("// SpecGuard Knowledge Graph — CVA6 Requirements")
    lines.append("// =========================================================")
    lines.append("// ")
    lines.append("// Auto-generated from CVA6 Requirements Specification v1.0.1")
    lines.append("// Source: https://docs.openhwgroup.org/projects/cva6-user-manual/")
    lines.append("// ")
    lines.append("// To execute:")
    lines.append("//   1. Open Neo4j Browser (http://localhost:7474)")
    lines.append("//   2. Paste this script and run with the play button")
    lines.append("//   OR")
    lines.append("//   $ cypher-shell -u neo4j -p <password> < specguard_graph.cypher")
    lines.append("// =========================================================")
    lines.append("")
    lines.append("// Clean any previous SpecGuard data (comment out to keep)")
    lines.append("MATCH (n) WHERE n:Requirement OR n:Category OR n:Component OR")
    lines.append("              n:Standard OR n:Configuration OR n:Smell")
    lines.append("DETACH DELETE n;")
    lines.append("")

    # Indexes for performance
    lines.append("// ---- Indexes ----")
    lines.append("CREATE INDEX requirement_id IF NOT EXISTS FOR (r:Requirement) ON (r.req_id);")
    lines.append("CREATE INDEX category_name IF NOT EXISTS FOR (c:Category) ON (c.name);")
    lines.append("CREATE INDEX component_name IF NOT EXISTS FOR (c:Component) ON (c.name);")
    lines.append("CREATE INDEX standard_name IF NOT EXISTS FOR (s:Standard) ON (s.name);")
    lines.append("")

    # Group nodes by label for cleaner output
    nodes_by_label: dict = {}
    for node in graph.nodes:
        nodes_by_label.setdefault(node.label, []).append(node)

    for label, nodes in nodes_by_label.items():
        lines.append(f"// ---- {label} nodes ({len(nodes)}) ----")
        for node in nodes:
            props_str = _format_properties(node.properties)
            lines.append(f"MERGE (n:{label} {{node_id: '{_escape_cypher_string(node.node_id)}'}}) "
                         f"SET n += {props_str};")
        lines.append("")

    # Group relationships by type
    rels_by_type: dict = {}
    for rel in graph.relationships:
        rels_by_type.setdefault(rel.rel_type, []).append(rel)

    for rel_type, rels in rels_by_type.items():
        lines.append(f"// ---- {rel_type} relationships ({len(rels)}) ----")
        for rel in rels:
            lines.append(
                f"MATCH (a:{rel.from_label} {{node_id: '{_escape_cypher_string(rel.from_id)}'}}), "
                f"(b:{rel.to_label} {{node_id: '{_escape_cypher_string(rel.to_id)}'}}) "
                f"MERGE (a)-[:{rel_type}]->(b);"
            )
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("=" * 70)
    print("SPECGUARD GRAPH BUILDER")
    print("=" * 70)
    print()

    # Load data
    requirements = get_all_requirements()
    print(f"Loaded {len(requirements)} requirements.")

    # Run smell detection to enrich graph
    print("Running smell detection pipeline...")
    smell_results = assess_dataset(requirements)

    # Build graph
    print("Building knowledge graph...")
    graph = build_graph(requirements, smell_results)

    # Stats
    stats = graph.stats()
    print()
    print("Graph statistics:")
    print(f"  Total nodes:         {stats['total_nodes']}")
    print(f"  Total relationships: {stats['total_relationships']}")
    print()
    print("Nodes by label:")
    for label, count in stats["nodes_by_label"].items():
        print(f"  {label:18s} {count:4d}")
    print()
    print("Relationships by type:")
    for rtype, count in stats["relationships_by_type"].items():
        print(f"  {rtype:18s} {count:4d}")

    # Generate Cypher
    cypher = graph_to_cypher(graph)
    output_path = Path(__file__).parent.parent.parent.parent / "results" / "specguard_graph.cypher"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(cypher)
    print()
    print(f"Cypher script written to: {output_path}")
    print(f"Lines: {len(cypher.splitlines())}")


if __name__ == "__main__":
    main()
