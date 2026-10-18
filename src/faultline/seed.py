"""Synthetic reference graph. No real user data or restricted telemetry."""

# Explicit graph model makes the relationship between changed code and tests auditable.
NODES: dict[str, list[tuple[str, str, str]]] = {
    "Service": [
        ("S-CHECKOUT", "Checkout API", "Processes orders"),
        ("S-PAYMENTS", "Payments", "Captures gateway payments"),
        ("S-GATEWAY", "Gateway Adapter", "Handles gateway callbacks"),
        ("S-INVENTORY", "Inventory", "Reserves stock"),
        ("S-ORDERS", "Order Pricing", "Computes order totals"),
        ("S-REFUNDS", "Refunds", "Processes wallet credits and returns"),
    ],
    "Symbol": [
        ("SYM-PAY-01", "handle_gateway_webhook", "faultline.fixtures.candidate"),
        ("SYM-STOCK-01", "reserve_inventory", "faultline.fixtures.candidate"),
        ("SYM-ORDER-01", "calculate_total", "faultline.fixtures.candidate"),
        ("SYM-REFUND-01", "process_refund", "faultline.fixtures.candidate"),
    ],
    "Change": [
        ("CHG-PAY-001", "Webhook idempotency regression", "The candidate removes duplicate-event protection."),
        ("CHG-STOCK-002", "Stock reservation guard regression", "The candidate removes insufficient-stock validation."),
        ("CHG-ORDER-003", "Order pricing refactor (control)", "Harmless control demonstrating a passing change."),
    ],
    "Invariant": [
        ("INV-PAY-01", "Exactly one capture per event", "Duplicate deliveries must not duplicate payments."),
        ("INV-STOCK-01", "Stock is never negative", "Insufficient inventory must reject reservation."),
        ("INV-ORDER-01", "Order total nonnegative", "Discounts may not create negative totals."),
        ("INV-REFUND-01", "Refund idempotency & ledger consistency", "Duplicate refund deliveries must not credit balance more than once."),
    ],
    "TestCase": [
        ("TC-PAY-IDEMPOTENCY", "Duplicate webhook replay", "Replay identical synthetic gateway events."),
        ("TC-STOCK-NONNEGATIVE", "Oversell prevention", "Try reserving more items than available."),
        ("TC-ORDER-TOTAL", "Pricing floor control", "Try a discount larger than subtotal."),
    ],
}

# Cypher edge types are hardcoded, never formed using incoming request fields.
EDGES: dict[str, list[tuple[str, str, str, str]]] = {
    "TOUCHES": [
        ("Change", "CHG-PAY-001", "Symbol", "SYM-PAY-01"),
        ("Change", "CHG-STOCK-002", "Symbol", "SYM-STOCK-01"),
        ("Change", "CHG-ORDER-003", "Symbol", "SYM-ORDER-01"),
    ],
    "PART_OF": [
        ("Symbol", "SYM-PAY-01", "Service", "S-PAYMENTS"),
        ("Symbol", "SYM-STOCK-01", "Service", "S-INVENTORY"),
        ("Symbol", "SYM-ORDER-01", "Service", "S-ORDERS"),
        ("Symbol", "SYM-REFUND-01", "Service", "S-REFUNDS"),
    ],
    "CALLS": [
        ("Service", "S-CHECKOUT", "Service", "S-PAYMENTS"),
        ("Service", "S-CHECKOUT", "Service", "S-INVENTORY"),
        ("Service", "S-CHECKOUT", "Service", "S-ORDERS"),
        ("Service", "S-CHECKOUT", "Service", "S-REFUNDS"),
        ("Service", "S-PAYMENTS", "Service", "S-GATEWAY"),
    ],
    "ENFORCES": [
        ("Service", "S-PAYMENTS", "Invariant", "INV-PAY-01"),
        ("Service", "S-INVENTORY", "Invariant", "INV-STOCK-01"),
        ("Service", "S-ORDERS", "Invariant", "INV-ORDER-01"),
        ("Service", "S-REFUNDS", "Invariant", "INV-REFUND-01"),
    ],
    "VALIDATES": [
        ("TestCase", "TC-PAY-IDEMPOTENCY", "Invariant", "INV-PAY-01"),
        ("TestCase", "TC-STOCK-NONNEGATIVE", "Invariant", "INV-STOCK-01"),
        ("TestCase", "TC-ORDER-TOTAL", "Invariant", "INV-ORDER-01"),
    ],
}
