"""Knowledge-graph create / update / delete: semantics, provenance, validation, persistence,
benchmark sandboxing, and the same operations on Neo4j (fake driver + optional live test)."""
import json
import os

import pytest

from alex import claude_code, kg
from alex.tools import SCHEMAS, WRITE_TOOLS, frozen_dispatch


@pytest.fixture()
def g():
    return kg.MemoryGraph()


def test_create_read_update_delete_cycle(g):
    assert kg.upsert_entity(g, "SMCI", "Company", "Super Micro Computer")["action"] == "created"
    assert g.nodes["SMCI"]["source"] == "user" and g.nodes["SMCI"]["added"]
    r = kg.upsert_relation(g, "NVIDIA", "supplies", "SMCI", {"product": "GPUs"})   # name resolves, case folds
    assert r == {"ok": True, "action": "created", "relation": "NVDA -SUPPLIES-> SMCI"}
    assert [x["node"]["id"] for x in g.neighbors("SMCI", "SUPPLIES", "in")["relations"]] == ["NVDA"]
    upd = kg.upsert_relation(g, "NVDA", "SUPPLIES", "SMCI", {"product": "GPU servers"})
    assert upd["action"] == "updated" and g.neighbors("SMCI")["relations"][0]["properties"]["product"] == "GPU servers"
    assert kg.upsert_entity(g, "SMCI", name="Supermicro")["action"] == "updated"
    assert kg.delete_relation(g, "NVDA", "SUPPLIES", "SMCI")["action"] == "deleted"
    assert kg.delete_entity(g, "SMCI") == {"ok": True, "action": "deleted", "entity": "SMCI", "relations_removed": 0}
    assert g.resolve("SMCI") is None


def test_seed_facts_can_be_corrected_and_symmetric_relations_match_either_way(g):
    assert kg.delete_relation(g, "INTC", "COMPETES_WITH", "NVDA")["ok"]          # stored as NVDA->INTC
    assert [x["node"]["id"] for x in g.neighbors("NVDA", "COMPETES_WITH")["relations"]] == ["AMD"]
    n = len(g.edges)
    assert kg.delete_entity(g, "TSM")["relations_removed"] > 0 and len(g.edges) < n
    assert not g.path(["AAPL", "NVDA"], relations=["SUPPLIES"])["paths"][0]["found"]


def test_validation_and_helpful_errors(g):
    assert "label" in kg.upsert_entity(g, "NEWCO")["error"]                    # new entity needs a type
    assert "cannot be changed" in kg.upsert_entity(g, "NVDA", "Sector")["error"]
    assert "invalid" in kg.upsert_entity(g, "bad id!", "Company")["error"]
    assert "invalid relation" in kg.upsert_relation(g, "NVDA", "SUPPLIES ); DROP", "AMD")["error"]
    assert kg.upsert_relation(g, "NVDQ", "SUPPLIES", "AMD")["did_you_mean"] == ["NVDA"]
    assert "two different" in kg.upsert_relation(g, "NVDA", "SUPPLIES", "NVDA")["error"]
    assert "property" in kg.upsert_relation(g, "NVDA", "SUPPLIES", "AMD", {"x": [1, 2]})["error"]
    assert "property name" in kg.upsert_relation(g, "NVDA", "SUPPLIES", "AMD", {"id": "x"})["error"]
    assert "no PARTNERS" in kg.delete_relation(g, "NVDA", "PARTNERS", "AMD")["error"]


def test_user_graph_persists_and_resets(tmp_path, monkeypatch):
    f = tmp_path / "kg_user.json"
    monkeypatch.setattr(kg.settings, "kg_user_file", str(f))
    g1 = kg.user_graph()
    assert not f.exists()                                                     # nothing written until a change
    kg.upsert_relation(g1, "ASML", "SUPPLIES", "INTC")
    g2 = kg.user_graph()                                                      # a later process sees it
    assert g2.has_edge("ASML", "SUPPLIES", "INTC")
    assert json.loads(f.read_text())["edges"]
    sandbox = kg.user_graph(persist=False)                                    # live benchmark: a copy
    kg.delete_relation(sandbox, "ASML", "SUPPLIES", "INTC")
    assert kg.user_graph().has_edge("ASML", "SUPPLIES", "INTC")               # the saved graph is untouched
    kg.main(["reset"])
    assert not f.exists() and not kg.user_graph().has_edge("ASML", "SUPPLIES", "INTC")


def test_benchmark_runs_are_sandboxed():
    a, b = frozen_dispatch(), frozen_dispatch()
    a["kg_delete_entity"]("TSM")
    assert b["kg_neighbors"]("TSM")["entity"]["id"] == "TSM"                  # another run is unaffected
    assert kg.memory_graph().resolve("TSM")                                   # the reference copy too


def test_write_tools_are_offered_everywhere_and_sandbox_flags_are_right():
    assert WRITE_TOOLS <= {s["name"] for s in SCHEMAS}
    claude_code.mcp_config.cache_clear()
    bench_live = json.loads(open(claude_code.mcp_config(True)).read())["mcpServers"]["alex"]["args"]
    chat_live = json.loads(open(claude_code.mcp_config(True, persist=True)).read())["mcpServers"]["alex"]["args"]
    assert "--sandbox" in bench_live and "--sandbox" not in chat_live


class FakeDriver:
    def __init__(self):
        self.queries = []

    def execute_query(self, cypher, params, database_=None):
        self.queries.append((cypher, params))
        rec = lambda d: type("R", (), {"data": lambda self: d})()
        if "RETURN n {.*}" in cypher:
            return [rec({"n": {"id": params["e"].upper(), "label": "Company", "name": params["e"]}})], None, None
        if "count(r) AS n" in cypher:
            return [rec({"n": 0})], None, None
        if "DELETE r" in cypher:
            return [rec({"n": 1})], None, None
        if "DETACH DELETE n RETURN k" in cypher:
            return [rec({"k": 3})], None, None
        if "DISTINCT type(r)" in cypher:
            return [rec({"t": "SUPPLIES"})], None, None
        return [], None, None

    def close(self):
        pass


def test_neo4j_writes_use_parameters_and_validated_types():
    d = FakeDriver()
    g = kg.Neo4jGraph(driver=d)
    assert kg.upsert_relation(g, "asml", "SUPPLIES", "intc")["action"] == "created"
    assert kg.delete_relation(g, "asml", "SUPPLIES", "intc")["action"] == "deleted"
    assert kg.delete_entity(g, "asml")["relations_removed"] == 3
    assert any("-[r:`SUPPLIES`]->" in c for c, _ in d.queries)               # directed, validated type
    assert all("asml" not in c.lower() for c, _ in d.queries)               # ids only as parameters
    assert "invalid relation" in kg.delete_relation(g, "a", "X`]-() DETACH DELETE n //", "b")["error"]


@pytest.mark.skipif(not os.getenv("ALEX_NEO4J_TEST_URI"), reason="no Neo4j test database configured")
def test_live_neo4j_crud_round_trip():
    neo = kg.Neo4jGraph(os.environ["ALEX_NEO4J_TEST_URI"], os.getenv("ALEX_NEO4J_TEST_USER", "neo4j"),
                        os.environ["ALEX_NEO4J_TEST_PASSWORD"])
    try:
        neo.clear()
        neo.load(*kg.seed())
        assert kg.upsert_entity(neo, "SMCI", "Company", "Super Micro Computer")["action"] == "created"
        assert kg.upsert_relation(neo, "NVDA", "SUPPLIES", "SMCI", {"product": "GPUs"})["action"] == "created"
        assert kg.upsert_relation(neo, "NVDA", "SUPPLIES", "SMCI", {"product": "servers"})["action"] == "updated"
        assert kg.delete_relation(neo, "INTC", "COMPETES_WITH", "NVDA")["ok"]   # symmetric, reversed
        assert [x["node"]["id"] for x in neo.neighbors("NVDA", "COMPETES_WITH")["relations"]] == ["AMD"]
        assert kg.delete_entity(neo, "SMCI")["relations_removed"] == 1
        assert neo.resolve("SMCI") is None
    finally:
        neo.clear()
        neo.load(*kg.seed())
        neo.close()
