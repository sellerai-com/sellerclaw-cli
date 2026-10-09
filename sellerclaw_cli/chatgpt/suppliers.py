"""Suppliers: finding and inspecting their products, stock and shipping, and dropship orders."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli._errors import CliError, UserInputError
from sellerclaw_cli.chatgpt._action import Param, action, execute, runs, split

_PROVIDER = Param("provider", "string", "The supplier, e.g. cj (see list_connections).", required=True, to="path")
_SUPPLIER_ORDER = Param(
    "supplier_order_id",
    "string",
    "The supplier's order id.",
    required=True,
    to="path",
    key="order_id",
)
_ADDRESS = Param(
    "shipping_address", "object",
    "Full address: {country_code, province, city, zip_code, address_line, full_name, phone}.",
)
_ITEMS = Param("items", "array", "Lines: each {variant_id, quantity}.", items="object")
_FROM = Param("from_country_code", "string", "Ship-from country, to pin the warehouse; omit for the cheapest.")


def _search(values: dict[str, Any], params: tuple[Param, ...]) -> Any:
    positionals, _, body = split(values, params)
    if not body.get("queries") and not body.get("category_ids"):
        raise UserInputError("pass queries, category_ids or both.")
    return execute("suppliers", "search-batch", positionals, None, body)


def _inspect(values: dict[str, Any]) -> Any:
    provider = values["provider"]
    ids = list(values["product_ids"])
    destination = values.get("destination") or {}
    if len(ids) == 1:
        flags = {
            "to_country": destination.get("country_code"),
            "to_zip": destination.get("zip_code"),
            "max_variants": values.get("max_variants"),
        }
        flags = {k: v for k, v in flags.items() if v is not None}
        return execute("suppliers", "inspect", {"provider": provider, "product_id": ids[0]}, flags)
    body = {"product_ids": ids}
    body |= {k: values[k] for k in ("destination", "quantity", "max_variants", "include") if values.get(k)}
    return execute("suppliers", "inspect-batch", {"provider": provider}, None, body)


def _stock(values: dict[str, Any]) -> Any:
    provider = values["provider"]
    if values.get("product_id"):
        return execute(
            "suppliers",
            "check-stock-by-product",
            {"provider": provider, "product_id": values["product_id"]},
        )
    variants = list(values.get("variant_ids") or [])
    if not variants:
        raise UserInputError("pass product_id or variant_ids.")
    if len(variants) == 1:
        return execute("suppliers", "check-stock", {"provider": provider, "variant_id": variants[0]})
    return execute("suppliers", "check-stock-batch", {"provider": provider}, None, {"variant_ids": variants})


def _shipping(values: dict[str, Any]) -> Any:
    provider = values["provider"]
    items = list(values.get("items") or [])
    if values.get("shipping_address"):
        body: dict[str, Any] = {"items": items, "shipping_address": values["shipping_address"]}
        if values.get("from_country_code"):
            body["from_country_code"] = values["from_country_code"]
        return execute("suppliers", "calculate-shipping", {"provider": provider}, None, body)
    if not values.get("destination"):
        raise UserInputError("pass destination {country_code, zip_code}, or a full shipping_address.")
    body = {"items": items, "destination": values["destination"]}
    return execute("suppliers", "quote-shipping", {"provider": provider}, None, body)


def _supplier_order(values: dict[str, Any]) -> Any:
    positionals = {"provider": values["provider"], "order_id": values["supplier_order_id"]}
    order = execute("suppliers", "get-order", positionals)
    try:
        tracking = execute("suppliers", "get-tracking", positionals)
    except CliError as exc:
        # Often just "not shipped yet" — the order itself is still the answer. The supplier's own
        # words go with it, so a failure to read tracking never passes for having none.
        return {"order": order, "tracking_error": exc.message}
    return {"order": order, "tracking": tracking}


ACTIONS = (
    action(
        "list_supplier_categories",
        "List supplier categories",
        "A supplier's own categories, to search a kind of product: find one by text, or walk the "
        "tree from the top.",
        (
            _PROVIDER,
            Param("search", "string", "Categories whose path contains this text.", to="flag"),
            Param("parent", "string", "The children of this category.", to="flag"),
            Param("limit", "integer", "Most categories.", to="flag"),
        ),
        runs("suppliers", "categories"),
        read_only=True,
    ),
    action(
        "search_supplier_products",
        "Search supplier products",
        "Search a supplier's catalog by one or several keywords and/or categories at once, merged, "
        "with warehouse and price filters. Each product comes back once, with the searches that "
        "found it.",
        (
            _PROVIDER,
            Param("queries", "array", "Keywords, one search each.", items="string"),
            Param("category_ids", "array", "Supplier categories to browse.", items="string"),
            Param("queries_within_categories", "boolean", "Search every keyword inside every category."),
            Param("stocked_in", "string", "Only goods already in a warehouse in this country."),
            Param("verified_only", "boolean", "Only verified warehouse stock."),
            Param("min_price", "number", "Lowest supplier price."),
            Param("max_price", "number", "Highest supplier price."),
            Param("sort", "string", "Sort key, e.g. listings, price, newest."),
            Param("order_by", "string", "asc or desc."),
            Param("page_size", "integer", "Results per search (default 20)."),
        ),
        _search,
        read_only=True,
    ),
    action(
        "inspect_supplier_products",
        "Inspect supplier products",
        "Price, variants, stock per warehouse and, with a destination, shipping for one supplier "
        "product in full, or a shortlist of up to 20.",
        (
            _PROVIDER,
            Param("product_ids", "array", "The supplier's product ids (1-20).", required=True, items="string"),
            Param("destination", "object", "Ship to: {country_code, zip_code}; omit to skip shipping."),
            Param("quantity", "integer", "Units to quote shipping for (several products)."),
            Param("max_variants", "integer", "Most variants per product."),
            Param(
                "include", "array", "Several products: heavy fields to add.", items="string",
                choices=("description", "attributes", "variants"),
            ),
        ),
        _inspect,
        read_only=True,
    ),
    action(
        "check_supplier_stock",
        "Check supplier stock",
        "Stock at the supplier per warehouse, for all variants of a product or for given variants.",
        (
            _PROVIDER,
            Param("product_id", "string", "The supplier's product id: all its variants."),
            Param("variant_ids", "array", "The supplier's variant ids.", items="string"),
        ),
        _stock,
        read_only=True,
    ),
    action(
        "quote_supplier_shipping",
        "Quote supplier shipping",
        "Shipping options, cost and delivery time from a supplier for some variants: to a country "
        "and postcode, or to a full address.",
        (
            _PROVIDER,
            Param("items", "array", "Lines: each {variant_id, quantity}.", required=True, items="object"),
            Param("destination", "object", "Ship to: {country_code, zip_code}."),
            _ADDRESS,
            _FROM,
        ),
        _shipping,
        read_only=True,
    ),
    action(
        "get_supplier_balance",
        "Get supplier balance",
        "Money on the owner's account with a supplier.",
        (_PROVIDER,),
        runs("suppliers", "get-balance"),
        read_only=True,
    ),
    action(
        "create_supplier_order",
        "Create a supplier order",
        "Place a dropship order with a supplier for a store order. The cheapest in-stock warehouse "
        "nearest the buyer is used unless pinned; payment follows the supplier balance.",
        (
            _PROVIDER,
            Param(
                "items",
                "array",
                "Lines: each {variant_id, quantity, shipping_method}.",
                required=True,
                items="object",
            ),
            Param(
                "shipping_address", "object",
                "The buyer's address: {country_code, province, city, zip_code, address_line, full_name, phone}.",
                required=True,
            ),
            _FROM,
            Param("order_id", "string", "The SellerClaw order it fulfils.", key="internal_order_id"),
        ),
        runs("suppliers", "create-order"),
        read_only=False,
    ),
    action(
        "confirm_supplier_order",
        "Confirm a supplier order",
        "Confirm a placed supplier order so the supplier processes it.",
        (_PROVIDER, _SUPPLIER_ORDER),
        runs("suppliers", "confirm-order"),
        read_only=False,
    ),
    action(
        "pay_supplier_order",
        "Pay a supplier order",
        "Pay a supplier order from the owner's supplier balance; may need the owner's approval.",
        (_PROVIDER, _SUPPLIER_ORDER),
        runs("suppliers", "pay-order"),
        read_only=False,
        destructive=True,
    ),
    action(
        "cancel_supplier_order",
        "Cancel a supplier order",
        "Cancel a supplier order. Pass the SellerClaw order it was placed for so that order can be "
        "bought again. The buyer's own order is not cancelled.",
        (
            _PROVIDER,
            _SUPPLIER_ORDER,
            Param("order_id", "string", "The SellerClaw order it was placed for.", key="internal_order_id"),
        ),
        runs("suppliers", "cancel-order"),
        read_only=False,
        destructive=True,
    ),
    action(
        "get_supplier_order",
        "Get a supplier order",
        "A supplier order's status and cost, and its tracking once shipped.",
        (_PROVIDER, _SUPPLIER_ORDER),
        _supplier_order,
        read_only=True,
    ),
)
