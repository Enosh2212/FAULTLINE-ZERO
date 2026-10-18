import json
from types import SimpleNamespace

import pytest

from faultline.config import Settings
from faultline.git_demo import create_demo, inspect_change, OWNERS, symbols, git
from faultline.graph_repository import GraphUnavailable
from faultline.schema import ChangeSummary, GraphNode, GraphEdge, PlanEntry, ExecutionResult
from faultline.tool_agent import ToolInvestigator
from tests.conftest import FakeGraphRepository


class GitRepo(FakeGraphRepository):
    def index_git(self, data):
        self.data = data

    def plan(self, change_id):
        if self.fail_plan:
            return []
        mapping = {"S-PAYMENTS": ("INV-PAY-01", "TC-PAY-IDEMPOTENCY"),
                   "S-INVENTORY": ("INV-STOCK-01", "TC-STOCK-NONNEGATIVE"),
                   "S-ORDERS": ("INV-ORDER-01", "TC-ORDER-TOTAL")}
        result = []
        for name in self.data["modified_symbols"]:
            service = OWNERS[name]
            if service in mapping:
                invariant, test = mapping[service]
                result.append(PlanEntry(symbol_id=change_id+":"+name, origin_service=service,
                    impacted_service=service, invariant_id=invariant, testcase_id=test))
        return result

    def uncovered_invariants(self, change_id):
        if self.fail_plan:
            return []
        mapping = {"S-REFUNDS": ("INV-REFUND-01", "Refund idempotency & ledger consistency", "Duplicate refund deliveries must not credit balance more than once.")}
        result = []
        for name in self.data.get("modified_symbols", []):
            service = OWNERS.get(name)
            if service in mapping:
                inv, title, desc = mapping[service]
                result.append({"symbol_id": change_id + ":" + name, "origin_service": service,
                               "impacted_service": service, "invariant_id": inv,
                               "invariant_name": title, "description": desc})
        return result


    def snapshot(self):
        data = super().snapshot()
        for symbol in self.data["symbols"]:
            sid = self.data["change_id"]+":"+symbol["name"]
            data.nodes.append(GraphNode(id=sid, label=symbol["name"], kind="Symbol"))
            data.edges.append(GraphEdge(source=sid, target=OWNERS[symbol["name"]], relation="PART_OF"))
            if symbol["name"] in self.data["modified_symbols"]:
                data.edges.append(GraphEdge(source=self.data["change_id"], target=sid, relation="TOUCHES"))
        return data

    def save_actions(self, report):
        pass


@pytest.fixture
def demo(tmp_path, monkeypatch):
    root = tmp_path / "commerce"
    create_demo(root)
    monkeypatch.setenv("FZ_DEMO_REPO", str(root))
    monkeypatch.setattr("faultline.tool_agent.get_settings", lambda: Settings())
    return root


@pytest.mark.parametrize("key,verdict,symbol", [
    ("payment", "reproduced", "handle_gateway_webhook"),
    ("inventory", "reproduced", "reserve_inventory"),
    ("control", "not_reproduced", "calculate_total"),
    ("uncovered", "inconclusive", "shipping_quote"),
])
def test_real_diff_and_execution(demo, key, verdict, symbol):
    diff = inspect_change(key)
    assert diff["modified_symbols"] == [symbol]
    assert "diff --git" in diff["diff"]
    result = ToolInvestigator(GitRepo(), key, mode="deterministic").run()
    assert result.verdict.value == verdict
    assert result.mode == "deterministic_fallback"
    assert result.status == "completed"
    if key == "uncovered":
        assert not result.cases
    else:
        assert result.cases[0].baseline.outcome == "pass"


def test_modified_trusted_blob_is_rejected(demo):
    git(demo, "checkout", "--detach", "payment")
    (demo / "commerce.py").write_text("raise RuntimeError('untrusted')")
    git(demo, "add", "commerce.py")
    git(demo, "commit", "-m", "tamper")
    git(demo, "tag", "-f", "payment")
    with pytest.raises(ValueError, match="verification failed"):
        inspect_change("payment")


def test_ref_and_path_input_rejected(demo):
    with pytest.raises(ValueError):
        inspect_change("../../anything")


def test_ast_indexes_classes_nested_methods():
    result = symbols("import os\nclass Cart:\n    def total(self):\n        return 0\n")
    assert [s["name"] for s in result] == ["Cart", "Cart.total"]


def test_no_graph_paths_means_no_execution(demo):
    repo = GitRepo()
    repo.fail_plan = True
    result = ToolInvestigator(repo, "payment", mode="deterministic").run()
    assert not result.cases and result.verdict.value == "inconclusive"


def test_graph_disconnection_has_no_hardcoded_fallback(demo):
    repo = GitRepo()
    def unavailable(_):
        raise GraphUnavailable("offline")
    repo.plan = unavailable
    with pytest.raises(GraphUnavailable):
        ToolInvestigator(repo, "payment", mode="deterministic").run()


class ScriptedModel:
    """Protocol test double, explicitly not verification of a real model."""
    def __init__(self, actions):
        self.actions = iter(actions)
        self.observations = []
    def choose(self, messages, timeout):
        self.observations.append(list(messages))
        name, args = next(self.actions)
        return {"role": "assistant", "content": "Untrusted model claim: everything is safe", "tool_calls": [
            {"id": "call-"+str(len(self.observations)), "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def test_model_selects_tools_and_observes_execution(demo):
    model = ScriptedModel([("get_git_diff", {}), ("trace_impact_graph", {}),
        ("compare_revisions", {"testcase_id": "TC-PAY-IDEMPOTENCY"}), ("record_finding", {}), ("finalize_investigation", {})])
    result = ToolInvestigator(GitRepo(), "payment", model=model).run()
    assert result.verdict.value == "reproduced"  # model's prose cannot override evidence
    assert result.metrics["llm_calls"] == 5
    assert any(m["role"] == "tool" and '"outcome": "fail"' in m["content"] for m in model.observations[-1])


def test_model_cannot_execute_tests_without_graph_authorization(demo):
    model = ScriptedModel([("compare_revisions", {"testcase_id": "TC-PAY-IDEMPOTENCY"})])
    result = ToolInvestigator(GitRepo(), "payment", model=model, max_iterations=1).run()
    assert not result.cases and result.verdict.value == "inconclusive"
    assert result.steps[0].status == "error"


def test_model_unavailable_is_not_silent_deterministic_execution(demo):
    class Offline:
        def choose(self, *args):
            raise TimeoutError("provider offline")
    result = ToolInvestigator(GitRepo(), "payment", model=Offline(), max_iterations=2).run()
    assert result.status == "error" and not result.cases
    assert len(result.steps) == 2


def test_require_model_without_credentials(demo):
    with pytest.raises(ValueError, match="not configured"):
        ToolInvestigator(GitRepo(), "payment", mode="model")


def test_unknown_arguments_and_invented_verdict_rejected(demo):
    model = ScriptedModel([("finalize_investigation", {"verdict": "pass"})])
    report = ToolInvestigator(GitRepo(), "payment", model=model, max_iterations=1).run()
    assert report.verdict.value == "inconclusive" and report.steps[0].status == "error"


def test_runner_error_has_error_verdict(demo):
    agent = ToolInvestigator(GitRepo(), "payment", mode="deterministic")
    agent.runner.run = lambda *_: ExecutionResult(outcome="error", observed="failed worker", duration_ms=0)
    report = agent.run()
    assert report.verdict.value == "investigation_error" and report.status == "error"


def test_contradictory_topology_rejects_execution(demo):
    repo = GitRepo()
    original = repo.snapshot
    def broken():
        snapshot = original()
        snapshot.edges = [e for e in snapshot.edges if e.relation != "VALIDATES"]
        return snapshot
    repo.snapshot = broken
    report = ToolInvestigator(repo, "payment", mode="deterministic", max_iterations=6).run()
    assert not report.cases and report.verdict.value == "inconclusive"


def test_early_finalization_is_inconclusive(demo):
    model = ScriptedModel([("get_git_diff", {}), ("trace_impact_graph", {}), ("finalize_investigation", {})])
    report = ToolInvestigator(GitRepo(), "payment", model=model).run()
    assert report.verdict.value == "inconclusive"



def test_provider_adapter_preserves_tool_protocol(monkeypatch):
    from faultline.tool_agent import CompatibleModel
    observed = {}
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"tool_calls": [{"id": "x", "type": "function", "function": {"name": "get_git_diff", "arguments": "{}"}}]}}], "usage": {"prompt_tokens": 9, "completion_tokens": 4}}
    def post(url, **kwargs):
        observed.update(kwargs)
        return Response()
    monkeypatch.setattr("httpx.post", post)
    model = CompatibleModel(Settings(llm_base_url="https://example.test/v1", llm_model="test", llm_api_key="not-real"))
    result = model.choose([{"role":"user","content":"Synthetic change"}], 2)
    assert result["tool_calls"][0]["function"]["name"] == "get_git_diff"
    assert observed["json"]["tool_choice"] == "required"
    assert observed["json"]["parallel_tool_calls"] is False
    assert model.usage == {"prompt_tokens":9,"completion_tokens":4}
    assert all(t["function"]["parameters"]["additionalProperties"] is False for t in observed["json"]["tools"])


def test_provider_adapter_rejects_multiple_calls(monkeypatch):
    from faultline.tool_agent import CompatibleModel
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices":[{"message":{"tool_calls":[{},{}]}}]}
    monkeypatch.setattr("httpx.post", lambda *a, **k: Response())
    model = CompatibleModel(Settings(llm_base_url="https://example.test", llm_model="test", llm_api_key="not-real"))
    with pytest.raises(ValueError, match="exactly one"):
        model.choose([], 2)


def test_holdout_regression_discovery(demo):
    """Verify that a previously unseen regression (refund) is discovered and reproduced via counterexample synthesis."""
    repo = GitRepo()
    result = ToolInvestigator(repo, "refund", mode="deterministic").run()
    assert result.verdict.value == "reproduced"
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.testcase_id == "SPEC-REFUND-IDEMPOTENCY"
    assert case.invariant_id == "INV-REFUND-01"
    assert case.baseline.outcome == "pass"
    assert case.candidate.outcome == "fail"
    assert "Duplicate refund credited" in case.candidate.observed
    assert result.status == "completed"
    assert result.execution_mode == "DETERMINISTIC FALLBACK"
    assert len(result.discovered_scenarios) == 1


def test_graph_ablation_fails_discovery(demo):
    """Ablation: remove the graph invariant connection and verify discovery fails without graph intelligence."""
    repo = GitRepo()
    # Ablate: withhold uncovered invariants from the graph
    repo.uncovered_invariants = lambda *_: []
    result = ToolInvestigator(repo, "refund", mode="deterministic").run()
    # Without graph intelligence connecting symbol to invariant, counterexample cannot be discovered
    assert result.verdict.value == "inconclusive"
    assert len(result.cases) == 0


def test_model_rate_limit_backoff_recovery(monkeypatch):
    """Test that CompatibleModel recovers gracefully from HTTP 429 rate limit."""
    import httpx
    from faultline.tool_agent import CompatibleModel
    attempts = 0

    class MockResponse:
        def __init__(self, status_code, headers, data):
            self.status_code = status_code
            self.headers = headers
            self._data = data

        def raise_for_status(self):
            if self.status_code >= 400:
                req = httpx.Request("POST", "https://example.test")
                resp = httpx.Response(self.status_code, request=req, headers=self.headers)
                raise httpx.HTTPStatusError("Rate limited", request=req, response=resp)

        def json(self):
            return self._data

    def mock_post(url, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return MockResponse(429, {"retry-after": "0.01"}, {})
        return MockResponse(200, {}, {
            "choices": [{"message": {"tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_git_diff", "arguments": "{}"}}]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        })

    monkeypatch.setattr("httpx.post", mock_post)
    model = CompatibleModel(Settings(llm_base_url="https://example.test", llm_model="test-model", llm_api_key="secret"))
    msg = model.choose([{"role": "user", "content": "hi"}], 10)
    assert attempts == 2
    assert msg["tool_calls"][0]["function"]["name"] == "get_git_diff"
    assert model.usage["total_tokens"] == 15

