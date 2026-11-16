"""Financial knowledge graph: entities and typed relations the model can query.

Schema (property graph; every node is an :Entity with an extra label, every edge typed):

  (:Company {id: ticker, name, country})      (:Sector {id, name})   (:Industry {id, name})
  (:Country {id, name})                        (:MacroSeries {id: FRED id, name})

  (Company)-[:IN_INDUSTRY]->(Industry)-[:PART_OF]->(Sector)
  (Company)-[:DOMICILED_IN]->(Country)
  (Company)-[:SUPPLIES {product}]->(Company)
  (Company)-[:COMPETES_WITH]->(Company)                      (symmetric, stored once)
  (Company)-[:CORRELATED {value, period}]->(Company)         (symmetric, stored once)
  (Company)-[:SENSITIVE_TO {direction, channel}]->(MacroSeries)

The schema is open: `add_node` / `add_edge` accept any label / relation type that is a
valid identifier, and the two model-facing tools are generic (neighbours, paths), so new
relation types become queryable without touching the tools or the prompts.

Two interchangeable backends answer the same queries:

  MemoryGraph   in-process, deterministic; used in frozen mode so every model sees the same graph
  Neo4jGraph    a Neo4j 5 database (NEO4J_URI); used in live mode with KG_BACKEND=neo4j,
                loaded with `alex-kg load` and extended from live data with `alex-kg sync`

No free-form Cypher is exposed to the model: queries are fixed and parameterised, and
labels / relation types are validated, so a prompt-injected tool call cannot write to
or dump the database.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import deque
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Protocol

from .config import settings

IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")
ENTITY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,63}$")
MAX_HOPS = 6
ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ seed data ----
# Synthetic but realistic, consistent with alex/fixtures.py. (id, label, name, extra props)
_NODES: list[tuple[str, str, str, dict]] = [
    ("AAPL", "Company", "Apple Inc.", {"country": "United States"}),
    ("MSFT", "Company", "Microsoft Corporation", {"country": "United States"}),
    ("NVDA", "Company", "NVIDIA Corporation", {"country": "United States"}),
    ("TSLA", "Company", "Tesla, Inc.", {"country": "United States"}),
    ("JPM", "Company", "JPMorgan Chase & Co.", {"country": "United States"}),
    ("BAC", "Company", "Bank of America Corporation", {"country": "United States"}),
    ("GS", "Company", "The Goldman Sachs Group, Inc.", {"country": "United States"}),
    ("AMD", "Company", "Advanced Micro Devices, Inc.", {"country": "United States"}),
    ("INTC", "Company", "Intel Corporation", {"country": "United States"}),
    ("TSM", "Company", "Taiwan Semiconductor Manufacturing Company", {"country": "Taiwan"}),
    ("ASML", "Company", "ASML Holding N.V.", {"country": "Netherlands"}),
    ("CTSH", "Company", "Cognizant Technology Solutions", {"country": "United States"}),
    ("INFY", "Company", "Infosys Limited", {"country": "India"}),
    ("sector:technology", "Sector", "Technology", {}),
    ("sector:financial-services", "Sector", "Financial Services", {}),
    ("sector:consumer-cyclical", "Sector", "Consumer Cyclical", {}),
    ("industry:semiconductors", "Industry", "Semiconductors", {}),
    ("industry:semiconductor-equipment", "Industry", "Semiconductor Equipment & Materials", {}),
    ("industry:consumer-electronics", "Industry", "Consumer Electronics", {}),
    ("industry:software-infrastructure", "Industry", "Software - Infrastructure", {}),
    ("industry:it-services", "Industry", "Information Technology Services", {}),
    ("industry:auto-manufacturers", "Industry", "Auto Manufacturers", {}),
    ("industry:banks-diversified", "Industry", "Banks - Diversified", {}),
    ("industry:capital-markets", "Industry", "Capital Markets", {}),
    ("country:us", "Country", "United States", {}),
    ("country:tw", "Country", "Taiwan", {}),
    ("country:nl", "Country", "Netherlands", {}),
    ("country:in", "Country", "India", {}),
    ("DGS10", "MacroSeries", "10-Year Treasury Constant Maturity Yield", {}),
    ("CPIAUCSL", "MacroSeries", "Consumer Price Index for All Urban Consumers", {}),
    ("UNRATE", "MacroSeries", "Unemployment Rate", {}),
]

_INDUSTRY = {"AAPL": "consumer-electronics", "MSFT": "software-infrastructure", "NVDA": "semiconductors",
             "AMD": "semiconductors", "INTC": "semiconductors", "TSM": "semiconductors",
             "ASML": "semiconductor-equipment", "TSLA": "auto-manufacturers", "JPM": "banks-diversified",
             "BAC": "banks-diversified", "GS": "capital-markets", "CTSH": "it-services", "INFY": "it-services"}
_SECTOR = {"semiconductors": "technology", "semiconductor-equipment": "technology",
           "consumer-electronics": "technology", "software-infrastructure": "technology",
           "it-services": "technology", "auto-manufacturers": "consumer-cyclical",
           "banks-diversified": "financial-services", "capital-markets": "financial-services"}
_COUNTRY = {"United States": "country:us", "Taiwan": "country:tw", "Netherlands": "country:nl",
            "India": "country:in"}

_EDGES: list[tuple[str, str, str, dict]] = [
    *[(t, "IN_INDUSTRY", f"industry:{i}", {}) for t, i in _INDUSTRY.items()],
    *[(f"industry:{i}", "PART_OF", f"sector:{s}", {}) for i, s in _SECTOR.items()],
    *[(n, "DOMICILED_IN", _COUNTRY[p["country"]], {}) for n, lab, _, p in _NODES if lab == "Company"],
    ("ASML", "SUPPLIES", "TSM", {"product": "EUV lithography systems"}),
    ("TSM", "SUPPLIES", "NVDA", {"product": "GPU wafer fabrication"}),
    ("TSM", "SUPPLIES", "AAPL", {"product": "A- and M-series chip fabrication"}),
    ("TSM", "SUPPLIES", "AMD", {"product": "CPU and GPU wafer fabrication"}),
    ("NVDA", "SUPPLIES", "MSFT", {"product": "data-centre GPUs"}),
    ("NVDA", "COMPETES_WITH", "AMD", {}), ("NVDA", "COMPETES_WITH", "INTC", {}),
    ("AMD", "COMPETES_WITH", "INTC", {}), ("JPM", "COMPETES_WITH", "BAC", {}),
    ("JPM", "COMPETES_WITH", "GS", {}), ("CTSH", "COMPETES_WITH", "INFY", {}),
    ("JPM", "SENSITIVE_TO", "DGS10", {"direction": "positive", "channel": "net interest margin"}),
    ("BAC", "SENSITIVE_TO", "DGS10", {"direction": "positive", "channel": "net interest margin"}),
    ("TSLA", "SENSITIVE_TO", "DGS10", {"direction": "negative", "channel": "auto-loan financing costs"}),
    ("AAPL", "SENSITIVE_TO", "CPIAUCSL", {"direction": "negative", "channel": "consumer discretionary spending"}),
]
SYMMETRIC = {"COMPETES_WITH", "CORRELATED"}


def _seed_edges() -> list[tuple[str, str, str, dict]]:
    from .fixtures import _CORR  # the same correlations the correlation tool returns
    corr = [(a, "CORRELATED", b, {"value": v, "period": "1y"})
            for a, b in (sorted(k) for k in _CORR) for v in [_CORR[frozenset((a, b))]]]
    return _EDGES + sorted(corr)


def seed() -> tuple[list[dict], list[dict]]:
    nodes = [{"id": i, "label": lab, "name": n, **p} for i, lab, n, p in _NODES]
    edges = [{"from": a, "type": t, "to": b, **p} for a, t, b, p in _seed_edges()]
    return nodes, edges


def _check_ident(kind: str, v: str) -> str:
    if not IDENT.match(v or ""):
        raise ValueError(f"invalid {kind} {v!r}")
    return v


def _node_view(n: dict) -> dict:
    return {"id": n["id"], "label": n["label"], "name": n.get("name", n["id"])}


class Graph(Protocol):
    def neighbors(self, entity: str, relation: str | None = None, direction: str = "both",
                  limit: int = 25) -> dict[str, Any]: ...
    def path(self, entities: list[str], max_hops: int = 4,
             relations: list[str] | None = None) -> dict[str, Any]: ...
    def stats(self) -> dict[str, Any]: ...


# ------------------------------------------------------------- memory backend ----
class MemoryGraph:
    def __init__(self, nodes: Iterable[dict] | None = None, edges: Iterable[dict] | None = None,
                 persist: Path | None = None) -> None:
        if nodes is None and edges is None:
            nodes, edges = seed()
        self.persist = None            # set after loading, so building the graph does not write
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        for n in nodes or []:
            self.add_node(n["id"], n["label"], **{k: v for k, v in n.items() if k not in ("id", "label")})
        for e in edges or []:
            self.add_edge(e["from"], e["type"], e["to"],
                          **{k: v for k, v in e.items() if k not in ("from", "type", "to")})
        self.persist = persist

    def _save(self) -> None:
        """Write the whole graph (a snapshot; the seed plus every user change) atomically."""
        if not self.persist:
            return
        self.persist.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.persist.with_suffix(".tmp")
        tmp.write_text(json.dumps({"nodes": list(self.nodes.values()), "edges": self.edges}, indent=1),
                       encoding="utf-8")
        tmp.replace(self.persist)

    # --- building
    def add_node(self, id: str, label: str, **props: Any) -> None:
        _check_ident("label", label)
        self.nodes.setdefault(id, {"id": id, "label": label}).update(props, label=label)
        self._save()

    def add_edge(self, a: str, rel: str, b: str, **props: Any) -> None:
        _check_ident("relation", rel)
        for x in (a, b):
            if x not in self.nodes:
                raise KeyError(f"unknown node {x!r}")
        for e in self.edges:   # MERGE semantics: one edge per (a, rel, b)
            if self._same(e, a, rel, b):
                e.update(props)
                self._save()
                return
        self.edges.append({"from": a, "type": rel, "to": b, **props})
        self._save()

    @staticmethod
    def _same(e: dict, a: str, rel: str, b: str) -> bool:
        ends = (e["from"], e["to"])
        return e["type"] == rel and (ends == (a, b) or (rel in SYMMETRIC and ends == (b, a)))

    def has_edge(self, a: str, rel: str, b: str) -> bool:
        return any(self._same(e, a, rel, b) for e in self.edges)

    def remove_edge(self, a: str, rel: str, b: str) -> int:
        before = len(self.edges)
        self.edges = [e for e in self.edges if not self._same(e, a, rel, b)]
        n = before - len(self.edges)
        if n:
            self._save()
        return n

    def remove_node(self, id: str) -> int:
        """Delete an entity and every relation touching it; returns the relations removed."""
        if id not in self.nodes:
            return 0
        before = len(self.edges)
        self.edges = [e for e in self.edges if id not in (e["from"], e["to"])]
        del self.nodes[id]
        self._save()
        return before - len(self.edges)

    # --- querying
    def resolve(self, entity: str) -> dict | None:
        q = (entity or "").strip().lower()
        if not q:
            return None
        for n in self.nodes.values():
            if n["id"].lower() == q or n.get("name", "").lower() == q:
                return n
        hits = [n for n in self.nodes.values()
                if q in n.get("name", "").lower() or n["id"].lower().endswith(":" + q)]
        return hits[0] if len(hits) == 1 else None

    def _unknown(self, entity: str) -> dict:
        q = (entity or "").lower()
        sugg = sorted(n["id"] for n in self.nodes.values()
                      if q and (q[:3] in n["id"].lower() or q[:4] in n.get("name", "").lower()))[:5]
        return {"error": f"unknown entity {entity!r}", **({"did_you_mean": sugg} if sugg else {})}

    def relation_types(self) -> list[str]:
        return sorted({e["type"] for e in self.edges})

    def neighbors(self, entity: str, relation: str | None = None, direction: str = "both",
                  limit: int = 25) -> dict[str, Any]:
        n = self.resolve(entity)
        if n is None:
            return self._unknown(entity)
        rel = relation.upper().strip() if relation else None
        if rel and rel not in self.relation_types():
            return {"error": f"unknown relation {relation!r}", "relations": self.relation_types()}
        direction = (direction or "both").lower()
        if direction not in ("in", "out", "both"):
            return {"error": "direction must be in, out or both"}
        out = []
        for e in self.edges:
            if rel and e["type"] != rel:
                continue
            for end, other, d in (("from", "to", "out"), ("to", "from", "in")):
                if e[end] != n["id"]:
                    continue
                sym = e["type"] in SYMMETRIC
                if direction != "both" and not sym and d != direction:
                    continue
                out.append({"relation": e["type"], "direction": "both" if sym else d,
                            "node": _node_view(self.nodes[e[other]]),
                            "properties": {k: v for k, v in e.items() if k not in ("from", "type", "to")}})
        out.sort(key=lambda r: (r["relation"], r["node"]["id"]))
        limit = max(1, min(int(limit or 25), 100))
        return {"entity": _node_view(n), "count": len(out), "relations": out[:limit],
                **({"truncated": True} if len(out) > limit else {})}

    def _adj(self, rels: set[str] | None = None) -> dict[str, list[tuple[str, dict, str]]]:
        adj: dict[str, list[tuple[str, dict, str]]] = {k: [] for k in self.nodes}
        for e in self.edges:
            if rels and e["type"] not in rels:
                continue
            adj[e["from"]].append((e["to"], e, "out"))
            adj[e["to"]].append((e["from"], e, "in"))
        return adj

    def path(self, entities: list[str], max_hops: int = 4,
             relations: list[str] | None = None) -> dict[str, Any]:
        if isinstance(entities, str):
            entities = [entities]
        if not entities or len(entities) < 2:
            return {"error": "need at least 2 entities"}
        hops = max(1, min(int(max_hops or 4), MAX_HOPS))
        rels, err = _rel_filter(relations, self.relation_types())
        if err:
            return err
        res = [self.resolve(e) for e in entities]
        for e, r in zip(entities, res):
            if r is None:
                return self._unknown(e)
        adj, src = self._adj(rels), res[0]["id"]
        paths = []
        for dst in (r["id"] for r in res[1:]):
            # BFS over the undirected view; neighbours visited in sorted order => deterministic
            prev: dict[str, tuple[str, dict, str] | None] = {src: None}
            q, depth = deque([src]), {src: 0}
            while q and dst not in prev:
                cur = q.popleft()
                if depth[cur] >= hops:
                    continue
                for nxt, e, d in sorted(adj[cur], key=lambda t: (t[0], t[1]["type"])):
                    if nxt not in prev:
                        prev[nxt], depth[nxt] = (cur, e, d), depth[cur] + 1
                        q.append(nxt)
            if dst not in prev:
                paths.append({"from": src, "to": dst, "found": False,
                              "message": f"no connection within {hops} hops"})
                continue
            steps, cur = [], dst
            while prev[cur] is not None:
                p, e, _ = prev[cur]
                steps.append({"from": e["from"], "relation": e["type"], "to": e["to"],
                              **{k: v for k, v in e.items() if k not in ("from", "type", "to")}})
                cur = p
            steps.reverse()
            paths.append({"from": src, "to": dst, "found": True, "hops": len(steps), "steps": steps,
                          "nodes": [_node_view(self.nodes[x]) for x in _walk(src, steps)]})
        return {"paths": paths}

    def stats(self) -> dict[str, Any]:
        labels: dict[str, int] = {}
        for n in self.nodes.values():
            labels[n["label"]] = labels.get(n["label"], 0) + 1
        rels: dict[str, int] = {}
        for e in self.edges:
            rels[e["type"]] = rels.get(e["type"], 0) + 1
        return {"backend": "memory", "nodes": len(self.nodes), "edges": len(self.edges),
                "labels": dict(sorted(labels.items())), "relations": dict(sorted(rels.items()))}


def _rel_filter(relations: Any, known: list[str]) -> tuple[set[str] | None, dict | None]:
    if not relations:
        return None, None
    if isinstance(relations, str):
        relations = [relations]
    rels = {str(r).upper().strip() for r in relations}
    bad = sorted(r for r in rels if r not in known)
    if bad:
        return None, {"error": f"unknown relation(s) {bad}", "relations": known}
    return rels, None


def _walk(src: str, steps: list[dict]) -> list[str]:
    """Node sequence along an undirected path whose steps keep their stored direction."""
    seq = [src]
    for s in steps:
        seq.append(s["to"] if s["from"] == seq[-1] else s["from"])
    return seq


# -------------------------------------------------------------- Neo4j backend ----
class Neo4jGraph:
    """Same queries as MemoryGraph, against Neo4j 5. Parameterised Cypher only."""

    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None,
                 driver: Any = None) -> None:
        if driver is None:
            from neo4j import GraphDatabase  # optional dependency: `uv sync --extra graph`
            driver = GraphDatabase.driver(uri or settings.neo4j_uri,
                                          auth=(user or settings.neo4j_user, password or settings.neo4j_password),
                                          connection_timeout=5)
        self.driver = driver

    def close(self) -> None:
        self.driver.close()

    def _q(self, cypher: str, **params: Any) -> list[dict]:
        records, _, _ = self.driver.execute_query(cypher, params, database_=settings.neo4j_database)
        return [r.data() for r in records]

    # --- building
    def setup(self) -> None:
        self._q("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")

    def load(self, nodes: list[dict], edges: list[dict]) -> dict[str, int]:
        self.setup()
        by_label: dict[str, list[dict]] = {}
        for n in nodes:
            by_label.setdefault(_check_ident("label", n["label"]), []).append(n)
        for label, rows in by_label.items():
            self._q(f"UNWIND $rows AS row MERGE (n:Entity {{id: row.id}}) SET n += row, n:`{label}`", rows=rows)
        by_type: dict[str, list[dict]] = {}
        for e in edges:
            by_type.setdefault(_check_ident("relation", e["type"]), []).append(
                {"a": e["from"], "b": e["to"],
                 "props": {k: v for k, v in e.items() if k not in ("from", "type", "to")}})
        for rel, rows in by_type.items():
            self._q(f"UNWIND $rows AS row MATCH (a:Entity {{id: row.a}}), (b:Entity {{id: row.b}}) "
                    f"MERGE (a)-[r:`{rel}`]->(b) SET r += row.props", rows=rows)
        return {"nodes": len(nodes), "edges": len(edges)}

    def add_node(self, id: str, label: str, **props: Any) -> None:
        self.load([{"id": id, "label": label, **props}], [])

    def add_edge(self, a: str, rel: str, b: str, **props: Any) -> None:
        self.load([], [{"from": a, "type": rel, "to": b, **props}])

    def clear(self) -> None:
        self._q("MATCH (n:Entity) DETACH DELETE n")

    def _pattern(self, rel: str) -> str:
        """Relation pattern with a validated type: directed unless the relation is symmetric."""
        rel = _check_ident("relation", rel)
        return f"-[r:`{rel}`]-" if rel in SYMMETRIC else f"-[r:`{rel}`]->"

    def has_edge(self, a: str, rel: str, b: str) -> bool:
        rows = self._q(f"MATCH (a:Entity {{id: $a}}){self._pattern(rel)}(b:Entity {{id: $b}}) "
                       "RETURN count(r) AS n", a=a, b=b)
        return bool(rows and rows[0]["n"])

    def remove_edge(self, a: str, rel: str, b: str) -> int:
        rows = self._q(f"MATCH (a:Entity {{id: $a}}){self._pattern(rel)}(b:Entity {{id: $b}}) "
                       "DELETE r RETURN count(*) AS n", a=a, b=b)
        return rows[0]["n"] if rows else 0

    def remove_node(self, id: str) -> int:
        rows = self._q("MATCH (n:Entity {id: $id}) OPTIONAL MATCH (n)-[r]-() WITH n, count(r) AS k "
                       "DETACH DELETE n RETURN k", id=id)
        return rows[0]["k"] if rows else 0

    # --- querying
    def resolve(self, entity: str) -> dict | None:
        rows = self._q("MATCH (n:Entity) WHERE toLower(n.id) = toLower($e) OR toLower(n.name) = toLower($e) "
                       "RETURN n {.*} AS n LIMIT 1", e=(entity or "").strip())
        if rows:
            return rows[0]["n"]
        rows = self._q("MATCH (n:Entity) WHERE toLower(n.name) CONTAINS toLower($e) "
                       "OR toLower(n.id) ENDS WITH ':' + toLower($e) RETURN n {.*} AS n LIMIT 2",
                       e=(entity or "").strip())
        return rows[0]["n"] if len(rows) == 1 else None

    def relation_types(self) -> list[str]:
        return sorted(r["t"] for r in self._q("MATCH ()-[r]->() RETURN DISTINCT type(r) AS t"))

    def neighbors(self, entity: str, relation: str | None = None, direction: str = "both",
                  limit: int = 25) -> dict[str, Any]:
        n = self.resolve(entity)
        if n is None:
            return {"error": f"unknown entity {entity!r}"}
        rel = relation.upper().strip() if relation else None
        if rel and rel not in self.relation_types():
            return {"error": f"unknown relation {relation!r}", "relations": self.relation_types()}
        direction = (direction or "both").lower()
        if direction not in ("in", "out", "both"):
            return {"error": "direction must be in, out or both"}
        rows = self._q(
            "MATCH (n:Entity {id: $id})-[r]-(m:Entity) WHERE $rel IS NULL OR type(r) = $rel "
            "RETURN type(r) AS relation, startNode(r) = n AS outgoing, properties(r) AS properties, "
            "m.id AS id, m.label AS label, coalesce(m.name, m.id) AS name", id=n["id"], rel=rel)
        out = []
        for r in rows:
            sym = r["relation"] in SYMMETRIC
            d = "both" if sym else ("out" if r["outgoing"] else "in")
            if direction != "both" and not sym and d != direction:
                continue
            out.append({"relation": r["relation"], "direction": d,
                        "node": {"id": r["id"], "label": r["label"], "name": r["name"]},
                        "properties": r["properties"]})
        out.sort(key=lambda r: (r["relation"], r["node"]["id"]))
        limit = max(1, min(int(limit or 25), 100))
        return {"entity": _node_view(n), "count": len(out), "relations": out[:limit],
                **({"truncated": True} if len(out) > limit else {})}

    def path(self, entities: list[str], max_hops: int = 4,
             relations: list[str] | None = None) -> dict[str, Any]:
        if isinstance(entities, str):
            entities = [entities]
        if not entities or len(entities) < 2:
            return {"error": "need at least 2 entities"}
        hops = max(1, min(int(max_hops or 4), MAX_HOPS))   # int, validated: safe to inline
        rels, err = _rel_filter(relations, self.relation_types())
        if err:
            return err
        # relation types are checked against the types present in the graph: safe to inline
        pattern = ":" + "|".join(f"`{r}`" for r in sorted(rels)) if rels else ""
        res = [self.resolve(e) for e in entities]
        for e, r in zip(entities, res):
            if r is None:
                return {"error": f"unknown entity {e!r}"}
        src, paths = res[0]["id"], []
        for dst in (r["id"] for r in res[1:]):
            rows = self._q(
                f"MATCH (a:Entity {{id: $a}}), (b:Entity {{id: $b}}), p = shortestPath((a)-[{pattern}*..{hops}]-(b)) "
                "RETURN [r IN relationships(p) | r {from: startNode(r).id, relation: type(r), "
                "to: endNode(r).id, .*}] AS steps, "
                "[x IN nodes(p) | {id: x.id, label: x.label, name: coalesce(x.name, x.id)}] AS nodes",
                a=src, b=dst)
            if not rows:
                paths.append({"from": src, "to": dst, "found": False,
                              "message": f"no connection within {hops} hops"})
            else:
                steps = rows[0]["steps"]
                paths.append({"from": src, "to": dst, "found": True, "hops": len(steps),
                              "steps": steps, "nodes": rows[0]["nodes"]})
        return {"paths": paths}

    def stats(self) -> dict[str, Any]:
        labels = {r["l"]: r["c"] for r in self._q("MATCH (n:Entity) RETURN n.label AS l, count(*) AS c")}
        rels = {r["t"]: r["c"] for r in self._q("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c")}
        return {"backend": "neo4j", "nodes": sum(labels.values()), "edges": sum(rels.values()),
                "labels": dict(sorted(labels.items())), "relations": dict(sorted(rels.items()))}


# ------------------------------------------------------------- live enrichment ----
def sync_live(g: Any, tickers: list[str], period: str = "1y") -> dict[str, Any]:
    """Add live sector / industry / country and correlation edges for tickers (live mode)."""
    from . import analysis, sources
    added = {"companies": 0, "correlations": 0, "errors": []}
    for t in tickers:
        f = sources.fundamentals(t)
        if "error" in f:
            added["errors"].append(f"{t}: {f['error']}")
            continue
        g.add_node(t, "Company", name=f.get("longName") or t, country=f.get("country") or "")
        for kind, val in (("Industry", f.get("industry")), ("Sector", f.get("sector"))):
            if val:
                g.add_node(f"{kind.lower()}:{_slug(val)}", kind, name=val)
        if f.get("industry"):
            g.add_edge(t, "IN_INDUSTRY", f"industry:{_slug(f['industry'])}")
            if f.get("sector"):
                g.add_edge(f"industry:{_slug(f['industry'])}", "PART_OF", f"sector:{_slug(f['sector'])}")
        if f.get("country"):
            cid = _COUNTRY.get(f["country"], f"country:{_slug(f['country'])}")   # reuse seeded ids
            g.add_node(cid, "Country", name=f["country"])
            g.add_edge(t, "DOMICILED_IN", cid)
        added["companies"] += 1
    if len(tickers) >= 2:
        c = analysis.correlation(tickers, period=period)
        for a, row in (c.get("matrix") or {}).items():
            for b, v in row.items():
                if a < b and v == v:   # skip NaN (a ticker without price history)
                    g.add_edge(a, "CORRELATED", b, value=round(float(v), 4), period=period)
                    added["correlations"] += 1
    return added


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


_MEMORY: MemoryGraph | None = None


def memory_graph() -> MemoryGraph:
    """Read-only reference copy of the seed graph (entity resolution in scoring, figures)."""
    global _MEMORY
    if _MEMORY is None:
        _MEMORY = MemoryGraph()
    return _MEMORY


def user_file() -> Path:
    p = Path(settings.kg_user_file)
    return p if p.is_absolute() else ROOT / p


def user_graph(persist: bool = True) -> MemoryGraph:
    """The user's graph: the saved snapshot if there is one, else the seed. With persist=True every
    change is written back; with persist=False it is a private sandbox copy."""
    f = user_file()
    if f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        g = MemoryGraph(data.get("nodes", []), data.get("edges", []))
    else:
        g = MemoryGraph()
    g.persist = f if persist else None
    return g


def graph(live: bool = False, persist: bool = True) -> Any:
    """Which graph the tools act on.

    frozen (benchmark)      a fresh seed graph per call: writes stay inside one run
    live, persist=False     a sandbox copy of the user's graph (live benchmark runs)
    live, persist=True      the user's graph: Neo4j when KG_BACKEND=neo4j, else the saved file
    """
    if not live:
        return MemoryGraph()
    if persist and settings.kg_backend.lower() == "neo4j":
        return Neo4jGraph()
    return user_graph(persist)


# ------------------------------------------------------------- CRUD operations ----
# Model-facing write operations. Every change is validated and stamped with its provenance
# (source = "user", date) so user-added knowledge stays distinguishable from the seed.
MAX_PROPS, MAX_TEXT = 20, 300


def _props(properties: Any) -> dict:
    if properties in (None, "", {}):
        return {}
    if not isinstance(properties, dict):
        raise ValueError("properties must be an object of name -> value")
    if len(properties) > MAX_PROPS:
        raise ValueError(f"at most {MAX_PROPS} properties")
    out = {}
    for k, v in properties.items():
        if not IDENT.match(str(k)) or k in ("id", "label", "from", "to", "type"):
            raise ValueError(f"invalid property name {k!r}")
        if not isinstance(v, (str, int, float, bool)):
            raise ValueError(f"property {k!r} must be text, a number or true/false")
        out[k] = v[:MAX_TEXT] if isinstance(v, str) else v
    return out


def _endpoint(g: Any, entity: str) -> tuple[str | None, dict | None]:
    n = g.resolve(entity)
    if n is None:
        err = g._unknown(entity) if hasattr(g, "_unknown") else {"error": f"unknown entity {entity!r}"}
        err["hint"] = "add it first with kg_add_entity"
        return None, err
    return n["id"], None


def upsert_entity(g: Any, entity: str, label: str | None = None, name: str | None = None,
                  properties: Any = None) -> dict:
    """Create an entity, or update the name/properties of an existing one."""
    try:
        props = _props(properties)
    except ValueError as e:
        return {"error": str(e)}
    today = date.today().isoformat()
    existing = g.resolve(entity)
    if existing:
        if label and label != existing.get("label"):
            return {"error": f"{existing['id']} is a {existing.get('label')}; an entity's type cannot be changed"}
        upd = {**props, "updated": today, **({"name": name[:MAX_TEXT]} if name else {})}
        g.add_node(existing["id"], existing["label"], **upd)
        return {"ok": True, "action": "updated", "entity": existing["id"], "changed": sorted(upd)}
    if not label:
        return {"error": f"{entity!r} is new: give its label (Company, Industry, Sector, Country, MacroSeries, "
                         "or another single word)"}
    eid = (entity or "").strip()
    if not ENTITY_ID.match(eid):
        return {"error": "invalid entity id: letters, digits and : . _ - only, at most 64 characters"}
    try:
        g.add_node(eid, _check_ident("label", label), name=(name or eid)[:MAX_TEXT], source="user",
                   added=today, **props)
    except ValueError as e:
        return {"error": str(e)}
    return {"ok": True, "action": "created", "entity": eid, "label": label}


def upsert_relation(g: Any, source: str, relation: str, target: str, properties: Any = None) -> dict:
    """Create a relation, or update the properties of an existing one (MERGE semantics)."""
    rel = (relation or "").upper().strip()
    if not IDENT.match(rel):
        return {"error": f"invalid relation {relation!r}: one word such as SUPPLIES or PARTNERS_WITH"}
    try:
        props = _props(properties)
    except ValueError as e:
        return {"error": str(e)}
    a, err = _endpoint(g, source)
    if err:
        return err
    b, err = _endpoint(g, target)
    if err:
        return err
    if a == b:
        return {"error": "a relation needs two different entities"}
    existed = g.has_edge(a, rel, b)
    today = date.today().isoformat()
    stamp = {"updated": today} if existed else {"source": "user", "added": today}
    g.add_edge(a, rel, b, **props, **stamp)
    return {"ok": True, "action": "updated" if existed else "created", "relation": f"{a} -{rel}-> {b}"}


def delete_relation(g: Any, source: str, relation: str, target: str) -> dict:
    rel = (relation or "").upper().strip()
    if not IDENT.match(rel):
        return {"error": f"invalid relation {relation!r}"}
    a, err = _endpoint(g, source)
    if err:
        return err
    b, err = _endpoint(g, target)
    if err:
        return err
    n = g.remove_edge(a, rel, b)
    if not n:
        return {"error": f"no {rel} relation from {a} to {b}",
                **({"relations": g.relation_types()} if rel not in g.relation_types() else {})}
    return {"ok": True, "action": "deleted", "relation": f"{a} -{rel}-> {b}"}


def delete_entity(g: Any, entity: str) -> dict:
    eid, err = _endpoint(g, entity)
    if err:
        return err
    k = g.remove_node(eid)
    return {"ok": True, "action": "deleted", "entity": eid, "relations_removed": k}


# ------------------------------------------------------------------------ CLI ----
def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="alex-kg", description="Manage / query the alex knowledge graph.")
    ap.add_argument("--backend", choices=("memory", "neo4j"), default=None,
                    help="default: KG_BACKEND from .env")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load", help="load the seed graph into Neo4j (idempotent MERGE)")
    sub.add_parser("clear", help="delete every :Entity node from Neo4j")
    sy = sub.add_parser("sync", help="add live sector/industry/country/correlation data for tickers")
    sy.add_argument("tickers", nargs="+")
    sub.add_parser("stats")
    nb = sub.add_parser("neighbors")
    nb.add_argument("entity"); nb.add_argument("--relation"); nb.add_argument("--direction", default="both")
    pa = sub.add_parser("path")
    pa.add_argument("entities", nargs="+"); pa.add_argument("--max-hops", type=int, default=4)
    pa.add_argument("--relations", help="comma-separated relation types to traverse")
    ae = sub.add_parser("add-entity", help="create or update an entity")
    ae.add_argument("entity"); ae.add_argument("--label"); ae.add_argument("--name")
    ar = sub.add_parser("add-relation", help="create or update a relation, e.g. ASML SUPPLIES INTC")
    ar.add_argument("source"); ar.add_argument("relation"); ar.add_argument("target")
    ar.add_argument("--prop", action="append", default=[], help="key=value (repeatable)")
    dr = sub.add_parser("delete-relation")
    dr.add_argument("source"); dr.add_argument("relation"); dr.add_argument("target")
    de = sub.add_parser("delete-entity")
    de.add_argument("entity")
    sub.add_parser("reset", help="discard the saved user graph (memory backend) and start from the seed")
    a = ap.parse_args(argv)

    backend = (a.backend or settings.kg_backend).lower()
    if a.cmd == "reset":
        f = user_file()
        existed = f.exists()
        if existed:
            f.unlink()
        print(json.dumps({"reset": True, "removed": str(f) if existed else None}))
        return
    g: Any = Neo4jGraph() if backend == "neo4j" or a.cmd in ("load", "clear") else user_graph()
    try:
        if a.cmd == "load":
            out: Any = g.load(*seed())
        elif a.cmd == "clear":
            g.clear(); out = {"cleared": True}
        elif a.cmd == "add-entity":
            out = upsert_entity(g, a.entity, a.label, a.name)
        elif a.cmd == "add-relation":
            props = dict(p.split("=", 1) for p in a.prop if "=" in p)
            out = upsert_relation(g, a.source, a.relation, a.target, props)
        elif a.cmd == "delete-relation":
            out = delete_relation(g, a.source, a.relation, a.target)
        elif a.cmd == "delete-entity":
            out = delete_entity(g, a.entity)
        elif a.cmd == "sync":
            out = sync_live(g, [t.upper() for t in a.tickers])
        elif a.cmd == "stats":
            out = g.stats()
        elif a.cmd == "neighbors":
            out = g.neighbors(a.entity, a.relation, a.direction)
        else:
            out = g.path(a.entities, a.max_hops, a.relations.split(",") if a.relations else None)
        print(json.dumps(out, indent=2, default=str))
    finally:
        if isinstance(g, Neo4jGraph):
            g.close()


if __name__ == "__main__":
    main()
