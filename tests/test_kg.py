"""Knowledge graph: memory backend behaviour, Neo4j backend via a fake driver, and an
optional live Neo4j parity check (set ALEX_NEO4J_TEST_URI / _PASSWORD to run it)."""
import json
import os

import pytest

from alex import kg


@pytest.fixture()
def g():
    return kg.MemoryGraph()


def test_seed_is_consistent(g):
    st = g.stats()
    assert st["labels"]["Company"] == 13 and st["relations"]["SUPPLIES"] == 5
    for e in g.edges:                                   # every edge points at real nodes
        assert e["from"] in g.nodes and e["to"] in g.nodes


def test_resolve_by_id_name_and_fragment(g):
    assert g.resolve("nvda")["id"] == "NVDA"
    assert g.resolve("Taiwan Semiconductor Manufacturing Company")["id"] == "TSM"
    assert g.resolve("10-Year Treasury")["id"] == "DGS10"          # unique name fragment
    assert g.resolve("semiconductors")["id"] == "industry:semiconductors"
    assert g.resolve("Inc") is None                                # ambiguous fragment


def test_neighbors_filters_and_directions(g):
    r = g.neighbors("NVDA", "SUPPLIES", "in")
    assert [x["node"]["id"] for x in r["relations"]] == ["TSM"]
    assert r["relations"][0]["properties"]["product"] == "GPU wafer fabrication"
    assert [x["node"]["id"] for x in g.neighbors("NVDA", "SUPPLIES", "out")["relations"]] == ["MSFT"]
    comp = g.neighbors("AMD", "competes_with", "out")              # symmetric: direction ignored
    assert {x["node"]["id"] for x in comp["relations"]} == {"NVDA", "INTC"}
    assert g.neighbors("NVDA", limit=2)["truncated"] is True


def test_errors_are_helpful(g):
    assert g.neighbors("NVDQ")["did_you_mean"] == ["NVDA"]
    assert "SUPPLIES" in g.neighbors("NVDA", "OWNS")["relations"]
    assert "error" in g.neighbors("NVDA", direction="up")
    assert "error" in g.path(["NVDA"])
    assert "error" in g.path(["NVDA", "AMD"], relations=["NOPE"])


def test_multi_hop_paths(g):
    p = g.path(["AAPL", "NVDA"], relations=["SUPPLIES"])["paths"][0]
    assert p["hops"] == 2 and [n["id"] for n in p["nodes"]] == ["AAPL", "TSM", "NVDA"]
    p = g.path(["ASML", "MSFT"], relations=["SUPPLIES"])["paths"][0]
    assert [n["id"] for n in p["nodes"]] == ["ASML", "TSM", "NVDA", "MSFT"]
    assert g.path(["INFY", "GS"], max_hops=1)["paths"][0]["found"] is False
    many = g.path(["NVDA", "AMD", "INTC"])["paths"]                # first entity to each other one
    assert [(x["to"], x["hops"]) for x in many] == [("AMD", 1), ("INTC", 1)]
    assert g.path(["AAPL", "NVDA"], max_hops=99)["paths"][0]["hops"] == 1   # clamped, not an error


def test_schema_is_open_but_identifiers_are_validated(g):
    g.add_node("XYZ", "Fund", name="XYZ Fund")
    g.add_edge("XYZ", "HOLDS", "NVDA", weight=0.1)
    g.add_edge("XYZ", "HOLDS", "NVDA", weight=0.2)                 # MERGE: updated, not duplicated
    r = g.neighbors("XYZ", "HOLDS")
    assert r["count"] == 1 and r["relations"][0]["properties"]["weight"] == 0.2
    with pytest.raises(ValueError):
        g.add_edge("XYZ", "HOLDS`]->() DETACH DELETE n //", "NVDA")
    with pytest.raises(ValueError):
        g.add_node("bad", "Fund:Admin")


class FakeDriver:
    """Records Cypher; answers just enough for neighbors()."""
    def __init__(self):
        self.queries = []

    def execute_query(self, cypher, params, database_=None):
        self.queries.append((cypher, params))
        rec = lambda d: type("R", (), {"data": lambda self: d})()
        if "RETURN n {.*}" in cypher:
            return [rec({"n": {"id": "NVDA", "label": "Company", "name": "NVIDIA Corporation"}})], None, None
        if "DISTINCT type(r)" in cypher:
            return [rec({"t": "SUPPLIES"})], None, None
        if "startNode(r) = n" in cypher:
            return [rec({"relation": "SUPPLIES", "outgoing": False, "properties": {"product": "wafers"},
                         "id": "TSM", "label": "Company", "name": "TSMC"})], None, None
        return [], None, None

    def close(self):
        pass


def test_neo4j_backend_uses_parameters_only():
    d = FakeDriver()
    g = kg.Neo4jGraph(driver=d)
    r = g.neighbors("NVDA", "SUPPLIES", "in")
    assert r["relations"][0]["node"]["id"] == "TSM"
    hostile = "NVDA'}) DETACH DELETE n //"
    g.neighbors(hostile)
    assert all(hostile not in c for c, _ in d.queries)               # user text never enters Cypher
    assert any(hostile in json.dumps(p) for _, p in d.queries)
    g.load([{"id": "A", "label": "Company"}], [{"from": "A", "type": "SUPPLIES", "to": "A"}])
    with pytest.raises(ValueError):
        g.load([{"id": "A", "label": "X`) DETACH DELETE n //"}], [])


@pytest.mark.skipif(not os.getenv("ALEX_NEO4J_TEST_URI"), reason="no Neo4j test database configured")
def test_live_neo4j_matches_memory_graph():
    neo = kg.Neo4jGraph(os.environ["ALEX_NEO4J_TEST_URI"], os.getenv("ALEX_NEO4J_TEST_USER", "neo4j"),
                        os.environ["ALEX_NEO4J_TEST_PASSWORD"])
    try:
        neo.clear()
        neo.load(*kg.seed())
        neo.load(*kg.seed())                                         # idempotent
        mem = kg.MemoryGraph()
        assert neo.stats()["relations"] == mem.stats()["relations"]
        for args in (("NVDA",), ("DGS10", None, "in"), ("tsm", "SUPPLIES", "out")):
            assert neo.neighbors(*args) == mem.neighbors(*args)
        hop = lambda r: [(p["from"], p["to"], p["found"], p.get("hops")) for p in r["paths"]]
        for args in ((["AAPL", "NVDA"], 4, ["SUPPLIES"]), (["ASML", "MSFT"], 4, ["SUPPLIES"]), (["INFY", "GS"], 1)):
            assert hop(neo.path(*args)) == hop(mem.path(*args))
    finally:
        neo.close()
