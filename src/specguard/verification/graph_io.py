"""Immutable scoped bundle snapshots and typed graph projections.

Memory and Neo4j feed the same analyzer from the same content-addressed JSON.
Arbitrary existing Neo4j graphs have no reviewed bundle scope and are not
silently converted. Neo4j writes are explicit and use a single transaction.
"""

from __future__ import annotations

import json
from typing import Any

from .model import COLLECTIONS, LABELS, Bundle, digest

LINKS = {
    "assumption_ids": "DEPENDS_ON_ASSUMPTION",
    "scenario_ids": "COVERS_SCENARIO",
    "evidence": "SUPPORTED_BY",
    "requirement_ids": "FORMALIZES",
    "mitigates": "MITIGATES",
    "parent_ids": "DERIVES_FROM",
    "verification_ids": "VERIFIES",
}


def bundle_graph(bundle: Bundle) -> dict[str, Any]:
    """Project entities and links; missing references remain visible in the bundle."""
    nodes = [
        {
            "id": row["id"],
            "label": LABELS[kind],
            "content_hash": digest(row),
            "payload": json.dumps(row, sort_keys=True),
        }
        for kind in COLLECTIONS
        for row in bundle.rows(kind)
    ]
    index = {n["id"]: n for n in nodes}
    edges = []
    missing = []
    for kind in COLLECTIONS:
        for row in bundle.rows(kind):
            for key, relation in LINKS.items():
                for target in row.get(key, []):
                    if target not in index:
                        missing.append({"source": row["id"], "target": target, "field": key})
                        continue
                    rel = relation
                    if key == "verification_ids":
                        edges.append({"source": target, "target": row["id"], "type": rel})
                        continue
                    if kind == "scenarios" and key == "requirement_ids":
                        edges.append(
                            {"source": target, "target": row["id"], "type": "COVERS_SCENARIO"}
                        )
                        continue
                    if key == "mitigates" and (
                        kind != "requirements" or index[target]["label"] != "SafetyHazard"
                    ):
                        raise ValueError(
                            "Bundle MITIGATES endpoints must be Requirement -> SafetyHazard"
                        )
                    edges.append({"source": row["id"], "target": target, "type": rel})
            if kind == "evidence":
                for target in row.get("dependencies", {}):
                    if target in index:
                        edges.append({"source": row["id"], "target": target, "type": "DEPENDS_ON"})
    return {"nodes": nodes, "edges": edges, "unresolved_links": missing}


def import_bundle(bundle: Bundle, config=None) -> dict[str, Any]:
    """Atomically add an immutable revision; never clear or overwrite another revision."""
    from specguard.compliance.neo4j_runner import Neo4jGraphRunner

    projection = bundle_graph(bundle)
    revision = digest(bundle.data)
    params = {
        "id": bundle.data["id"],
        "revision": revision,
        "payload": json.dumps(bundle.data, sort_keys=True),
        "nodes": projection["nodes"],
        "edges": projection["edges"],
    }
    # Labels/types come exclusively from fixed mappings, never user Cypher.
    with Neo4jGraphRunner(config) as runner:
        assert runner._driver is not None
        with runner._driver.session(database=runner.config.database) as session:

            def write(tx):
                tx.run(
                    "MERGE (s:SpecGuardSnapshot {bundle_id: $id, revision: $revision}) "
                    "SET s.payload = $payload",
                    params,
                ).consume()
                for node in projection["nodes"]:
                    tx.run(
                        f"MERGE (n:SpecGuardArtifact:{node['label']} "
                        "{bundle_id: $id, revision: $revision, artifact_id: $artifact}) "
                        "SET n.payload = $payload, n.content_hash = $hash",
                        id=params["id"],
                        revision=revision,
                        artifact=node["id"],
                        payload=node["payload"],
                        hash=node["content_hash"],
                    ).consume()
                for edge in projection["edges"]:
                    tx.run(
                        "MATCH (a:SpecGuardArtifact {bundle_id: $id, revision: $revision, "
                        "artifact_id: $source}), (b:SpecGuardArtifact {bundle_id: $id, "
                        "revision: $revision, artifact_id: $target}) "
                        f"MERGE (a)-[:{edge['type']}]->(b)",
                        id=params["id"],
                        revision=revision,
                        source=edge["source"],
                        target=edge["target"],
                    ).consume()

            session.execute_write(write)
    return {
        "bundle_id": bundle.data["id"],
        "revision": revision,
        "nodes": len(projection["nodes"]),
        "edges": len(projection["edges"]),
        "unresolved_links": projection["unresolved_links"],
    }


def read_bundle(bundle_id: str, revision: str, config=None, *, runner=None) -> Bundle:
    """Read one exact immutable revision, validating its content hash before analysis."""
    from specguard.compliance.neo4j_runner import Neo4jGraphRunner

    owned = runner is None
    run = runner or Neo4jGraphRunner(config)
    try:
        rows = run(
            "MATCH (s:SpecGuardSnapshot {bundle_id: $id, revision: $revision}) "
            "RETURN s.payload AS payload",
            {"id": bundle_id, "revision": revision},
        )
        if len(rows) != 1:
            raise ValueError("Expected exactly one reviewed bundle snapshot; import it explicitly")
        bundle = Bundle.from_dict(json.loads(rows[0]["payload"]))
        if bundle.data["id"] != bundle_id or digest(bundle.data) != revision:
            raise ValueError("Stored snapshot identity/content hash mismatch")
        return bundle
    finally:
        if owned:
            run.close()
