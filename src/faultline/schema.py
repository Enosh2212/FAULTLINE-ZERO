"""Public API and engine contracts."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    INCONCLUSIVE = "inconclusive"
    ERROR = "investigation_error"


class ChangeSummary(BaseModel):
    id: str
    title: str
    summary: str


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class GraphSnapshot(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class PlanEntry(BaseModel):
    symbol_id: str
    origin_service: str
    impacted_service: str
    invariant_id: str
    testcase_id: str


class ExecutionResult(BaseModel):
    outcome: Literal["pass", "fail", "error"]
    observed: str
    duration_ms: int = Field(ge=0)


class CaseResult(BaseModel):
    testcase_id: str
    invariant_id: str
    affected_service: str
    baseline: ExecutionResult
    candidate: ExecutionResult
    verdict: Verdict
    evidence_path: list[str]


class AgentStep(BaseModel):
    tool: str
    result: str
    arguments: dict = Field(default_factory=dict)
    duration_ms: int = 0
    status: str = "ok"


class Investigation(BaseModel):
    id: str
    change_id: str
    title: str
    verdict: Verdict
    generated_at: str
    recommendation: str
    selected_test_count: int
    cases: list[CaseResult]
    steps: list[AgentStep]
    mode: str = "deterministic"
    status: str = "completed"
    revisions: dict[str, str] = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    model_name: str | None = None
    execution_mode: str = "DETERMINISTIC FALLBACK"
    discovered_scenarios: list[dict] = Field(default_factory=list)
    project_context: dict = Field(default_factory=dict)



class InvestigationRequest(BaseModel):
    change_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9-]+$")
