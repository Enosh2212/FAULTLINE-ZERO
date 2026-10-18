"""Independent business requirements: these assertions are NOT derived from candidate code."""
from importlib import import_module
from typing import Callable


def payment_idempotency(module: object) -> str:
    ledger: list[dict] = []
    module.handle_gateway_webhook("evt_demo_42", 1200, ledger)
    module.handle_gateway_webhook("evt_demo_42", 1200, ledger)
    captures = len(ledger)
    assert captures == 1, f"Duplicate capture: {captures} records for one gateway event"
    return f"One capture for two deliveries (records={captures})"


def stock_never_negative(module: object) -> str:
    try:
        remaining = module.reserve_inventory(2, 5)
    except ValueError:
        return "Oversell rejected (stock=2, request=5)"
    assert remaining >= 0, f"Oversell accepted: remaining stock={remaining}"
    raise AssertionError("Expected stock shortage to be rejected")


def total_never_negative(module: object) -> str:
    result = module.calculate_total(300, 500)
    assert result == 0, f"Total should be clamped to zero, got {result}"
    return "Discount correctly bounded at zero"


ALLOWED_SCENARIOS: dict[str, Callable[[object], str]] = {
    "TC-PAY-IDEMPOTENCY": payment_idempotency,
    "TC-STOCK-NONNEGATIVE": stock_never_negative,
    "TC-ORDER-TOTAL": total_never_negative,
}


def execute(version: str, testcase_id: str) -> str:
    if version not in {"baseline", "candidate"}:
        raise ValueError("unknown revision")
    scenario = ALLOWED_SCENARIOS.get(testcase_id)
    if scenario is None:
        raise ValueError("testcase not allowlisted")
    module = import_module(f"faultline.fixtures.{version}")
    return scenario(module)
