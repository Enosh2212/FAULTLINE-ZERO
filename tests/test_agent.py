from faultline.agent import InvestigationAgent
from faultline.runner import ScenarioRunner
from faultline.schema import Verdict


def test_payment_verdict_and_persistent_memory(repository):
    agent = InvestigationAgent(repository, ScenarioRunner())
    result = agent.investigate("CHG-PAY-001")
    assert result.verdict == Verdict.REPRODUCED
    assert result.selected_test_count == 1
    assert result.cases[0].evidence_path == [
        "CHG-PAY-001", "SYM-PAY-01", "S-PAYMENTS", "INV-PAY-01", "TC-PAY-IDEMPOTENCY"
    ]
    assert repository.report(result.id) == result
    assert "BLOCK" in result.recommendation


def test_control_verdict_is_not_reproduced(repository):
    result = InvestigationAgent(repository, ScenarioRunner()).investigate("CHG-ORDER-003")
    assert result.verdict == Verdict.NOT_REPRODUCED
    assert "NOT proof" in result.recommendation


def test_no_graph_evidence_means_no_execution(repository):
    repository.fail_plan = True
    result = InvestigationAgent(repository, ScenarioRunner()).investigate("CHG-PAY-001")
    assert result.verdict == Verdict.INCONCLUSIVE
    assert result.selected_test_count == 0
    assert not result.cases


def test_unknown_change_returns_none(repository):
    assert InvestigationAgent(repository, ScenarioRunner()).investigate("NOT-REAL") is None
