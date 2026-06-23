from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "analytics"

SPECS = (
    Cmd(
        "report",
        "POST",
        "/agent/analytics/stores/{store_id}/report",
        summary=(
            "Queue a full sales-analytics report for one store (revenue, AOV, period-over-period "
            "trend, ABC tiers, best/worst sellers, sleeping catalog, recommendations). Returns "
            "immediately; the result is delivered to the chat when ready."
        ),
        flags=(
            flag(
                "period",
                help="Reporting window.",
                choices=("last_7d", "last_30d", "last_90d", "this_month", "this_year"),
                default="last_30d",
            ),
        ),
    ),
    Cmd(
        "metrics",
        "GET",
        "/agent/analytics/stores/{store_id}/metrics",
        summary=(
            "Compute store sales metrics inline (synchronous): revenue, AOV, period-over-period "
            "trend, ABC tiers, and the top SKUs by revenue with their % share. Use this when you "
            "need numbers to answer in-task (e.g. 'top sellers by revenue this month'); for a "
            "narrated report delivered to the chat, use 'report' instead. Reads the local "
            "sales-history mirror (fast); a store still importing its history (or --fresh) reads "
            "live, which can be slow on large catalogs — allow a generous timeout for that case."
        ),
        flags=(
            flag(
                "period",
                help="Reporting window.",
                choices=("last_7d", "last_30d", "last_90d", "this_month", "this_year"),
                default="last_30d",
            ),
            flag(
                "top",
                type=int,
                param="top",
                minimum=1,
                maximum=50,
                default=10,
                help="How many top SKUs by revenue to return.",
            ),
            flag(
                "fresh",
                type=bool,
                help="Bypass the local mirror and fetch live from the store (slower).",
            ),
        ),
    ),
    Cmd(
        "timeseries",
        "GET",
        "/agent/analytics/stores/{store_id}/timeseries",
        summary=(
            "Revenue and orders bucketed over time — the data behind the trend charts. Ask for "
            "'revenue by week, last 8 weeks' (--granularity week --buckets 8) or 'by month, last "
            "12 months' (--granularity month --buckets 12), independent of any report period. "
            "Buckets are calendar-aligned and the last one is the current, partial period."
        ),
        flags=(
            flag(
                "granularity",
                help="Bucket size.",
                choices=("day", "week", "month"),
                default="week",
            ),
            flag(
                "buckets",
                type=int,
                param="buckets",
                minimum=1,
                maximum=366,
                default=8,
                help="How many buckets ending now.",
            ),
            flag(
                "fresh",
                type=bool,
                help="Bypass the local mirror and fetch live from the store (slower).",
            ),
        ),
    ),
)

app = build_group(NAME, "Store sales analytics (read-only).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
