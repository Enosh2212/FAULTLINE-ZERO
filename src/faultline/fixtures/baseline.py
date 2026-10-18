"""Intentionally correct sample application logic (synthetic, no real payments)."""


def handle_gateway_webhook(event_id: str, amount: int, ledger: list[dict]) -> None:
    # Invariant: repeated delivery of the same event never charges twice.
    if not any(item["event_id"] == event_id for item in ledger):
        ledger.append({"event_id": event_id, "amount": amount})


def reserve_inventory(stock: int, requested: int) -> int:
    if requested <= 0:
        raise ValueError("requested quantity must be positive")
    if stock < requested:
        raise ValueError("not enough stock")
    return stock - requested


def calculate_total(subtotal: int, discount: int) -> int:
    return max(0, subtotal - discount)


def process_refund(refund_id: str, amount: int, wallet: dict) -> None:
    # Invariant: duplicate delivery of a refund event never credits the wallet twice.
    processed = wallet.setdefault("processed_refunds", [])
    if refund_id not in processed:
        wallet["balance"] = wallet.get("balance", 0) + amount
        processed.append(refund_id)

