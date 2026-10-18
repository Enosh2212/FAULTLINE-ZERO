"""In-memory test double ONLY; the real API runtime uses FalkorDB."""
import pytest
from faultline.schema import ChangeSummary, GraphEdge, GraphNode, GraphSnapshot, PlanEntry
from faultline.seed import NODES, EDGES


class FakeGraphRepository:
    def __init__(self):
        self.saved = {}
        self.fail_plan = False

    def ready(self):
        return not self.fail_plan

    def bootstrap(self):
        pass

    def changes(self):
        return [ChangeSummary(id=i, title=n, summary=d) for i, n, d in NODES["Change"]]

    def change(self, change_id):
        return next((x for x in self.changes() if x.id == change_id), None)

    def snapshot(self):
        return GraphSnapshot(
            nodes=[GraphNode(id=i, label=n, kind=kind) for kind, rows in NODES.items() for i, n, _ in rows],
            edges=[GraphEdge(source=s, relation=relation, target=t)
                   for relation, rows in EDGES.items() for _, s, _, t in rows],
        )

    def plan(self, change_id):
        if self.fail_plan:
            return []
        plans = {
            "CHG-PAY-001": ("SYM-PAY-01", "S-PAYMENTS", "INV-PAY-01", "TC-PAY-IDEMPOTENCY"),
            "CHG-STOCK-002": ("SYM-STOCK-01", "S-INVENTORY", "INV-STOCK-01", "TC-STOCK-NONNEGATIVE"),
            "CHG-ORDER-003": ("SYM-ORDER-01", "S-ORDERS", "INV-ORDER-01", "TC-ORDER-TOTAL"),
        }
        p = plans.get(change_id)
        if not p:
            return []
        sym, service, invariant, testcase = p
        return [PlanEntry(symbol_id=sym, origin_service=service, impacted_service=service,
                          invariant_id=invariant, testcase_id=testcase)]

    def uncovered_invariants(self, change_id):
        if self.fail_plan:
            return []
        if change_id in {"CHG-REFUND-001", "GIT-REFUND"}:
            return [{
                "symbol_id": "SYM-REFUND-01", "origin_service": "S-REFUNDS",
                "impacted_service": "S-REFUNDS", "invariant_id": "INV-REFUND-01",
                "invariant_name": "Refund idempotency & ledger consistency",
                "description": "Duplicate refund deliveries must not credit balance more than once."
            }]
        return []

    def evidence_subgraph(self, change_id):
        return self.snapshot()


    def save(self, investigation):
        self.saved[investigation.id] = investigation

    def report(self, investigation_id):
        return self.saved.get(investigation_id)

    def recent_reports(self, limit=8):
        return list(reversed(list(self.saved.values())))[:limit]


@pytest.fixture
def repository():
    return FakeGraphRepository()
