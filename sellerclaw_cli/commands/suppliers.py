from __future__ import annotations

import typer

from sellerclaw_cli._command_group import (
    LONG_TIMEOUT_SECONDS,
    Cmd,
    body_field,
    build_group,
    flag,
)

NAME = "suppliers"

SPECS = (
    Cmd(
        "list-accounts",
        "GET",
        "/agent/supplier-accounts",
        summary="List the owner's connected supplier accounts.",
    ),
    Cmd(
        "create-account",
        "POST",
        "/agent/supplier-accounts/offline",
        summary=(
            "Add a supplier with no integration behind it — the owner's own, named by them. "
            "Nothing is authorized and no key is handed over: the row is a name to hang costs, "
            "stock, lead times and a contact on, and its id is what a catalog product "
            "(`catalog set-supplier`) and a price-list upload point at. Names are unique per "
            "owner. For CJ and other integrations use their own connect flow instead."
        ),
        body=(
            body_field(
                "name",
                required=True,
                help="What the owner calls this supplier. Unique among their own suppliers.",
                example="Nest Supply Co.",
            ),
            body_field(
                "currency",
                help="ISO-4217 code this supplier's costs are stated in, e.g. USD.",
                example="USD",
            ),
            body_field(
                "contact",
                help="How to reach them — email, phone, or a note. Free text.",
                example="orders@nestsupply.example.com",
            ),
            body_field(
                "lead_time_days",
                type=int,
                help=(
                    "Days from ordering to the goods arriving, as this supplier's standing figure. "
                    "Leave it out when they never said — a guessed lead time becomes a guessed "
                    "delivery promise on a storefront."
                ),
                example=7,
            ),
            body_field(
                "min_order_qty",
                type=int,
                help="Fewest units they accept on one order. Leave out when unstated.",
                example=20,
            ),
            body_field(
                "website_url",
                help="The supplier's own site, if they have one. Must start with https://.",
                example="https://nestsupply.example.com",
            ),
        ),
    ),
    Cmd(
        "update-account",
        "PATCH",
        "/agent/supplier-accounts/offline/{supplier_id}",
        summary=(
            "Correct what is recorded about one of the owner's own suppliers. An omitted field "
            "keeps its value; null clears currency or contact. The name cannot be cleared — it is "
            "the supplier's identity."
        ),
        body=(
            body_field("name", help="New name. Must stay unique among the owner's suppliers."),
            body_field(
                "currency",
                nullable=True,
                clearable=True,
                help="ISO-4217 code, or null to stop stating one.",
            ),
            body_field(
                "contact",
                nullable=True,
                clearable=True,
                help="Email, phone or note, or null to stop stating one.",
            ),
            body_field(
                "lead_time_days",
                type=int,
                nullable=True,
                clearable=True,
                help="Standing lead time in days, or null to stop stating one.",
            ),
            body_field(
                "min_order_qty",
                type=int,
                nullable=True,
                clearable=True,
                help="Minimum order in units, or null to stop stating one.",
            ),
            body_field(
                "website_url",
                nullable=True,
                clearable=True,
                help="The supplier's site (https://…), or null to stop stating one.",
            ),
        ),
    ),
    Cmd(
        "delete-account",
        "DELETE",
        "/agent/supplier-accounts/offline/{supplier_id}",
        summary=(
            "Remove one of the owner's own suppliers. Refused while catalog products still point "
            "at it, and the refusal carries their number so the owner decides. "
            "--unlink-products is that answer: the products stay in the catalog with no supplier "
            "behind them."
        ),
        flags=(
            flag(
                "unlink_products",
                type=bool,
                help=(
                    "Detach the catalog products first instead of refusing. They keep selling; "
                    "they just stop being this supplier's goods."
                ),
            ),
        ),
    ),
    Cmd(
        "resolve-url",
        "GET",
        "/agent/suppliers/resolve-url",
        summary="Resolve a public supplier product URL to {provider, product_id}.",
        flags=(flag("url", required=True, help="Public supplier product URL."),),
    ),
    Cmd(
        "categories",
        "GET",
        "/agent/suppliers/{provider}/categories",
        summary="Browse or search the supplier's own category tree (ids for --category).",
        flags=(
            flag(
                "search",
                help=(
                    "Find every category whose breadcrumb contains this text, at any depth — the "
                    "quickest way to the id for 'belts'."
                ),
            ),
            flag(
                "parent",
                help=(
                    "List the children of this category (its name, breadcrumb or id). Omit both "
                    "flags for the top level."
                ),
            ),
            flag(
                "limit",
                type=int,
                minimum=1,
                maximum=500,
                default=50,
                help="Most categories to return; the reply's `total` says how many matched.",
            ),
        ),
    ),
    Cmd(
        "search-products",
        "GET",
        "/agent/suppliers/{provider}/products",
        summary="Search a supplier's catalog by keyword and/or category, with warehouse / price / sort filters.",
        flags=(
            flag(
                "query",
                help=(
                    "Search text. Optional when --category is given: that browses the whole "
                    "category, which is how you ask for a kind of product rather than for a word "
                    "that happens to be in its name."
                ),
            ),
            flag(
                "category",
                param="category_id",
                help=(
                    "Only products in this category of the supplier's own tree. Get the id from "
                    "`suppliers categories <provider> --search <text>`."
                ),
            ),
            flag("page", type=int, help="Page number."),
            flag("page_size", type=int, help="Results per page."),
            flag(
                "stocked_in",
                help=(
                    "Only products already held in a warehouse in this country (ISO alpha-2, e.g. "
                    "US) — where the goods SIT, not where they are going. A hard filter: most "
                    "dropship goods ship from China and are dropped by it, so search without it "
                    "first and add it once there is something to narrow."
                ),
            ),
            flag(
                "verified_only",
                type=bool,
                help="Only products with verified warehouse inventory.",
            ),
            flag("min_price", type=float, help="Minimum supplier sell price."),
            flag("max_price", type=float, help="Maximum supplier sell price."),
            flag("sort", help="Provider sort key (e.g. price)."),
            flag("order_by", help="Sort direction (asc / desc)."),
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
            "One-shot card for ONE product: details + variants + real per-warehouse stock + "
            "optional shipping quote. Stock comes with it, so no check-stock call afterwards. "
            "For several products at once use inspect-batch."
        ),
        flags=(
            flag(
                "to_country",
                help=(
                    "Where the goods would ship TO (ISO-3166 alpha-2); set it and a shipping "
                    "quote is included. A destination, never a warehouse filter."
                ),
            ),
            flag("to_zip", help="Destination postal code; required with --to-country."),
            flag("max_variants", type=int, help="Cap variants returned (default 20)."),
        ),
    ),
    Cmd(
        "inspect-batch",
        "POST",
        "/agent/suppliers/{provider}/products/inspect-batch",
        summary=(
            "Read a WHOLE shortlist in one call: price, per-warehouse stock and shipping for up "
            "to 20 products. Prefer this over looping inspect / check-stock-by-product per "
            "product. Descriptions and variant lists are omitted unless the body's include field "
            "asks for them."
        ),
        # Up to 20 products x ~4 rate-limited supplier calls: minutes are possible, so this gets
        # the long client timeout rather than the 30s default.
        timeout=LONG_TIMEOUT_SECONDS,
        body=(
            body_field(
                "product_ids",
                type=str,
                repeatable=True,
                required=True,
                help="Supplier product ids to read (1-20).",
            ),
            body_field(
                "destination",
                type=dict,
                help=(
                    "Where the goods would ship to: {country_code*, zip_code*}. Omit to skip "
                    "shipping entirely."
                ),
                example={"country_code": "US", "zip_code": "90001"},
            ),
            body_field(
                "quantity",
                type=int,
                help="Units per product to quote shipping for (default 1).",
            ),
            body_field(
                "max_variants",
                type=int,
                help="Cap variants counted per product (default 5); the real total is reported.",
            ),
            body_field(
                "include",
                type=str,
                repeatable=True,
                help=(
                    "Heavy fields to add per product: description, attributes, variants. "
                    "All omitted by default."
                ),
            ),
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
        "check-stock-by-product",
        "GET",
        "/agent/suppliers/{provider}/stock/product/{product_id}",
        summary=(
            "Stock for ALL variants of a product in ONE call, split per warehouse (each variant's "
            "`warehouses` lists the country/area and shippable quantity). Prefer this over looping "
            "check-stock / check-stock-batch per variant when you have the product id."
        ),
    ),
    Cmd(
        "quote-shipping",
        "POST",
        "/agent/suppliers/{provider}/shipping/quote",
        summary=(
            "Quote shipping to a region from country + zip only — the cheapest in-stock warehouse "
            "wins (not always China). Use this for a quick 'what would shipping cost to X' check; "
            "use calculate-shipping once the full delivery address is known. Answers "
            "{quotes, unavailable}: no method on offer is an answer, not an empty result."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                required=True,
                help="Lines to quote: array of {variant_id*, quantity*}.",
            ),
            body_field(
                "destination",
                type=dict,
                required=True,
                help="Where to: {country_code*, zip_code*}.",
                example={"country_code": "US", "zip_code": "10001"},
            ),
        ),
    ),
    Cmd(
        "calculate-shipping",
        "POST",
        "/agent/suppliers/{provider}/shipping/calculate",
        summary=(
            "Quote shipping to a full delivery address. The cheapest in-stock warehouse is chosen "
            "automatically; pass from_country_code to pin a specific origin. Answers "
            "{quotes, unavailable} — a shipment the supplier will not price says so, with a "
            "retryable flag, instead of coming back empty."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Lines to ship: array of {variant_id*, quantity*}.",
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
            body_field(
                "from_country_code",
                help=(
                    "Ship-from country (ISO alpha-2) — pins the origin warehouse; omit to "
                    "auto-pick the cheapest in-stock warehouse."
                ),
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
        summary=(
            "Place a dropship purchase order with the supplier. The cheapest in-stock warehouse "
            "nearest the buyer is chosen automatically; pass from_country_code to pin an origin."
        ),
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
            body_field(
                "from_country_code",
                help=(
                    "Ship-from country (ISO alpha-2) — pins the origin warehouse; omit to "
                    "auto-pick the cheapest in-stock warehouse nearest the buyer."
                ),
            ),
            body_field(
                "pay_type",
                type=int,
                help=(
                    "How the purchase gets paid for. OMIT IT and SellerClaw decides from the "
                    "supplier wallet: enough to cover the estimate -> created unpaid, then paid "
                    "from the wallet once the real total is checked against the approved cost; "
                    "not enough, unreadable, or a currency that cannot be compared -> the reply "
                    "carries `pay_url`, a payment page for the owner, and nothing is charged. "
                    "Pin it only to override that: 2 charges the wallet on creation, before any "
                    "such check."
                ),
            ),
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
