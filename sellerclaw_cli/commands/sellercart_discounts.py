from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sellercart-discounts"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/discounts",
        summary=(
            "The shop's discounts running and scheduled: each one's id, target and target_name, "
            "percent, starts_at / ends_at, status (scheduled, active, ended) and 'products' — how "
            "many products sell at it now, or from its start. 0 means a narrower discount decides "
            "those prices; null, on a shop or category discount, that the shop is too big to "
            "count; target_missing means its product is gone from the shop. Read it before "
            "changing a discount."
        ),
        flags=(
            flag(
                "include_ended",
                type=bool,
                help="Also the discounts that ended in the last 30 days.",
            ),
        ),
    ),
    Cmd(
        "set",
        "POST",
        "/agent/sellercart/discounts",
        summary=(
            "Run a discount — a whole percent off the regular price, for a period — or change the "
            "one 'id' names (fields left out keep their value). One command for every target: "
            "'shop'; 'category' with the shop's category name; 'product' with the listing_id from "
            "`sellercart-products list` (all its variants); 'variant' with one variation_id. The "
            "sale price is the regular price less the percent, rounded down to the tenth, and it "
            "follows the regular price as costs and markup move. Where several cover one variant "
            "the narrowest wins (variant > product > category > shop); of two of one kind, the one "
            "that started later. It applies from starts_at to ends_at with no publish and no "
            "approval. The answer says what it did: 'effect' (products covered, a sample of new "
            "prices), 'below_cost' — variants that now sell for less than they cost — and "
            "'warnings'. Tell the owner both; the discount stands."
        ),
        body=(
            body_field("id", help="The discount to change. Leave out to start a new one."),
            body_field(
                "target",
                choices=("shop", "category", "product", "variant"),
                help="What it covers. Required for a new discount.",
            ),
            body_field(
                "listing_id",
                help="target product: the listing's own id, from `sellercart-products list`.",
            ),
            body_field(
                "variation_id",
                help="target variant: the variation's own id, from `sellercart-products list`.",
            ),
            body_field(
                "category",
                help="target category: its name as the shop's categories spell it.",
                example="Mugs",
            ),
            body_field(
                "percent",
                type=int,
                help="Whole percent off, 1–99. Required for a new discount.",
                example=20,
            ),
            body_field(
                "starts_at",
                help=(
                    "When it starts, ISO 8601 with the owner's UTC offset. A new discount starts "
                    "now when left out."
                ),
                example="2026-11-27T00:00:00-05:00",
            ),
            body_field(
                "ends_at",
                help=(
                    "The first moment it no longer applies, ISO 8601 with the owner's UTC offset: "
                    "a sale until November 30 ends at 2026-12-01T00:00:00. Required for a new "
                    "discount."
                ),
                example="2026-12-01T00:00:00-05:00",
            ),
            body_field(
                "label",
                nullable=True,
                help="The owner's name for it, shown in their list — never to buyers. null drops it.",
                example="Black Friday",
            ),
        ),
    ),
    Cmd(
        "remove",
        "DELETE",
        "/agent/sellercart/discounts/{discount_id}",
        summary=(
            "Stop a discount. A running one ends now and stays in the list as one that ran "
            "(outcome 'stopped'); one not started yet, or already over, is deleted ('deleted')."
        ),
    ),
)

app = build_group(
    NAME,
    "Discounts on the seller's own storefront: a percentage off, on what, for how long.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
