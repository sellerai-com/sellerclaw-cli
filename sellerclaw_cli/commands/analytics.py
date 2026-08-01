from __future__ import annotations

import typer

from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS, Cmd, build_group, flag

NAME = "analytics"

# Every read in this group takes the same window and the same store selection, so a caller learns
# the contract once instead of a dialect per command. Declared here and spread into each Cmd, which
# also means `describe` shows them identically everywhere.

PERIOD_CHOICES = (
    "last_7d",
    "last_30d",
    "last_90d",
    "this_month",
    "last_month",
    "this_year",
)

WINDOW_FLAGS = (
    flag(
        "period",
        help="Window ending now.",
        choices=PERIOD_CHOICES,
        default="last_30d",
    ),
    flag(
        "week",
        type=int,
        minimum=0,
        maximum=52,
        help=(
            "A COMPLETED ISO week instead of --period: 0 = last week (the most recent finished "
            "one, never the week in progress), 1 = the week before it. Use for 'how was last week'."
        ),
    ),
    flag(
        "month",
        type=int,
        minimum=0,
        maximum=24,
        help=(
            "A COMPLETED calendar month instead of --period: 0 = last month, 1 = the month before. "
            "Use for 'compare March with February' (two calls, --month 4 and --month 5)."
        ),
    ),
    flag(
        "date_from",
        param="from",
        aliases=("--from",),
        help="Start of an explicit range, YYYY-MM-DD (inclusive). Needs --to.",
    ),
    flag(
        "date_to",
        param="to",
        aliases=("--to",),
        help="End of an explicit range, YYYY-MM-DD (inclusive whole day). Needs --from.",
    ),
)

STORE_FLAGS = (
    flag(
        "store",
        repeatable=True,
        help=(
            "Another store to fold into the same answer; repeat to add more. The server recomputes "
            "over the combined data, so never add up two single-store answers yourself."
        ),
    ),
)

# Reused in several summaries: the two things that make an answer honest.
_SELECTION = (
    "Pass `all` instead of a store id to cover every active store, or repeat --store to pick "
    "several. Averages, shares and rankings are recomputed over the combined data."
)
_COVERAGE = (
    "Every answer carries `coverage`: which `store_ids` it covers, `history_status` "
    "(ready / syncing / unavailable) and `history_covered_from`. `syncing` means the store is "
    "still importing its sales history — say so instead of reporting the figures as complete."
)

SPECS = (
    Cmd(
        "metrics",
        "GET",
        "/agent/analytics/stores/{store_id}/metrics",
        summary=(
            "Sales and profit for a window, computed inline: revenue, orders, AOV, trend vs the "
            "previous equal window, gross profit and margin, ABC tiers by revenue and by profit, "
            "sales mix by category, top SKUs by revenue and by profit, sleeping (listed but unsold) "
            "SKUs. The default money command — use it for 'how are sales', 'top sellers', 'what's "
            "my margin'. Period: --period, or --week/--month for a completed week/month, or "
            "--from/--to for an explicit range. "
            f"{_SELECTION} Profit is GROSS (cost of goods only); add --with-fees for profit after "
            "the marketplace's cut. `cost_coverage_pct` is the share of revenue with a known cost — "
            "cost exists only for supplier-sourced products, so frame a low value as 'profit on "
            f"sourced products', not whole-store. {_COVERAGE}"
        ),
        flags=(
            *WINDOW_FLAGS,
            *STORE_FLAGS,
            flag(
                "top",
                type=int,
                param="top",
                minimum=1,
                maximum=50,
                default=10,
                help="How many top SKUs to return, by revenue and by profit.",
            ),
            flag(
                "with_fees",
                type=bool,
                help=(
                    "Also read what the marketplace charged (eBay/Shopify/Etsy) and add a `net` "
                    "block: marketplace_fees, net_profit, net_margin_pct, sources. SLOW — a live "
                    "call per store. The block is absent when any selected store's fees cannot be "
                    "read (e.g. Amazon) or the stores bill in different currencies."
                ),
            ),
            flag(
                "fresh",
                type=bool,
                help="Bypass the local mirror and fetch live from the store (slower).",
            ),
        ),
        # A fee read goes out to each platform's finance API and pages through transactions.
        timeout=LONG_TIMEOUT_SECONDS,
    ),
    Cmd(
        "timeseries",
        "GET",
        "/agent/analytics/stores/{store_id}/timeseries",
        summary=(
            "Revenue, orders and units bucketed over time — the data behind a trend chart. The "
            "window says WHICH span to chart and --granularity how finely to cut it: `--month 0 "
            "--granularity day` charts last month day by day. --buckets overrides the count when "
            "you want a fixed number of periods instead ('the last 12 months' = --granularity "
            "month --buckets 12). Buckets are calendar-aligned, oldest first; each has "
            f"period_start/period_end, revenue, order_count, units. {_SELECTION} {_COVERAGE}"
        ),
        flags=(
            *WINDOW_FLAGS,
            *STORE_FLAGS,
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
                help="Fixed number of buckets ending at the window's end. Omit to cover the window.",
            ),
            flag(
                "fresh",
                type=bool,
                help="Bypass the local mirror and fetch live from the store (slower).",
            ),
        ),
    ),
    Cmd(
        "inventory",
        "GET",
        "/agent/analytics/stores/{store_id}/inventory",
        summary=(
            "Stock health: what is (about to be) out of stock while still listed, and what to "
            "reorder. Joins current stock with sales velocity over the window. Returns `stockouts` "
            "(costliest first — each with current_stock, daily_velocity, days_of_cover, "
            "lost_revenue_per_day, is_out_of_stock) plus out_of_stock_count and "
            "total_lost_revenue_per_day; and `reorders` (most urgent first — days_of_cover, "
            "reorder_point, suggested_order_qty, needs_reorder) plus reorder_count. "
            "`lead_time_is_default` = true means the owner has not set a restock lead time (set it "
            "with `channels set-lead-time`) — or several stores were combined, which have no single "
            "one. In-transit stock is not modelled: the math is on-hand only. Use for 'what's out "
            "of stock', 'what do I need to reorder', 'am I about to sell out'. "
            f"{_SELECTION} {_COVERAGE}"
        ),
        flags=(
            *WINDOW_FLAGS,
            *STORE_FLAGS,
            flag(
                "top",
                type=int,
                param="top",
                minimum=1,
                maximum=100,
                default=20,
                help="How many rows to return per facet (stockouts / reorders).",
            ),
        ),
    ),
    Cmd(
        "geography",
        "GET",
        "/agent/analytics/stores/{store_id}/geography",
        summary=(
            "Where the orders went over the window: `countries` (each with order_count, "
            "order_share 0..1 and share_delta_pp — the shift vs the previous equal window), the "
            "`primary_country`, and its `primary_country_regions` (e.g. US states). Use for 'where "
            "are my buyers', and to advise on shipping policies, fulfillment placement and where "
            f"to advertise. {_SELECTION} {_COVERAGE}"
        ),
        flags=(*WINDOW_FLAGS, *STORE_FLAGS),
    ),
    Cmd(
        "capital",
        "GET",
        "/agent/analytics/stores/{store_id}/capital",
        summary=(
            "Money sitting in stock on hand: `tied_up_value`, and `dead_stock_value` — the slice "
            "that has not sold in --dead-after days. Use for 'how much cash is tied up in "
            "inventory', 'what should I discount or write off'. Takes NO period: stock is always as "
            "of now (no stock history is kept). Stock is valued at supplier cost, which exists only "
            "for sourced products, so `coverage_pct` (0..1) is the share of on-hand units the money "
            "figures actually cover — a low value means the real number is bigger than the one "
            f"shown, and must be said out loud. {_SELECTION} {_COVERAGE}"
        ),
        flags=(
            *STORE_FLAGS,
            flag(
                "dead_after",
                type=int,
                param="dead_after",
                minimum=1,
                maximum=365,
                default=90,
                help="Days without a sale after which in-stock items count as dead stock.",
            ),
        ),
    ),
    Cmd(
        "operations-digest",
        "GET",
        "/agent/stores/{store_id}/operations-digest",
        summary=(
            "One morning operations briefing for a store — what needs attention today, across "
            "every platform. Universal blocks (all stores): `orders` (orders awaiting shipment — "
            "`awaiting_count` + the oldest `top_oldest` at risk of a late ship) and `inventory` "
            "(sold-out-but-listed `top_stockouts` with `total_lost_revenue_per_day`, plus "
            "`top_reorders` with `reorder_count`). Enrichment blocks — filled only where the "
            "marketplace exposes them (eBay today): `shipping` (in-transit/overdue parcels + "
            "tracking links), `disputes` (open returns/disputes with deadlines and "
            "`amount_at_risk`), `account_health` (seller level + the metric nearest its "
            "threshold). Each block has `available` (false = the platform has no such concept, "
            "not an error) and `error` (set when a supported block failed to load). Lead with "
            "`headline` — `orders_to_ship`, `shipments_overdue`, `disputes_open`, `out_of_stock`, "
            "`reorders_due`, `account_at_risk`, `attention_count`, `has_errors`. Use for 'what "
            "needs my attention today', 'morning check', 'anything urgent on this store'. This one "
            "is always about NOW and one store at a time, so it takes no window and no --store."
        ),
        flags=(
            flag(
                "velocity_period",
                help="Velocity window for the inventory block (how far back sales are measured).",
                choices=PERIOD_CHOICES,
                default="last_30d",
            ),
        ),
    ),
    Cmd(
        "report",
        "POST",
        "/agent/analytics/stores/{store_id}/report",
        summary=(
            "DELIVERY, not data: queues a narrated sales report for one store and returns "
            "immediately — the figures arrive back to you later as a separate message, to relay to "
            "the owner. Use when the owner asked for a report. When YOU need numbers to finish a "
            "task, use `metrics` instead, which returns them in the response."
        ),
        flags=(
            flag(
                "period",
                help="Reporting window.",
                choices=PERIOD_CHOICES,
                default="last_30d",
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Store sales analytics (read-only): sales, trends, stock, geography, tied-up capital.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
