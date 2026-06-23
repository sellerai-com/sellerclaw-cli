from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "suppliers"

SPECS = (
    Cmd(
        "list-accounts",
        "GET",
        "/agent/supplier-accounts",
        summary="List the owner's connected supplier accounts.",
    ),
    Cmd(
        "resolve-url",
        "GET",
        "/agent/suppliers/resolve-url",
        summary="Resolve a public supplier product URL to {provider, product_id}.",
        flags=(flag("url", required=True, help="Public supplier product URL."),),
    ),
    Cmd(
        "search-products",
        "GET",
        "/agent/suppliers/{provider}/products",
        summary="Search a supplier's catalog.",
        flags=(
            flag("query", required=True, help="Search text."),
            flag("page", type=int, help="Page number."),
            flag("page_size", type=int, help="Results per page."),
        ),
    ),
    Cmd(
        "get-product",
        "GET",
        "/agent/suppliers/{provider}/products/{product_id}",
        summary="Get one supplier product.",
    ),
    Cmd(
        "get-variants",
        "GET",
        "/agent/suppliers/{provider}/products/{product_id}/variants",
        summary="List a supplier product's variants.",
    ),
    Cmd(
        "inspect",
        "GET",
        "/agent/suppliers/{provider}/products/{product_id}/inspect",
        summary=(
            "One-shot product card: get-product + variants "
            "+ optional shipping quote. Prefer this over chaining the individual commands."
        ),
        flags=(
            flag("country", help="ISO-3166 alpha-2; if set, a shipping quote is included."),
            flag("zip", help="Postal code; required when --country is set."),
            flag("max_variants", type=int, help="Cap variants returned (default 20)."),
            flag("shipping_method", help="Pin a shipping method; otherwise the provider's default."),
        ),
    ),
    Cmd(
        "check-stock",
        "GET",
        "/agent/suppliers/{provider}/stock/{variant_id}",
        summary="Check stock for a supplier variant.",
    ),
    Cmd(
        "check-stock-batch",
        "POST",
        "/agent/suppliers/{provider}/stock/batch",
        summary=(
            "Check stock for many variants in one call (body: "
            "{\"variant_ids\":[\"…\",\"…\"]})."
        ),
        body=(
            body_field(
                "variant_ids",
                type=str,
                repeatable=True,
                required=True,
                help="Supplier variant ids to check (1-200).",
            ),
        ),
    ),
    Cmd(
        "calculate-shipping",
        "POST",
        "/agent/suppliers/{provider}/shipping/calculate",
        summary="Calculate shipping cost for a supplier order.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Lines to ship: array of {variant_id*, quantity*, shipping_method*}.",
            ),
            body_field(
                "shipping_address",
                type=dict,
                required=True,
                help=(
                    "Destination: {country_code*, province*, city*, zip_code*, "
                    "address_line*, full_name*, phone*}."
                ),
            ),
            body_field("pay_type", type=int, help="Supplier pay type (1-3, default 2)."),
            body_field(
                "internal_order_id",
                help="SellerClaw order this fulfills (UUID); makes the call idempotent.",
            ),
        ),
    ),
    Cmd(
        "get-balance",
        "GET",
        "/agent/suppliers/{provider}/balance",
        summary="Get the supplier account balance.",
    ),
    Cmd(
        "create-order",
        "POST",
        "/agent/suppliers/{provider}/orders",
        summary="Place a dropship purchase order with the supplier.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Lines to order: array of {variant_id*, quantity*, shipping_method*}.",
            ),
            body_field(
                "shipping_address",
                type=dict,
                required=True,
                help=(
                    "Destination: {country_code*, province*, city*, zip_code*, "
                    "address_line*, full_name*, phone*}."
                ),
            ),
            body_field("pay_type", type=int, help="Supplier pay type (1-3, default 2)."),
            body_field(
                "internal_order_id",
                help="SellerClaw order this fulfills (UUID); makes the call idempotent.",
            ),
        ),
    ),
    Cmd(
        "get-order",
        "GET",
        "/agent/suppliers/{provider}/orders/{order_id}",
        summary="Get one supplier order.",
    ),
    Cmd(
        "confirm-order",
        "POST",
        "/agent/suppliers/{provider}/orders/{order_id}/confirm",
        summary="Confirm a supplier order.",
    ),
    Cmd(
        "pay-order",
        "POST",
        "/agent/suppliers/{provider}/orders/{order_id}/pay",
        summary="Pay for a supplier order.",
    ),
    Cmd(
        "get-tracking",
        "GET",
        "/agent/suppliers/{provider}/orders/{order_id}/tracking",
        summary="Get tracking for a supplier order.",
    ),
)

app = build_group(
    NAME,
    "Supplier accounts, catalog search, and dropship orders (provider is the first argument).",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
