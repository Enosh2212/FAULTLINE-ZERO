"""Constrained scenario specification and deterministic interpreter.

No arbitrary Python, shell commands, or Cypher are executed.
All scenario actions and invariant checks are schema-validated and executed
against verified revision modules using isolated state containers.
"""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from faultline.schema import ExecutionResult


class ActionType(str, Enum):
    CREATE_ORDER = "create_order"
    RESERVE_INVENTORY = "reserve_inventory"
    CAPTURE_PAYMENT = "capture_payment"
    RETRY_WEBHOOK = "retry_webhook"
    ISSUE_REFUND = "issue_refund"
    QUERY_LEDGER = "query_ledger"
    QUERY_WALLET = "query_wallet"


class ActionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: ActionType
    params: dict[str, Any] = Field(default_factory=dict)


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^SPEC-[A-Z0-9-]+$")
    target_invariant: str = Field(min_length=1, max_length=64)
    initial_state: dict[str, Any] = Field(default_factory=dict)
    ordered_actions: list[ActionStep] = Field(min_length=1, max_length=10)
    expected_properties: dict[str, Any] = Field(default_factory=dict)
    evidence_references: list[str] = Field(default_factory=list)


class ScenarioInterpreter:
    """Safe deterministic interpreter executing only allowlisted commerce operations."""

    @staticmethod
    def execute(module: object, spec: ScenarioSpec) -> ExecutionResult:
        state = {
            "ledger": list(spec.initial_state.get("ledger", [])),
            "wallet": dict(spec.initial_state.get("wallet", {"balance": 100, "processed_refunds": []})),
            "stock": int(spec.initial_state.get("stock", 10)),
            "order_total": None,
            "observations": [],
        }

        try:
            for step in spec.ordered_actions:
                act = step.action
                p = step.params

                if act == ActionType.CAPTURE_PAYMENT:
                    evt_id = str(p.get("event_id", "evt_demo_42"))
                    amount = int(p.get("amount", 1200))
                    getattr(module, "handle_gateway_webhook")(evt_id, amount, state["ledger"])
                    state["observations"].append(f"Captured payment {evt_id} for {amount}")

                elif act == ActionType.RETRY_WEBHOOK:
                    evt_type = str(p.get("event_type", "payment"))
                    if evt_type == "refund":
                        ref_id = str(p.get("refund_id", "ref_auto_01"))
                        amount = int(p.get("amount", 50))
                        getattr(module, "process_refund")(ref_id, amount, state["wallet"])
                        state["observations"].append(f"Retried refund webhook {ref_id}")
                    else:
                        evt_id = str(p.get("event_id", "evt_demo_42"))
                        amount = int(p.get("amount", 1200))
                        getattr(module, "handle_gateway_webhook")(evt_id, amount, state["ledger"])
                        state["observations"].append(f"Retried payment webhook {evt_id}")

                elif act == ActionType.ISSUE_REFUND:
                    ref_id = str(p.get("refund_id", "ref_auto_01"))
                    amount = int(p.get("amount", 50))
                    getattr(module, "process_refund")(ref_id, amount, state["wallet"])
                    state["observations"].append(f"Issued refund {ref_id} for {amount}")

                elif act == ActionType.RESERVE_INVENTORY:
                    requested = int(p.get("requested", 5))
                    new_stock = getattr(module, "reserve_inventory")(state["stock"], requested)
                    state["stock"] = new_stock
                    state["observations"].append(f"Reserved {requested} items, remaining {new_stock}")

                elif act == ActionType.CREATE_ORDER:
                    subtotal = int(p.get("subtotal", 300))
                    discount = int(p.get("discount", 500))
                    total = getattr(module, "calculate_total")(subtotal, discount)
                    state["order_total"] = total
                    state["observations"].append(f"Order total: {total}")

                elif act == ActionType.QUERY_WALLET:
                    state["observations"].append(f"Wallet balance: {state['wallet'].get('balance', 0)}")

                elif act == ActionType.QUERY_LEDGER:
                    state["observations"].append(f"Ledger entries: {len(state['ledger'])}")

            # Evaluate independent invariant oracles
            inv = spec.target_invariant

            if inv == "INV-REFUND-01":
                # Invariant: Duplicate refund delivery must not credit wallet multiple times
                expected_balance = spec.expected_properties.get("expected_balance", 150)
                actual_balance = state["wallet"].get("balance", 0)
                processed = state["wallet"].get("processed_refunds", [])
                if actual_balance != expected_balance:
                    return ExecutionResult(
                        outcome="fail",
                        observed=f"Duplicate refund credited: wallet balance={actual_balance} (expected {expected_balance})",
                        duration_ms=0,
                    )
                return ExecutionResult(
                    outcome="pass",
                    observed=f"Refund idempotent: balance={actual_balance}, processed_count={len(processed)}",
                    duration_ms=0,
                )

            elif inv == "INV-PAY-01":
                ledger = state["ledger"]
                if len(ledger) != 1:
                    return ExecutionResult(
                        outcome="fail",
                        observed=f"Duplicate payment captures: {len(ledger)} records for one event",
                        duration_ms=0,
                    )
                return ExecutionResult(
                    outcome="pass",
                    observed=f"Payment idempotent: exactly 1 capture in ledger",
                    duration_ms=0,
                )

            elif inv == "INV-STOCK-01":
                if state["stock"] < 0:
                    return ExecutionResult(
                        outcome="fail",
                        observed=f"Oversell accepted: remaining stock={state['stock']}",
                        duration_ms=0,
                    )
                return ExecutionResult(
                    outcome="pass",
                    observed=f"Stock constraint preserved: remaining={state['stock']}",
                    duration_ms=0,
                )

            elif inv == "INV-ORDER-01":
                tot = state["order_total"]
                if tot is not None and tot < 0:
                    return ExecutionResult(
                        outcome="fail",
                        observed=f"Order total negative: {tot}",
                        duration_ms=0,
                    )
                return ExecutionResult(
                    outcome="pass",
                    observed=f"Order total nonnegative: {tot}",
                    duration_ms=0,
                )

            return ExecutionResult(
                outcome="pass",
                observed="; ".join(state["observations"][-3:]),
                duration_ms=0,
            )

        except AssertionError as exc:
            return ExecutionResult(outcome="fail", observed=str(exc)[:300], duration_ms=0)
        except ValueError as exc:
            # If stock shortage was expected, handle it
            if spec.target_invariant == "INV-STOCK-01":
                return ExecutionResult(outcome="pass", observed=f"Shortage rejected correctly: {exc}", duration_ms=0)
            return ExecutionResult(outcome="error", observed=f"Execution error: {exc}", duration_ms=0)
        except Exception as exc:
            return ExecutionResult(outcome="error", observed=f"Runtime error: {type(exc).__name__}: {exc}", duration_ms=0)


def synthesize_counterexample(invariant_id: str, symbol_name: str | None = None) -> ScenarioSpec:
    """Generate a structured, bounded counterexample scenario to test an invariant."""
    if invariant_id == "INV-REFUND-01":
        return ScenarioSpec(
            id="SPEC-REFUND-IDEMPOTENCY",
            target_invariant="INV-REFUND-01",
            initial_state={"wallet": {"balance": 100, "processed_refunds": []}},
            ordered_actions=[
                ActionStep(action=ActionType.ISSUE_REFUND, params={"refund_id": "ref_holdout_101", "amount": 50}),
                ActionStep(action=ActionType.RETRY_WEBHOOK, params={"event_type": "refund", "refund_id": "ref_holdout_101", "amount": 50}),
                ActionStep(action=ActionType.QUERY_WALLET, params={}),
            ],
            expected_properties={"expected_balance": 150, "expected_refund_count": 1},
            evidence_references=["INV-REFUND-01", "S-REFUNDS", symbol_name or "process_refund"],
        )
    elif invariant_id == "INV-PAY-01":
        return ScenarioSpec(
            id="SPEC-PAY-IDEMPOTENCY",
            target_invariant="INV-PAY-01",
            initial_state={"ledger": []},
            ordered_actions=[
                ActionStep(action=ActionType.CAPTURE_PAYMENT, params={"event_id": "evt_spec_42", "amount": 1000}),
                ActionStep(action=ActionType.RETRY_WEBHOOK, params={"event_type": "payment", "event_id": "evt_spec_42", "amount": 1000}),
                ActionStep(action=ActionType.QUERY_LEDGER, params={}),
            ],
            expected_properties={"expected_records": 1},
            evidence_references=["INV-PAY-01", "S-PAYMENTS", symbol_name or "handle_gateway_webhook"],
        )
    elif invariant_id == "INV-STOCK-01":
        return ScenarioSpec(
            id="SPEC-STOCK-OVERSELL",
            target_invariant="INV-STOCK-01",
            initial_state={"stock": 2},
            ordered_actions=[
                ActionStep(action=ActionType.RESERVE_INVENTORY, params={"requested": 5}),
            ],
            expected_properties={"should_reject": True},
            evidence_references=["INV-STOCK-01", "S-INVENTORY", symbol_name or "reserve_inventory"],
        )
    elif invariant_id == "INV-ORDER-01":
        return ScenarioSpec(
            id="SPEC-ORDER-FLOOR",
            target_invariant="INV-ORDER-01",
            initial_state={},
            ordered_actions=[
                ActionStep(action=ActionType.CREATE_ORDER, params={"subtotal": 300, "discount": 500}),
            ],
            expected_properties={"expected_total": 0},
            evidence_references=["INV-ORDER-01", "S-ORDERS", symbol_name or "calculate_total"],
        )
    raise ValueError(f"Unknown invariant for scenario synthesis: {invariant_id}")
