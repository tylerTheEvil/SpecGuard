"""Neo4j-backed graph runner for the compliance constraint engine.

This module provides a concrete implementation of the ``GraphRunner``
callable interface declared in :mod:`specguard.compliance.constraint_engine`
that executes a constraint's ``cypher_query`` against a real Neo4j database
(via the official ``neo4j`` Python driver) and returns the result rows as a
list of plain ``dict`` objects.

Quarantine / optional-dependency contract
------------------------------------------
The deterministic SpecGuard core is intentionally stdlib-only for DO-330
qualifiability. The ``neo4j`` driver is therefore an *optional* dependency
declared in the ``[graph]`` extra. To keep ``import specguard`` working with
no extras installed, the ``neo4j`` import is **lazy and guarded** — it happens
inside the runner constructor, not at module import time. This mirrors the
quarantine pattern used by :mod:`specguard.linguistic`.

Honest scope note
------------------
This runner only *executes* the codified Cypher patterns against a graph; it
demonstrates that the 15 representative objectives are syntactically and
semantically valid Cypher and produce rows of the expected shape. The
compliance metadata loaded by ``scripts/load_neo4j.py`` is **mock** (synthetic
DAL assignments, traceability edges, interface/hazard nodes). This proves
*executability*, not certification fitness — the patterns would require
Designated Engineering Representative (DER) review before any real use.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from neo4j import Driver


# Default connection configuration. All values overridable via env vars so the
# runner can target a different DBMS without code changes.
DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "neo4j"  # placeholder only; set SPECGUARD_NEO4J_PASSWORD for your DBMS
DEFAULT_DATABASE = "neo4j"


@dataclass
class Neo4jConfig:
    """Connection configuration for the Neo4j runner.

    Defaults target the local project DBMS. Every field can be overridden via
    an environment variable so credentials are not hard-coded in callers:

    - ``SPECGUARD_NEO4J_URI``
    - ``SPECGUARD_NEO4J_USER``
    - ``SPECGUARD_NEO4J_PASSWORD``
    - ``SPECGUARD_NEO4J_DATABASE``
    """

    uri: str = DEFAULT_URI
    user: str = DEFAULT_USER
    password: str = DEFAULT_PASSWORD
    database: str = DEFAULT_DATABASE

    @classmethod
    def from_env(cls) -> Neo4jConfig:
        """Build a config, overriding defaults from environment variables."""
        return cls(
            uri=os.environ.get("SPECGUARD_NEO4J_URI", DEFAULT_URI),
            user=os.environ.get("SPECGUARD_NEO4J_USER", DEFAULT_USER),
            password=os.environ.get("SPECGUARD_NEO4J_PASSWORD", DEFAULT_PASSWORD),
            database=os.environ.get("SPECGUARD_NEO4J_DATABASE", DEFAULT_DATABASE),
        )


class Neo4jGraphRunner:
    """Callable graph runner backed by a live Neo4j database.

    Instances are callables matching the ``GraphRunner`` type alias
    ``(cypher_query: str, params: dict) -> list[dict]`` and can be passed
    directly to :func:`specguard.compliance.run_compliance_check`.

    The driver is created lazily on first use (or eagerly via :meth:`connect`)
    and should be released with :meth:`close` or by using the runner as a
    context manager::

        with Neo4jGraphRunner() as run:
            report = run_compliance_check(run, DO_178C_OBJECTIVES)
    """

    def __init__(self, config: Neo4jConfig | None = None) -> None:
        self.config = config or Neo4jConfig.from_env()
        self._driver: Driver | None = None

    def connect(self) -> None:
        """Create the underlying driver. Imports ``neo4j`` lazily.

        Raises:
            ImportError: if the ``neo4j`` driver is not installed (the
                ``[graph]`` extra is missing).
        """
        if self._driver is not None:
            return
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:  # pragma: no cover - exercised only w/o extra
            raise ImportError(
                "The 'neo4j' driver is required for Neo4jGraphRunner. "
                "Install the graph extra: pip install -e '.[graph]'"
            ) from exc
        self._driver = GraphDatabase.driver(
            self.config.uri, auth=(self.config.user, self.config.password)
        )

    def verify_connectivity(self) -> None:
        """Open the driver and ping the server. Raises on failure."""
        self.connect()
        assert self._driver is not None
        self._driver.verify_connectivity()

    def close(self) -> None:
        """Release the underlying driver."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self) -> Neo4jGraphRunner:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __call__(self, cypher_query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute ``cypher_query`` and return result rows as dicts.

        Args:
            cypher_query: a Cypher statement (typically a constraint's
                ``cypher_query``) that returns one row per violation.
            params: query parameters bound by name.

        Returns:
            One dict per result record, keys being the RETURN column aliases.
        """
        self.connect()
        assert self._driver is not None
        with self._driver.session(database=self.config.database) as session:
            result = session.run(cypher_query, params or {})
            return [record.data() for record in result]


def make_neo4j_runner(config: Neo4jConfig | None = None) -> Neo4jGraphRunner:
    """Convenience factory mirroring ``make_graph_runner`` in the demo."""
    return Neo4jGraphRunner(config)
