from faultline.runner import ScenarioRunner
from faultline.agent import classify, service_path
from faultline.schema import GraphEdge, GraphSnapshot, Verdict


def test_payment_regression_is_executed_against_real_code():
    runner = ScenarioRunner(timeout=6)
    baseline = runner.run("baseline", "TC-PAY-IDEMPOTENCY")
    candidate = runner.run("candidate", "TC-PAY-IDEMPOTENCY")
    assert (baseline.outcome, candidate.outcome) == ("pass", "fail")
    assert "Duplicate capture" in candidate.observed
    assert classify(baseline.outcome, candidate.outcome) is Verdict.REPRODUCED


def test_stock_regression():
    runner = ScenarioRunner(timeout=6)
    assert runner.run("baseline", "TC-STOCK-NONNEGATIVE").outcome == "pass"
    assert runner.run("candidate", "TC-STOCK-NONNEGATIVE").outcome == "fail"


def test_unchanged_control_not_flagged():
    runner = ScenarioRunner(timeout=6)
    assert runner.run("baseline", "TC-ORDER-TOTAL").outcome == "pass"
    assert runner.run("candidate", "TC-ORDER-TOTAL").outcome == "pass"


def test_untrusted_test_names_never_execute():
    runner = ScenarioRunner()
    assert runner.run("candidate", "../../etc/passwd").outcome == "error"
    assert runner.run("nightmare", "TC-PAY-IDEMPOTENCY").outcome == "error"


def test_graph_path_only_traverses_calls():
    snapshot = GraphSnapshot(nodes=[], edges=[
        GraphEdge(source="A", target="B", relation="CALLS"),
        GraphEdge(source="B", target="C", relation="CALLS"),
        GraphEdge(source="A", target="Z", relation="VALIDATES"),
    ])
    assert service_path(snapshot, "A", "C") == ["A", "B", "C"]
    assert service_path(snapshot, "A", "Z") == []
