"""Exercise the real repository's Cypher command orchestration without a Docker dependency."""
from types import SimpleNamespace
import sys

from faultline.config import Settings
from faultline.graph_repository import FalkorGraphRepository, PLAN_CYPHER


class FakeDriverGraph:
    def __init__(self):
        self.calls = []

    def query(self, query, params=None):
        self.calls.append(("write", query, params))
        return SimpleNamespace(result_set=[[1]])

    def ro_query(self, query, params=None):
        self.calls.append(("read", query, params))
        if "RETURN DISTINCT symbol.id" in query:
            result = [["SYM-PAY-01", "S-PAYMENTS", "S-PAYMENTS", "INV-PAY-01", "TC-PAY-IDEMPOTENCY"]]
        elif "RETURN n.id, n.name, labels(n)" in query:
            result = [["S-PAYMENTS", "Payments", ["Service"]]]
        elif "RETURN a.id, type(r), b.id" in query:
            result = [["S-CHECKOUT", "CALLS", "S-PAYMENTS"]]
        elif "RETURN c.id, c.name, c.description" in query:
            result = [["CHG-PAY-001", "Payment", "Changes idempotency"]]
        else:
            result = []
        return SimpleNamespace(result_set=result)


def test_falkor_repository_bootstrap_parameterized_queries(monkeypatch):
    driver = FakeDriverGraph()
    class FakeDB:
        def __init__(self, **kwargs):
            assert kwargs["host"] == "example"
        def select_graph(self, name):
            assert name == "faultline_test"
            return driver
    monkeypatch.setitem(sys.modules, "falkordb", SimpleNamespace(FalkorDB=FakeDB))
    repo = FalkorGraphRepository(Settings(graph_host="example", graph_name="faultline_test"))
    repo.bootstrap()
    assert all("MERGE" in q for mode, q, _ in driver.calls if mode == "write")
    snapshot = repo.snapshot()
    assert snapshot.nodes[0].kind == "Service"
    assert snapshot.edges[0].relation == "CALLS"
    plan = repo.plan("CHG-PAY-001")
    assert plan[0].testcase_id == "TC-PAY-IDEMPOTENCY"
    mode, sql, params = driver.calls[-1]
    assert mode == "read" and "RETURN DISTINCT symbol.id" in sql
    assert params == {"change_id": "CHG-PAY-001"}
    assert "CHG-PAY-001" not in sql  # never concatenate user input
    assert "[:CALLS*0..3]" in PLAN_CYPHER
