from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "channels"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sales-channels",
        summary="List connected sales channels (stores).",
        flags=(
            flag("platform", help="Filter by platform (shopify, ebay, ...)."),
            flag(
                "status",
                repeatable=True,
                help="Filter by status (active, credentials_invalid, ...); repeat for multiple.",
            ),
        ),
    ),
    Cmd(
        "get",
        "GET",
        "/agent/sales-channels/{sales_channel_id}",
        summary="Get one sales channel by id.",
    ),
    Cmd(
        "set-markup",
        "PATCH",
        "/agent/sales-channels/{sales_channel_id}",
        summary="Set this store's dropshipping markup (percent, e.g. 30 = +30%).",
        body=(
            body_field(
                "markup_percent",
                type=float,
                required=True,
                help=(
                    "Markup percent applied over the product cost when pricing listings "
                    "(0-500; 15 = +15%). A store starts with no markup set — until you set one, "
                    "new listings are created without a price and cannot be published."
                ),
                example=30,
            ),
        ),
    ),
    Cmd(
        "set-lead-time",
        "PATCH",
        "/agent/sales-channels/{sales_channel_id}",
        summary=(
            "Set this store's supplier restock lead time (days) — how long a reorder takes to "
            "arrive. Drives the reorder math in `analytics inventory`; unset stores fall back to a "
            "built-in default."
        ),
        body=(
            body_field(
                "reorder_lead_time_days",
                type=int,
                required=True,
                help="Days from placing a reorder to stock arriving (1-365).",
                example=14,
            ),
        ),
    ),
    Cmd(
        "set-default-policies",
        "PATCH",
        "/agent/sales-channels/{sales_channel_id}",
        summary=(
            "Pin the marketplace policy a draft should use when none is named — eBay and Etsy only. "
            "This is the owner's standing answer, so ask before setting it: different goods "
            "legitimately ship under different policies, and a one-off choice must not become the "
            "store's rule. Once pinned, drafts stop coming back with `needs_policies`. Keys are the "
            "platform's own (eBay: default_fulfillment_policy_id, default_payment_policy_id, "
            "default_return_policy_id; Etsy: default_shipping_profile_id, default_return_policy_id); "
            "an empty value removes the pin and the store goes back to asking. A key the store's "
            "marketplace does not have is refused, not stored. Read the current pins from "
            "`channels get` (`specifics`)."
        ),
        body=(
            body_field(
                "default_policies",
                type=dict,
                required=True,
                help="Policy ids keyed by the platform's own default_* key; empty value unpins.",
                example={"default_fulfillment_policy_id": "6001234567890"},
            ),
        ),
    ),
    Cmd(
        "set-target-market",
        "PATCH",
        "/agent/sales-channels/{sales_channel_id}",
        summary=(
            "Set the store's target market — the destination (ISO alpha-2, e.g. US) whose shipping "
            "is folded into the listing price. Pass an empty string to clear the override, so "
            "pricing falls back to the market inferred from the store's order history. Read the "
            "current value from `channels get` (`specifics.target_market`)."
        ),
        body=(
            body_field(
                "target_market",
                required=True,
                help="Destination country (ISO alpha-2); empty string clears the override.",
                example="US",
            ),
        ),
    ),
    Cmd(
        "set-shipping-in-price",
        "PATCH",
        "/agent/sales-channels/{sales_channel_id}",
        summary=(
            "Toggle whether shipping to the target market is bundled into the listing price "
            "(default on). Turn off when the store charges shipping separately on the platform."
        ),
        body=(
            body_field(
                "shipping_included_in_price",
                type=bool,
                required=True,
                help="true to fold shipping into the price, false to charge it separately.",
                example=True,
            ),
        ),
    ),
)

app = build_group(NAME, "Connected sales channels (stores).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
