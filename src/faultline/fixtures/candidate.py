"""Deliberately faulty candidate changes FOR EDUCATIONAL DEMONSTRATION ONLY."""


def handle_gateway_webhook(event_id: str, amount: int, ledger: list[dict]) -> None:
    # BUG: missing idempotency check in changed version.
    ledger.append({"event_id": event_id, "amount": amount})


def reserve_inventory(stock: int, requested: int) -> int:
    if requested <= 0:
        raise ValueError("requested quantity must be positive")
    # BUG: insufficient stock check was removed.
    return stock - requested


def calculate_total(subtotal: int, discount: int) -> int:
    return max(0, subtotal - discount)


def process_refund(refund_id: str, amount: int, wallet: dict) -> None:
    # BUG: missing idempotency check; duplicate refund delivery credits multiple times.
    processed = wallet.setdefault("processed_refunds", [])
    wallet["balance"] = wallet.get("balance", 0) + amount
    processed.append(refund_id)

