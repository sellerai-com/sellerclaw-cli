from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "shopify-finances"

SPECS = (
    Cmd(
        "pnl",
        "GET",
        "/agent/stores/{store_id}/finances/pnl",
        summary=(
            "Shopify Payments profit-and-loss for a trailing window: card-processed gross sales "
            "minus processing fees, refunds, disputes and adjustments = 'net_proceeds' (BEFORE "
            "cost of goods). Returns 'fees' (processing + other), refunds amount/count, and "
            "'truncated' if the window was too large to read fully. If 'available' is false the "
            "store has no Shopify Payments data — say so, don't invent numbers. 'gross_sales' is "
            "card-processed only (not total store revenue — use 'analytics metrics' for that); "
            "for TRUE net profit subtract cost of goods from 'analytics metrics' (cogs). For "
            "month-over-month, call it twice (current vs prior equal window) and diff."
        ),
        flags=(
            flag("days", type=int, param="days", minimum=1, maximum=365, default=30, help="Trailing window in days."),
        ),
    ),
    Cmd(
        "cashflow",
        "GET",
        "/agent/stores/{store_id}/finances/cashflow",
        summary=(
            "Shopify Payments cash inflow only (no costs): 'received_last_week', "
            "'expected_this_week' (scheduled/in-transit payouts), 'on_hold' (balance awaiting "
            "the next payout), plus a Monday-aligned weekly inflow series ('weeks') and the "
            "payouts list. If 'available' is false the store has no Shopify Payments data."
        ),
        flags=(
            flag("weeks", type=int, param="weeks", minimum=1, maximum=52, default=6, help="How many weeks the inflow series spans."),
        ),
    ),
)

app = build_group(NAME, "Shopify Payments finances (read-only): P&L and cash flow.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
