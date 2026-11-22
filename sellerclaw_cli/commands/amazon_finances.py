from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "amazon-finances"

SPECS = (
    Cmd(
        "summary",
        "GET",
        "/agent/amazon/stores/{store_id}/finances/summary",
        summary=(
            "What Amazon posted to the store's account over a trailing window: totals per Amazon "
            "transaction type (Shipment, Refund, ServiceFee, Adjustment…) and currency, plus the net. "
            "Amazon's own figures and names — nothing estimated. 'truncated' means a busy store had "
            "more transactions than one answer reads; narrow the window."
        ),
        read_only=True,
        flags=(
            flag("days", type=int, minimum=1, maximum=180, default=30, help="Trailing window in days (Amazon: up to 180)."),
        ),
    ),
    Cmd(
        "payouts",
        "GET",
        "/agent/amazon/stores/{store_id}/finances/payouts",
        summary=(
            "Amazon's settlement groups — what it gathered and paid out (or is about to) — newest "
            "first, with status, transfer date, total and the bank account's last digits."
        ),
        read_only=True,
        flags=(
            flag("days", type=int, minimum=1, maximum=180, default=90, help="Groups started in the last N days."),
            flag("limit", type=int, minimum=1, maximum=100, default=20, help="Max payouts to return."),
        ),
    ),
    Cmd(
        "order",
        "GET",
        "/agent/amazon/stores/{store_id}/finances/orders/{order_id}",
        summary=(
            "What one Amazon order brought in and what Amazon took: charges (Principal, Tax, "
            "ShippingCharge…), fees (Commission, FBA fees… negative = taken), tax Amazon kept as the "
            "marketplace facilitator, seller-funded promotions and refunds, summed per type, plus the "
            "net. order_id is SellerClaw's order id from `orders list`, or the Amazon order number "
            "(123-1234567-1234567)."
        ),
        read_only=True,
    ),
)

app = build_group(NAME, "Amazon money: posted transactions summed, payouts, one order's fees.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
