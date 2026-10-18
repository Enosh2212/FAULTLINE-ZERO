"""Optional bounded LLM planning. The graph and runner remain the source of truth.

The model may reorder graph-authorized scenario execution; it cannot add, remove,
mark a test passing, or override deterministic policy. No model is required for
local operation. Runtime config uses a trusted OpenAI-compatible endpoint.
"""
import json
import logging

from faultline.config import get_settings
from faultline.schema import AgentStep, PlanEntry

logger = logging.getLogger(__name__)


class LLMPlanner:
    def prioritize(self, title: str, plans: list[PlanEntry]) -> tuple[list[PlanEntry], AgentStep]:
        settings = get_settings()
        if not plans:
            return plans, AgentStep(tool="agent.plan", result="No executable graph paths. Conservative inconclusive outcome.")
        if not (settings.llm_api_key and settings.llm_base_url and settings.llm_model):
            return plans, AgentStep(
                tool="agent.deterministic_plan",
                result="No external model configured; retaining graph-derived test order."
            )
        try:
            import httpx
            authorized = [p.testcase_id for p in plans]
            request_data = {
                "model": settings.llm_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": (
                        "You are a software regression triage planner. You may ONLY reorder the "
                        "authorized testcase IDs. You must include every ID exactly once. "
                        "Never predict test results. Respond ONLY with a JSON object: "
                        '{"order":["ID",...],"rationale":"one short sentence"}. '
                        "Do not include other keys."
                    )},
                    {"role": "user", "content": json.dumps({
                        "change": title,
                        "graph_authorized_tests": [
                            {"testcase_id": p.testcase_id, "invariant": p.invariant_id,
                             "affected_service": p.impacted_service} for p in plans
                        ],
                    })},
                ],
            }
            url = settings.llm_base_url.rstrip("/") + "/chat/completions"
            result = httpx.post(
                url, json=request_data,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"}, timeout=7.0,
            )
            result.raise_for_status()
            content = result.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.strip("`").removeprefix("json").strip()
            proposal = json.loads(content)
            order = proposal["order"]
            if not isinstance(order, list) or len(order) != len(authorized) or sorted(order) != sorted(authorized):
                raise ValueError("Model suggested tests outside FalkorDB's authorized plan")
            positions = {identifier: index for index, identifier in enumerate(order)}
            return sorted(plans, key=lambda p: positions[p.testcase_id]), AgentStep(
                tool="agent.llm_priority_plan",
                result=(f"Grounded execution order: {', '.join(order)}. "
                        f"Advisory rationale: {str(proposal.get('rationale', 'none'))[:180]}")
            )
        except Exception as exc:  # Optional external dependency must not block deterministic execution.
            # System still runs graph-selected tests in deterministic order.
            logger.warning("Optional LLM prioritization skipped (%s)", type(exc).__name__)
            return plans, AgentStep(tool="agent.deterministic_fallback",
                                    result="Model unavailable or invalid; graph-authorized order preserved.")
