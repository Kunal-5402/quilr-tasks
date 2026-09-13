"""In-memory data. A real server would query a customer system here."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    email: str
    tier: str
    balance: float


_CUSTOMERS: dict[str, Customer] = {
    c.customer_id: c
    for c in [
        Customer("CUST-A1B2C", "Ada Lovelace", "ada@example.com", "gold", 420.50),
        Customer("CUST-X9Y8Z", "Alan Turing", "alan@example.com", "silver", 88.00),
    ]
}

_REFUNDS: dict[str, dict] = {}


def find_customer(customer_id: str) -> Customer | None:
    return _CUSTOMERS.get(customer_id)


def create_refund(customer_id: str, amount: float, reason: str) -> dict:
    refund = {
        "refund_id": f"REF-{uuid.uuid4().hex[:8].upper()}",
        "customer_id": customer_id,
        "amount": amount,
        "reason": reason,
        "status": "pending",
    }
    _REFUNDS[refund["refund_id"]] = refund
    return refund


def find_refund(refund_id: str) -> dict | None:
    return _REFUNDS.get(refund_id)
