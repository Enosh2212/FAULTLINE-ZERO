"""Deterministic, explainable agent that executes graph-selected test actions.

No LLM is allowed to invent a passing result or make a deployment decision.
"""
from collections import deque
from datetime import datetime, timezone
from uuid import uuid4

from faultline.graph_repository import GraphRepository
from faultline.runner import ScenarioRunner
from faultline.llm_planner import LLMPlanner
from faultline.schema import AgentStep, CaseResult, GraphSnapshot, Investigation, PlanEntry, Verdict


def service_path(snapshot: GraphSnapshot, start: str, target: str) -> list[str]:
    if start == target:
        return [start]
    adjacency: dict[str, list[str]] = {}
    for edge in snapshot.edges:
        if edge.relation == "CALLS":
            adjacency.setdefault(edge.source, []).append(edge.target)
    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        for neighbor in adjacency.get(node, []):
            if neighbor in visited:
                continue
            if neighbor == target:
                return path + [neighbor]
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))
    return []


def classify(baseline: str, candidate: str) -> Verdict:
    if baseline == "pass" and candidate == "fail":
        return Verdict.REPRODUCED
    if baseline == "pass" and candidate == "pass":
        return Verdict.NOT_REPRODUCED
    return Verdict.INCONCLUSIVE


def build_recommendation(verdict: Verdict) -> str:
    if verdict == Verdict.ERROR:
        return "Investigation error: provider or test execution failed. No deployment approval can be inferred; inspect recorded errors and retry."
    if verdict == Verdict.REPRODUCED:
        return "BLOCK candidate deployment: at least one invariant passed baseline and failed candidate. Review trace and patch before retrying."
    if verdict == Verdict.NOT_REPRODUCED:
        return "No regression reproduced by selected scenarios. This is NOT proof of overall deployment safety; retain ordinary test and review gates."
    return "Insufficient executable evidence. Hold automatic approval and request developer review."


class InvestigationAgent:
    def __init__(self, repository: GraphRepository, runner: ScenarioRunner):
        self.repository = repository
        self.runner = runner

    def investigate(self, change_id: str) -> Investigation | None:
        change = self.repository.change(change_id)
        if change is None:
            return None
        trace: list[AgentStep] = []
        plans = self.repository.plan(change_id)  # Critical dependency: cannot infer tests without graph.
        trace.append(AgentStep(tool="falkordb.trace_change", result=f"{len(plans)} relevant invariant-test paths found"))
        plans, planning_step = LLMPlanner().prioritize(change.title, plans)
        trace.append(planning_step)
        topology = self.repository.snapshot()
        trace.append(AgentStep(tool="falkordb.load_provenance", result=f"{len(topology.nodes)} nodes and {len(topology.edges)} relationships read"))
        cases: list[CaseResult] = []
        executed: set[str] = set()
        for item in plans:
            # Bounded, deduplicated and never executes tests selected from user-provided strings.
            if item.testcase_id in executed or len(executed) >= 12:
                continue
            executed.add(item.testcase_id)
            path = service_path(topology, item.origin_service, item.impacted_service)
            if not path:
                trace.append(AgentStep(tool="agent.reject_unproven_path", result=f"No dependency path for {item.testcase_id}"))
                continue
            baseline = self.runner.run("baseline", item.testcase_id)
            candidate = self.runner.run("candidate", item.testcase_id)
            verdict = classify(baseline.outcome, candidate.outcome)
            trace.append(AgentStep(
                tool="runner.compare_revisions",
                result=f"{item.testcase_id}: baseline={baseline.outcome}, candidate={candidate.outcome}; {verdict.value}",
            ))
            cases.append(CaseResult(
                testcase_id=item.testcase_id, invariant_id=item.invariant_id,
                affected_service=item.impacted_service,
                baseline=baseline, candidate=candidate, verdict=verdict,
                evidence_path=[change_id, item.symbol_id, *path, item.invariant_id, item.testcase_id],
            ))
        if any(c.verdict == Verdict.REPRODUCED for c in cases):
            verdict = Verdict.REPRODUCED
        elif cases and all(c.verdict == Verdict.NOT_REPRODUCED for c in cases):
            verdict = Verdict.NOT_REPRODUCED
        else:
            verdict = Verdict.INCONCLUSIVE
        recommendation = build_recommendation(verdict)
        trace.append(AgentStep(tool="policy.deployment_gate", result=recommendation))
        report = Investigation(
            id="INV-" + uuid4().hex[:12].upper(), change_id=change_id, title=change.title,
            verdict=verdict,
            generated_at=datetime.now(timezone.utc).isoformat(), recommendation=recommendation,
            selected_test_count=len(executed), cases=cases, steps=trace,
        )
        self.repository.save(report)
        return report
