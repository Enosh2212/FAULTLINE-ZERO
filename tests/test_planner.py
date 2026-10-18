"""LLM layer cannot make unsupported claims or override graph-selected scenarios."""
from faultline.config import Settings
from faultline.llm_planner import LLMPlanner
from faultline.schema import PlanEntry


def test_missing_model_uses_graph_order(monkeypatch):
    monkeypatch.setattr("faultline.llm_planner.get_settings", lambda: Settings())
    plan = [PlanEntry(symbol_id="SYM", origin_service="S1", impacted_service="S1",
                      invariant_id="INV", testcase_id="TC-PAY-IDEMPOTENCY")]
    result, trace = LLMPlanner().prioritize("Synthetic change", plan)
    assert result == plan
    assert trace.tool == "agent.deterministic_plan"


def test_model_cannot_inject_new_testcase(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": '{"order":["MALICIOUS"],"rationale":"Run anything"}'}}]}

    monkeypatch.setattr("faultline.llm_planner.get_settings", lambda: Settings(
        llm_api_key="demo", llm_model="demo-model", llm_base_url="http://example.test"
    ))
    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: FakeResponse())
    plan = [PlanEntry(symbol_id="SYM", origin_service="S1", impacted_service="S1",
                      invariant_id="INV", testcase_id="TC-PAY-IDEMPOTENCY")]
    result, trace = LLMPlanner().prioritize("Synthetic change", plan)
    assert result == plan
    assert trace.tool == "agent.deterministic_fallback"
