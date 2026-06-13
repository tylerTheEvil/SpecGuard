"""Integration tests for the merge-based Neo4j write/read helpers.

Marked ``@pytest.mark.neo4j`` — skip cleanly when the driver is missing or the
database is unreachable, so plain ``pytest`` keeps passing.

Order-independence contract: these tests do NOT assume what is currently loaded
in the DB. The module fixture clears the database, runs the merge assertions on
its own freshly-built state, and **reloads via the existing loader**
(``scripts.load_neo4j.load_all``) on teardown so the other neo4j test modules —
each of which reloads its own graph in its own module fixture anyway — are
unaffected regardless of execution order.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.neo4j

_PROBE_TIMEOUT = 3.0


def _neo4j_available() -> bool:
    try:
        from neo4j import GraphDatabase

        from specguard.compliance.neo4j_runner import Neo4jConfig
    except ImportError:
        return False
    config = Neo4jConfig.from_env()
    try:
        driver = GraphDatabase.driver(
            config.uri, auth=(config.user, config.password), connection_timeout=_PROBE_TIMEOUT
        )
        try:
            driver.verify_connectivity()
            return True
        finally:
            driver.close()
    except Exception:
        return False


def _count_by_dataset(tag: str) -> int:
    from specguard.graph.neo4j_io import run_readonly_cypher

    rows = run_readonly_cypher(
        "MATCH (n) WHERE n.dataset = $tag RETURN count(n) AS c", params={"tag": tag}
    )
    return rows[0]["c"]


@pytest.fixture(scope="module")
def clean_db():
    """Clear the DB for this module, reload the canonical graph on teardown."""
    if not _neo4j_available():
        pytest.skip("Neo4j not reachable — skipping neo4j_io tests")

    from specguard.compliance.neo4j_runner import Neo4jGraphRunner

    runner = Neo4jGraphRunner()
    runner.connect()
    runner("MATCH (n) DETACH DELETE n", {})
    runner.close()
    yield
    # Restore canonical state so sibling neo4j modules see a populated DB
    # regardless of test ordering.
    from scripts.load_neo4j import load_all

    load_all()


def _build_small_graph(req_ids, text="The unit shall behave correctly.", category="Test"):
    """Build a tiny RequirementGraph from a few synthetic requirements.

    ``text``/``category`` are parameterised so callers can keep two datasets'
    shared entity nodes (Components/Standards/Categories) disjoint — the
    ``dataset`` property is single-valued, so a node MENTIONed by two datasets
    would be re-stamped by the second writer (documented behaviour). Realistic
    coexistence (different engineers' requirement sets) is the case under test.
    """
    from specguard.core import assess_dataset
    from specguard.data.cva6_requirements import Requirement
    from specguard.graph.builder import build_graph

    reqs = [Requirement(req_id=rid, text=text, category=category) for rid in req_ids]
    return build_graph(reqs, assess_dataset(reqs))


def _count_requirements_by_dataset(tag: str) -> int:
    from specguard.graph.neo4j_io import run_readonly_cypher

    rows = run_readonly_cypher(
        "MATCH (n:Requirement) WHERE n.dataset = $tag RETURN count(n) AS c",
        params={"tag": tag},
    )
    return rows[0]["c"]


# ---------------------------------------------------------------------------
# merge_graph
# ---------------------------------------------------------------------------


def test_two_datasets_coexist(clean_db):
    from specguard.graph.neo4j_io import merge_graph

    # Disjoint entity vocabularies so shared nodes don't flip the dataset tag.
    g_a = _build_small_graph(["A-1", "A-2"], text="The MMU shall translate addresses.")
    g_b = _build_small_graph(["B-1"], text="The store buffer shall drain promptly.")

    merge_graph(g_a, dataset_tag="alpha")
    assert _count_requirements_by_dataset("alpha") == 2

    # Merging a second dataset must NOT remove the first's requirements.
    merge_graph(g_b, dataset_tag="beta")
    assert _count_requirements_by_dataset("alpha") == 2
    assert _count_requirements_by_dataset("beta") == 1
    # Total node count strictly grew — nothing was deleted.
    assert _count_by_dataset("alpha") > 0
    assert _count_by_dataset("beta") > 0


def test_merge_idempotent(clean_db):
    from specguard.graph.neo4j_io import merge_graph

    g = _build_small_graph(["IDEM-1", "IDEM-2"])
    merge_graph(g, dataset_tag="idem")
    first = _count_by_dataset("idem")
    # Re-merging the same tag must not duplicate nodes.
    merge_graph(g, dataset_tag="idem")
    assert _count_by_dataset("idem") == first


def test_merge_graph_rejects_empty_tag(clean_db):
    from specguard.graph.neo4j_io import merge_graph

    g = _build_small_graph(["X-1"])
    with pytest.raises(ValueError):
        merge_graph(g, dataset_tag="   ")


# ---------------------------------------------------------------------------
# merge_accepted_edges
# ---------------------------------------------------------------------------


def test_merge_accepted_edges_lands_with_provenance(clean_db):
    from specguard.extraction.extractor import EdgeProposal, EdgeType
    from specguard.extraction.review import ReviewQueue, export_accepted_edges
    from specguard.graph.neo4j_io import merge_accepted_edges, run_readonly_cypher

    queue = ReviewQueue()
    queue.add(
        EdgeProposal(
            edge_type=EdgeType.MENTIONS,
            source_id="PROV-1",
            target_entity="L1WTD",
            confidence=0.91,
            evidence_span="L1WTD cache",
        )
    )
    queue.accept(0)
    edges = export_accepted_edges(queue)
    assert len(edges) == 1

    result = merge_accepted_edges(edges)
    assert result["edges_merged"] == 1

    rows = run_readonly_cypher(
        "MATCH (a:Requirement {node_id: 'PROV-1'})-[r:MENTIONS]->(b) "
        "RETURN r.human_confirmed AS hc, r.source AS src, b.node_id AS tgt"
    )
    assert rows
    assert rows[0]["hc"] is True
    assert rows[0]["src"] == "llm_extraction"
    assert rows[0]["tgt"] == "L1WTD"


# ---------------------------------------------------------------------------
# run_readonly_cypher guard
# ---------------------------------------------------------------------------


def test_readonly_rejects_write_query(clean_db):
    from specguard.graph.neo4j_io import run_readonly_cypher

    with pytest.raises(ValueError):
        run_readonly_cypher("MATCH (n) DETACH DELETE n")
    with pytest.raises(ValueError):
        run_readonly_cypher("CREATE (n:Foo) RETURN n")
    with pytest.raises(ValueError):
        run_readonly_cypher("MATCH (n) SET n.x = 1")


def test_readonly_allows_read_query(clean_db):
    from specguard.graph.neo4j_io import run_readonly_cypher

    rows = run_readonly_cypher("RETURN 1 AS one")
    assert rows == [{"one": 1}]
