"""The owner's catalog: products, their cost, markup, variations and supplier, and file imports."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.chatgpt._action import Param, action, execute, runs, store_param

_PRODUCT = Param("product_id", "string", "The catalog product's id.", required=True, to="path")
_STATUSES = ("sourced", "active", "archived")
_KIND = Param(
    "kind", "string", "catalog = a product spreadsheet; price_list = a supplier's price list.",
    required=True, choices=("catalog", "price_list"),
)
_FILE = Param("file_id", "string", "The file's id from list_files or save_file_from_url.")
_SUPPLIER = Param("supplier_id", "string", "Price list: the supplier account's id from list_connections.")
_COLUMNS = Param(
    "columns", "object", "The file's headings mapped to the template's columns, when they differ, "
    'e.g. {"Артикул": "SKU"}.',
)
_GROUPS = {"catalog": "catalog-file", "price_list": "price-list"}


def _import_body(values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    group = _GROUPS[values["kind"]]
    if not values.get("file_id"):
        raise UserInputError("pass file_id.")
    body: dict[str, Any] = {"file_id": values["file_id"]}
    if values["kind"] == "price_list":
        if not values.get("supplier_id"):
            raise UserInputError("a price list belongs to a supplier: pass supplier_id.")
        body["supplier_id"] = values["supplier_id"]
    if values.get("columns"):
        body["columns"] = values["columns"]
    return group, body


def _preview_import(values: dict[str, Any]) -> Any:
    if not values.get("file_id"):
        return execute(_GROUPS[values["kind"]], "template", None, {"fmt": values.get("format") or "xlsx"})
    group, body = _import_body(values)
    return {"check": execute(group, "check", None, None, body), "preview": execute(group, "preview", None, None, body)}


def _apply_import(values: dict[str, Any]) -> Any:
    group, body = _import_body(values)
    applied = execute(group, "apply", None, None, body)
    if values["kind"] != "price_list" or not values.get("create_missing_products"):
        return applied
    created = execute("price-list", "create-products", None, None, {"supplier_id": body["supplier_id"]})
    return {"applied": applied, "created_products": created}


ACTIONS = (
    action(
        "get_catalog_overview",
        "Get the catalog overview",
        "Catalog totals: products by status and how many are out of stock.",
        (),
        runs("catalog", "overview"),
        read_only=True,
    ),
    action(
        "list_products",
        "List products",
        "Catalog products, narrowed by any mix of status, supplier, SKU, text and where they are "
        "or are not on sale. total is the full match count.",
        (
            Param("q", "string", "Text in the name or a variation's SKU.", to="flag"),
            Param("status", "string", "Catalog status.", to="flag", choices=_STATUSES),
            Param("sku", "array", "Exact SKUs.", items="string", to="flag"),
            Param("supplier_provider", "string", "Supplier, e.g. cj.", to="flag"),
            Param("supplier_id", "string", "One supplier account.", to="flag"),
            Param(
                "supplier_product_id", "array", "The supplier's product ids: is this product already in the catalog?",
                items="string", to="flag",
            ),
            Param("published_in", "string", "A store's id or domain: only products on sale there.", to="flag"),
            Param("not_published_in", "string", "A store's id or domain: only products not on sale there.", to="flag"),
            Param("limit", "integer", "Results per page.", to="flag"),
            Param("offset", "integer", "Results to skip.", to="flag"),
        ),
        runs("catalog", "list"),
        read_only=True,
    ),
    action(
        "search_products",
        "Search products",
        "Find catalog products by part of the name or a SKU.",
        (
            Param("q", "string", "What to search for.", required=True, to="flag"),
            Param("status", "string", "Catalog status.", to="flag", choices=_STATUSES),
            Param("limit", "integer", "Results per page.", to="flag"),
            Param("offset", "integer", "Results to skip.", to="flag"),
        ),
        runs("catalog", "search"),
        read_only=True,
    ),
    action(
        "get_product",
        "Get a product",
        "One catalog product: variations with SKU, stock and prices, images, attributes, category "
        "and supplier.",
        (_PRODUCT,),
        runs("catalog", "get"),
        read_only=True,
    ),
    action(
        "create_products",
        "Create products",
        "Create catalog products. Nothing appears on a store until it is drafted and published. "
        "Returns each created product and each refused item with the reason.",
        (
            Param(
                "items", "array",
                "Each {name, description, category, variations: [{supplier_variant_id, sku, name, "
                "available_quantity, shipping_cost, purchase_price?, images?, attributes?, barcode?, "
                "weight_grams?}], images?, brand?, country_of_origin?, attributes?}.",
                required=True, items="object",
            ),
        ),
        runs("catalog", "create"),
        read_only=False,
    ),
    action(
        "update_products",
        "Update products",
        "Change one or many catalog products (up to 200): name, description, images, category, "
        "status, brand, country of origin, attributes, weight. Listings made from them keep their "
        "own copy until they are updated.",
        (
            Param(
                "items", "array",
                "Each {product_id, patch: {name?, description?, images?, category?, status?, brand?, "
                "country_of_origin?, attributes?, weight_grams?}}; attributes replace the whole map.",
                required=True, items="object",
            ),
        ),
        runs("catalog", "bulk-update"),
        read_only=False,
        destructive=True,
    ),
    action(
        "delete_product",
        "Delete a product",
        "Delete a catalog product.",
        (_PRODUCT,),
        runs("catalog", "delete"),
        read_only=False,
        destructive=True,
    ),
    action(
        "set_product_cost",
        "Set product cost",
        "Set what the supplier charges for a product, for all variations or each one. Store prices "
        "follow from cost and markup.",
        (
            _PRODUCT,
            Param("purchase_price", "number", "Cost applied to every variation."),
            Param("variations", "array", "Per variation: {supplier_variant_id, purchase_price}.", items="object"),
        ),
        runs("catalog", "set-prices"),
        read_only=False,
        destructive=True,
    ),
    action(
        "add_supplier_product",
        "Add a supplier product",
        "Add a supplier's product to the catalog with all its variants, images and cost, linked to "
        "that supplier for stock and ordering.",
        (
            Param("supplier_provider", "string", "Supplier, e.g. cj.", required=True),
            Param("supplier_product_id", "string", "The supplier's product id.", required=True),
            Param("destination", "object", "Where it ships: {country_code, zip_code}.", required=True),
            Param("max_variants", "integer", "Most variants to import (default 500)."),
        ),
        runs("catalog", "source-from-supplier"),
        read_only=False,
    ),
    action(
        "get_product_markup",
        "Get product markup",
        "Which of these products carry a markup of their own, and on which store. Others are priced "
        "by their store's markup.",
        (Param("product_ids", "array", "Catalog product ids (up to 200).", required=True, items="string", to="flag"),),
        runs("catalog", "markup"),
        read_only=True,
    ),
    action(
        "set_product_markup",
        "Set product markup",
        "Give products a markup of their own over cost, overriding their store's, on one store or "
        "everywhere; null removes it. Applies after the owner approves.",
        (
            Param("product_ids", "array", "Catalog product ids (1-200).", required=True, items="string"),
            Param(
                "markup_percent",
                "number",
                "Percent over cost (0-500); null removes it.",
                required=True,
                nullable=True,
            ),
            store_param(to="body", key="sales_channel_id", required=False),
        ),
        runs("catalog", "set-markup"),
        read_only=False,
        destructive=True,
    ),
    action(
        "set_product_variations",
        "Set product variations",
        "Correct a product's stock, SKU, barcode, weight, shipping cost or purchase price, for all "
        "variations or each one. Stock and cost of a CJ product come from the supplier.",
        (
            _PRODUCT,
            Param("available_quantity", "integer", "Stock for every variation."),
            Param("sku", "string", "SKU for every variation."),
            Param("barcode", "string", "Barcode for every variation."),
            Param("weight_grams", "integer", "Packed weight of one unit."),
            Param("purchase_price", "number", "Cost for every variation."),
            Param("shipping_cost", "number", "Supplier shipping cost per unit."),
            Param("purchase_currency", "string", "Currency the cost is in, e.g. EUR."),
            Param(
                "variations", "array",
                "Per variation: {supplier_variant_id, sku?, barcode?, available_quantity?, purchase_price?, "
                "shipping_cost?, weight_grams?}.",
                items="object",
            ),
        ),
        runs("catalog", "set-variations"),
        read_only=False,
        destructive=True,
    ),
    action(
        "set_product_supplier",
        "Set product supplier",
        "Record which supplier account supplies a product, or null for nobody.",
        (
            _PRODUCT,
            Param(
                "supplier_id",
                "string",
                "Supplier account id from list_connections; null unbinds.",
                required=True,
                nullable=True,
            ),
            Param("supplier_product_id", "string", "The supplier's code for the item."),
            Param("supplier_product_url", "string", "The item's page at the supplier."),
        ),
        runs("catalog", "set-supplier"),
        read_only=False,
        destructive=True,
    ),
    action(
        "preview_import",
        "Preview an import",
        "Check a product spreadsheet or a supplier price list from the owner's files and preview "
        "what importing it would change: new products, changed prices and stock, unreadable rows. "
        "Without a file, returns the template to fill in.",
        (_KIND, _FILE, _SUPPLIER, _COLUMNS, Param("format", "string", "Template format.", choices=("xlsx", "csv"))),
        _preview_import,
        read_only=True,
    ),
    action(
        "apply_import",
        "Apply an import",
        "Import a previewed product spreadsheet or supplier price list into the catalog as "
        "previewed. Nothing is deleted or taken off sale.",
        (
            _KIND,
            Param("file_id", "string", "The file's id.", required=True),
            _SUPPLIER,
            _COLUMNS,
            Param("create_missing_products", "boolean", "Price list: also create products for lines that match none."),
        ),
        _apply_import,
        read_only=False,
        destructive=True,
    ),
    action(
        "stop_selling_missing_from_price_list",
        "Stop selling missing products",
        "Set stock to zero for positions a supplier's new price list no longer contains, when the "
        "owner asked for it. The products stay in the catalog.",
        (
            Param("supplier_id", "string", "The supplier account's id.", required=True),
            Param("codes", "array", "SKUs or barcodes of the positions.", required=True, items="string"),
        ),
        runs("price-list", "out-of-sale"),
        read_only=False,
        destructive=True,
    ),
)
