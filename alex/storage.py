"""Persistence: Postgres (analysis records) + Neo4j (ticker/sector/correlation graph).

Best-effort by default (settings.storage_best_effort): if a DB is unreachable the
call logs a warning and returns without raising, so the agent keeps working with
DBs down. Set STORAGE_BEST_EFFORT=false to make storage failures hard errors.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .config import settings

log = logging.getLogger("alex.storage")

# Once a backend fails to connect, latch it "down" so we don't eat a multi-second
# timeout on every subsequent tool call this process. Cleared only on restart.
# ponytail: process-local latch; fine for CLI/single-worker, revisit for HA.
_DOWN: set[str] = set()


def _guard(e: Exception, what: str, backend: str) -> None:
    _DOWN.add(backend)  # latch: skip this backend for the rest of the process
    if settings.storage_best_effort:
        log.warning("storage skipped (%s, %s down): %s", what, backend, e)
    else:
        raise


# ------------------------------------------------------------- Postgres ----
_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis (
    id         BIGSERIAL PRIMARY KEY,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind       TEXT NOT NULL,          -- risk | correlation | agent_answer ...
    tickers    TEXT[] NOT NULL,
    payload    JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS analysis_kind_ts ON analysis (kind, ts DESC);
"""


def _pg():
    import psycopg
    return psycopg.connect(settings.postgres_dsn, connect_timeout=3)


def init_postgres() -> None:
    if "postgres" in _DOWN:
        return
    try:
        with _pg() as conn:
            conn.execute(_SCHEMA)
    except Exception as e:  # noqa: BLE001
        _guard(e, "init_postgres", "postgres")


def save_analysis(kind: str, tickers: list[str], payload: dict[str, Any]) -> None:
    if "postgres" in _DOWN:
        return
    try:
        with _pg() as conn:
            conn.execute(
                "INSERT INTO analysis (kind, tickers, payload) VALUES (%s, %s, %s)",
                (kind, tickers, json.dumps(payload, default=str)),
            )
    except Exception as e:  # noqa: BLE001
        _guard(e, "save_analysis", "postgres")


# ---------------------------------------------------------------- Neo4j ----
def _neo():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=3,
    )


def upsert_correlations(period: str, pairs: list[tuple[str, str, float]]) -> None:
    """Store correlation edges: (:Ticker)-[:CORRELATED {value, period}]->(:Ticker)."""
    if "neo4j" in _DOWN:
        return
    try:
        drv = _neo()
        with drv.session() as s:
            for a, b, v in pairs:
                s.run(
                    """
                    MERGE (x:Ticker {symbol:$a})
                    MERGE (y:Ticker {symbol:$b})
                    MERGE (x)-[r:CORRELATED {period:$p}]->(y)
                    SET r.value=$v, r.updated=timestamp()
                    """,
                    a=a, b=b, v=v, p=period,
                )
        drv.close()
    except Exception as e:  # noqa: BLE001
        _guard(e, "upsert_correlations", "neo4j")


def tag_sector(ticker: str, sector: str | None) -> None:
    if not sector or "neo4j" in _DOWN:
        return
    try:
        drv = _neo()
        with drv.session() as s:
            s.run(
                """
                MERGE (t:Ticker {symbol:$t})
                MERGE (sec:Sector {name:$s})
                MERGE (t)-[:IN_SECTOR]->(sec)
                """,
                t=ticker, s=sector,
            )
        drv.close()
    except Exception as e:  # noqa: BLE001
        _guard(e, "tag_sector", "neo4j")
