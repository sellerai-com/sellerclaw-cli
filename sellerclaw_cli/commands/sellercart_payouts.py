from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "sellercart-payouts"

SPECS = (
    Cmd(
        "status",
        "GET",
        "/agent/sellercart/payouts",
        summary=(
            "Whether the shop can take money yet, and what is still missing: Stripe connected, "
            "charges cleared, delivery answered. A shop that cannot take orders is a browsable "
            "catalog — check this before telling the seller they are open for business."
        ),
    ),
    Cmd(
        "connect",
        "POST",
        "/agent/sellercart/payouts/connect",
        summary=(
            "The Stripe onboarding link to give the seller. They finish it themselves — identity "
            "verification is theirs to do and cannot be done for them. Call `refresh` afterwards."
        ),
        body=(
            body_field(
                "country",
                required=True,
                help=(
                    "Two-letter country the Stripe account is opened in. Ask the seller — required "
                    "here on purpose: the API would otherwise default to US, and a German seller "
                    "handed a US account has to start over rather than correct it."
                ),
                example="US",
            ),
        ),
    ),
    Cmd(
        "refresh",
        "POST",
        "/agent/sellercart/payouts/refresh",
        summary="Re-read Stripe's verdict on the seller. Use after they say they finished onboarding.",
    ),
    Cmd(
        "delivery",
        "PUT",
        "/agent/sellercart/payouts/delivery",
        summary=(
            "What delivery costs and where the shop ships. Both are required before checkout opens at "
            "all — an unanswered delivery price is not the same as free."
        ),
        body=(
            body_field(
                "shipping_amount",
                type=float,
                required=True,
                help="Delivery charge per order, in the shop's currency. 0 means free — say it on purpose.",
                example=5.99,
            ),
            body_field(
                "shipping_countries",
                type=list,
                required=True,
                help="Two-letter country codes the shop ships to (1-50).",
                example=["US", "CA"],
            ),
        ),
    ),
    Cmd(
        "tax",
        "PUT",
        "/agent/sellercart/payouts/tax",
        summary=(
            "Turn Stripe Tax on for this shop. Only once the seller is tax-registered in their own "
            "Stripe account — switching it on before that makes checkout fail, not comply."
        ),
        body=(
            body_field(
                "enabled",
                type=bool,
                required=True,
                help="Whether Stripe Tax is applied at checkout.",
                example=True,
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Getting the storefront paid: Stripe onboarding, delivery terms, tax.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
