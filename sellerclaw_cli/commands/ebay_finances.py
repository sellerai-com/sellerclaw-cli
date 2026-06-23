from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "ebay-finances"

SPECS = (
    Cmd(
        "summary",
        "GET",
        "/agent/ebay/stores/{store_id}/finances/summary",
        summary=(
            "eBay money in/out and total fees over a trailing window (Finances API). eBay is "
            "authoritative on fees, so combine 'total_fees' with the store's revenue and cost "
            "of goods to compute true net profit for the period."
        ),
        flags=(
            flag("days", type=int, param="days", minimum=1, maximum=365, default=30, help="Trailing window in days."),
        ),
    ),
    Cmd(
        "funds",
        "GET",
        "/agent/ebay/stores/{store_id}/finances/funds",
        summary=(
            "Current eBay funds: available, on hold, processing. 'money_stuck' = on hold + "
            "processing (cash the seller can't access yet)."
        ),
    ),
    Cmd(
        "payouts",
        "GET",
        "/agent/ebay/stores/{store_id}/finances/payouts",
        summary="eBay payouts in a trailing window plus their total — the cash actually paid out.",
        flags=(
            flag("days", type=int, param="days", minimum=1, maximum=365, default=30, help="Trailing window in days."),
            flag("limit", type=int, param="limit", minimum=1, maximum=200, default=50, help="Max payouts to return."),
        ),
    ),
    Cmd(
        "pnl",
        "GET",
        "/agent/ebay/stores/{store_id}/finances/pnl",
        summary=(
            "eBay profit-and-loss waterfall for a trailing window (Finances transaction feed): "
            "gross sales minus fees (final value incl. fixed per-order, Promoted ads, "
            "international, regulatory), shipping labels, store subscription and returns = "
            "'net_proceeds' (BEFORE cost of goods). Returns 'fees' broken down by category, "
            "returns amount/count/'return_rate', and 'truncated' if the window was too large to "
            "read fully. For TRUE net profit, subtract cost of goods from 'analytics metrics' "
            "(cogs); this command never crosses into analytics. For month-over-month, call it "
            "twice (current vs prior equal window) and diff."
        ),
        flags=(
            flag("days", type=int, param="days", minimum=1, maximum=365, default=30, help="Trailing window in days."),
        ),
    ),
    Cmd(
        "cashflow",
        "GET",
        "/agent/ebay/stores/{store_id}/finances/cashflow",
        summary=(
            "eBay cash inflow only (no costs): 'received_last_week', 'expected_this_week' "
            "(scheduled/in-process payouts), 'on_hold', plus a Monday-aligned weekly inflow "
            "series ('weeks') and the payouts list. Use for the cash-flow report."
        ),
        flags=(
            flag("weeks", type=int, param="weeks", minimum=1, maximum=52, default=6, help="How many weeks the inflow series spans."),
        ),
    ),
)

app = build_group(NAME, "eBay finances (read-only): fees, payouts, funds on hold.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
