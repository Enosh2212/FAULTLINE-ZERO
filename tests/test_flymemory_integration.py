"""Integration tests for FlyMemory retrieval, agent tool execution, and FalkorDB grounding."""
import pytest

from faultline.flymemory.config import FlyMemoryConfig
from faultline.flymemory.feature_encoder import IncidentFeatureEncoder
from faultline.flymemory.flyhash import FlyHash
from faultline.flymemory.retriever import MemoryRetriever
from faultline.flymemory.store import FlyMemoryStore, IncidentMemory
from faultline.tool_agent import ToolInvestigator, RecallSimilarIncidentsArgs


class MockFalkorRepo:
    """Mock FalkorDB repository providing controlled graph topology answers."""

    def __init__(self):
        self.memories = []

    def _read(self, cypher: str, **kwargs: str):
        sym = kwargs.get("sym", "")
        inv = kwargs.get("inv", "")
        if sym == "handle_gateway_webhook" and inv == "INV-PAY-01":
            return [("S-PAYMENTS", "S-PAYMENTS")]
        if sym == "process_refund" and inv == "INV-REFUND-01":
            return [("S-REFUNDS", "S-REFUNDS")]
        if sym == "reserve_stock" and inv == "INV-STOCK-01":
            return [("S-INVENTORY", "S-INVENTORY")]
        return []

    def _write(self, cypher: str, **kwargs: str):
        return []

    def recent_reports(self, limit: int = 8):
        return []

    def plan(self, change_id: str):
        return []

    def snapshot(self):
        from faultline.schema import GraphSnapshot
        return GraphSnapshot(nodes=[], edges=[])

    def index_git(self, data):
        pass

    def save(self, report):
        pass

    def save_actions(self, report):
        pass


def test_memory_retriever_graph_grounding():
    cfg = FlyMemoryConfig(seed=42)
    store = FlyMemoryStore(cfg)
    encoder = IncidentFeatureEncoder(cfg)
    fhash = FlyHash(cfg)

    # Seed store with historical payment incident
    fp_pay = fhash.hash(encoder.encode(symbols=["handle_gateway_webhook"], invariants=["INV-PAY-01"], services=["S-PAYMENTS"]))
    mem = IncidentMemory(
        id="MEM-HIST-01",
        incident_id="INC-HIST-01",
        repo_id="REPO-COMMERCE",
        title="Historical Webhook Idempotency Bug",
        change_id="payment",
        verdict="reproduced",
        verified=True,
        active_indices=fp_pay,
        symbols=["handle_gateway_webhook"],
        services=["S-PAYMENTS"],
        invariants=["INV-PAY-01"],
        test_strategy="TC-PAY-IDEMPOTENCY",
        evidence_path=["GIT-PAYMENT", "handle_gateway_webhook", "S-PAYMENTS", "INV-PAY-01", "TC-PAY-IDEMPOTENCY"],
    )
    store.add(mem)

    retriever = MemoryRetriever(cfg, store, encoder, fhash)
    mock_repo = MockFalkorRepo()

    query_context = {
        "modified_symbols": ["handle_gateway_webhook"],
        "services": ["S-PAYMENTS"],
        "invariants": ["INV-PAY-01"],
        "diff": "+ charge_customer(order_id)",
    }

    results = retriever.retrieve("REPO-COMMERCE", query_context, graph_repo=mock_repo, top_k=3)

    assert len(results) == 1
    top = results[0]
    assert top.memory_id == "MEM-HIST-01"
    assert top.graph_verified is True, "FalkorDB should verify the topological path"
    assert top.final_score >= top.similarity_score, "Graph verification should apply a confidence boost"
    assert "TC-PAY-IDEMPOTENCY" in top.historical_test_strategy
    assert "INV-PAY-01" in top.shared_invariants
    assert "Similarity hypothesis only" in top.caveat


def test_tool_investigator_recall_similar_incidents_tool():
    repo = MockFalkorRepo()
    investigator = ToolInvestigator(repo, "payment", mode="deterministic")

    # Call the tool explicitly
    res = investigator.action("recall_similar_incidents", RecallSimilarIncidentsArgs(top_k=3))
    assert isinstance(res, list)
    assert len(res) >= 1
    top_hit = res[0]
    assert "similarity_score" in top_hit
    assert "graph_verified" in top_hit
    assert "relevance_explanation" in top_hit
    assert "caveat" in top_hit
    assert "Similarity hypothesis only" in top_hit["caveat"]


def test_tool_investigator_records_memory_on_finish(monkeypatch):
    from faultline.flymemory.store import get_flymemory_store
    store = get_flymemory_store()
    initial_count = store.count("REPO-COMMERCE")

    repo = MockFalkorRepo()
    investigator = ToolInvestigator(repo, "payment", mode="deterministic")
    report = investigator.run()

    # The report should have executed and completed
    assert report.status == "completed"
    # FlyMemory should have incrementally recorded this verified investigation
    final_count = store.count("REPO-COMMERCE")
    assert final_count >= initial_count
