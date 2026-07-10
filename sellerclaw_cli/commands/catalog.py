from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "catalog"

SPECS = (
    Cmd(
        "overview",
        "GET",
        "/agent/products/overview",
        summary="Catalog summary: total products, counts by status, out-of-stock count.",
    ),
    Cmd(
        "list",
        "GET",
        "/agent/products",
        summary="List catalog products.",
        flags=(
            flag("status", help="Filter by status (sourced, active, archived)."),
            flag("supplier_provider", help="Filter by supplier provider code."),
        ),
    ),
    Cmd("get", "GET", "/agent/products/{product_id}", summary="Get one product by id."),
    Cmd(
        "search",
        "GET",
        "/agent/products",
        summary=(
            "Find catalog products by name or SKU (case-insensitive substring). Returns the "
            "matching products, each with its id for a 'get' follow-up."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of the name or any variation SKU)."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
            flag("status", help="Also filter by status (sourced, active, archived)."),
        ),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/products",
        summary="Create products (batch; the body accepts an array of products).",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                required=True,
                help=(
                    "Array of products to create. Each item: name*, description*, category*, "
                    "variations* (array of {supplier_variant_id, sku, name, available_quantity, "
                    "shipping_cost, purchase_price?, images?, attributes?}), and "
                    "optional images. Supplier binding (supplier_id, supplier_product_id, "
                    "supplier_provider) must be all set together or all omitted."
                ),
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/products/{product_id}",
        summary="Update product metadata (name, description, images, category, status).",
        body=(
            body_field("name", help="New product name."),
            body_field("description", help="New product description."),
            body_field("images", type=str, repeatable=True, help="Replacement list of image URLs."),
            body_field("category", help="New category (breadcrumb string, e.g. 'A > B > C')."),
            body_field(
                "status",
                choices=("sourced", "active", "archived"),
                help="New catalog status.",
            ),
        ),
    ),
    Cmd(
        "set-prices",
        "PATCH",
        "/agent/products/{product_id}/prices",
        summary=(
            "Set the purchase price (supplier cost). Body: {\"purchase_price\": 9.50} applies to "
            "all variations; {\"variations\": [{\"supplier_variant_id\": ..., \"purchase_price\": ...}]} "
            "targets each. The buyer-facing sell price is derived at publish time as cost x "
            "channel markup, not set here."
        ),
        body=(
            body_field(
                "purchase_price",
                type=float,
                help="Broadcast purchase price (supplier cost) applied to every variation.",
            ),
            body_field(
                "variations",
                type=dict,
                repeatable=True,
                help=(
                    "Per-variation prices: array of {supplier_variant_id*, purchase_price?}. "
                    "Mutually exclusive with the broadcast price above."
                ),
            ),
        ),
    ),
    Cmd("delete", "DELETE", "/agent/products/{product_id}", summary="Delete a product."),
    Cmd(
        "source-from-supplier",
        "POST",
        "/agent/products/source-from-supplier",
        summary="Add one supplier product to the catalog (3 supplier calls, any variant count).",
        body=(
            body_field("supplier_provider", required=True, help="Provider slug, e.g. 'cj'."),
            body_field("supplier_product_id", required=True, help="Supplier-side product id."),
            body_field(
                "destination",
                type=dict,
                required=True,
                help="Where it ships: {country_code* (ISO-3166 alpha-2), zip_code*}.",
            ),
            body_field(
                "max_variants",
                type=int,
                help="Cap variants imported (default 500, 1-2000).",
            ),
        ),
    ),
)

app = build_group(NAME, "Internal SellerClaw product catalog.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
