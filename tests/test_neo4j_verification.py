"""Opt-in disposable Neo4j snapshot parity; never uses an undesignated user database."""

import copy

import pytest

from specguard.compliance.neo4j_runner import Neo4jConfig, require_isolated_test_database
from specguard.verification.analyzer import analyze_bundle
from specguard.verification.graph_io import import_bundle, read_bundle
from specguard.verification.model import Bundle
from tests.test_verification import contracts

pytestmark = pytest.mark.neo4j


def test_live_snapshot_parity_and_revision_isolation():
    config = Neo4jConfig.from_env()
    try:
        require_isolated_test_database(config)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    pytest.importorskip("neo4j")
    old = Bundle.from_dict(contracts())
    new_data = copy.deepcopy(old.data)
    new_data["contracts"][1]["guarantees"][0]["eq"] = 0
    new = Bundle.from_dict(new_data)
    first = import_bundle(old, config)
    second = import_bundle(new, config)
    for source, saved in ((old, first), (new, second)):
        loaded = read_bundle(source.data["id"], saved["revision"], config)
        assert analyze_bundle(source) == analyze_bundle(loaded)
    assert first["revision"] != second["revision"]
