"""Listings on the owner's stores, and the categories and attributes a listing needs."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli._errors import CliError
from sellerclaw_cli.chatgpt._action import (
    Param,
    action,
    by_platform,
    execute,
    per_platform,
    platform_of,
    runs,
    store_param,
    unsupported,
)

_STORE = store_param()
_STORE_FLAG = store_param(to="flag")
_STORE_BODY = store_param(to="body")

_ALL_PLATFORMS = (
    "shopify", "ebay", "amazon", "walmart", "woocommerce", "wix", "bigcommerce", "etsy", "tiktok_shop",
)
_LISTING_IDS = Param(
    "listing_ids", "array", "The listings' own ids (listing_id), not variation ids.", required=True, items="string"
)


def _delete_listings(values: dict[str, Any]) -> Any:
    store_id = str(values["store_id"])
    platform = platform_of(store_id)
    ids = list(values["listing_ids"])
    if platform == "ebay":
        # eBay deletes one listing per call. Each gets its own outcome: a refusal halfway through
        # must not hide the ones already gone, or the model would send them again.
        results: list[dict[str, Any]] = []
        for listing_id in ids:
            try:
                execute("ebay-listings", "delete", {"store_id": store_id, "listing_id": listing_id})
            except CliError as exc:
                results.append({"listing_id": listing_id, "deleted": False, "error": exc.message})
            else:
                results.append({"listing_id": listing_id, "deleted": True})
        return {"results": results}
    groups = {"shopify": "shopify-listings", "wix": "wix-listings", "etsy": "etsy-listings"}
    group = groups.get(platform)
    if group is None:
        raise unsupported("Deleting listings", platform, [*groups, "ebay"])
    return execute(group, "delete", {"store_id": store_id}, None, {"listing_ids": ids})


def _problems(values: dict[str, Any], params: tuple[Param, ...]) -> Any:
    from sellerclaw_cli.chatgpt._action import split

    _, flags, _ = split(values, params)
    flags.pop("hidden", None)
    return execute("listing-problems", "list-hidden" if values.get("hidden") else "list", None, flags)


def _set_hidden(values: dict[str, Any]) -> Any:
    command = "hide" if values["hidden"] else "unhide"
    return execute("listing-problems", command, None, None, {"problem_ids": list(values["problem_ids"])})


def _browse_categories(values: dict[str, Any], params: tuple[Param, ...]) -> Any:
    from sellerclaw_cli.chatgpt._action import split

    _, flags, _ = split(values, params)
    children = execute("categories", "children", None, flags)
    if values.get("parent_category_id"):
        return children
    return {"trees": execute("categories", "trees", None, {"store_id": values["store_id"]}), "top_level": children}


def _save_category(values: dict[str, Any]) -> Any:
    body: dict[str, Any] = {"store_id": values["store_id"], "name": values["name"]}
    if values.get("category_id"):
        return execute("categories", "rename", None, None, {**body, "external_id": values["category_id"]})
    if values.get("parent_category_id"):
        body["parent_external_id"] = values["parent_category_id"]
    return execute("categories", "create", None, None, body)


ACTIONS = (
    action(
        "search_listings",
        "Search listings",
        "Find listings across all stores by title text, SKU or marketplace item id, store, product, "
        "status, and whether shoppers can buy them. One entry per listing with its listing_id and "
        "its variations. With no criteria, the most recently updated.",
        (
            Param("q", "string", "Text in the title, a SKU or a marketplace item id.", to="flag"),
            store_param(to="flag", required=False),
            Param("product_id", "string", "Catalog product: every listing made from it.", to="flag"),
            Param("sku", "array", "Exact SKUs.", items="string", to="flag"),
            Param(
                "status", "string", "Listing status.", to="flag",
                choices=("draft", "active", "published", "withdrawn", "removed"),
            ),
            Param(
                "sale_state", "array",
                "Whether shoppers can buy it; not_selling = hidden, under review, refused or gone.",
                items="string", to="flag", choices=("selling", "out_of_stock", "not_selling", "not_published"),
            ),
            Param(
                "has_unpublished_changes",
                "boolean",
                "Only listings with edits not yet on the marketplace.",
                to="flag",
            ),
            Param("not_in_catalog", "boolean", "Only listings found on the store but not in the catalog.", to="flag"),
            Param("limit", "integer", "Results per page.", to="flag"),
            Param("offset", "integer", "Results to skip.", to="flag"),
        ),
        runs("listings", "search"),
        read_only=True,
    ),
    action(
        "get_listing",
        "Get a listing",
        "One listing with every variation's price, stock and status, whether shoppers can buy it "
        "and why not, and what the marketplace refused.",
        (Param("listing_id", "string", "The listing's id.", required=True, to="path"),),
        runs("listings", "get"),
        read_only=True,
    ),
    action(
        "get_store_listing_summary",
        "Get a store's listing summary",
        "Counts of a store's listings by status, total and zero stock, and price range.",
        (
            _STORE,
            Param(
                "status",
                "string",
                "Only this status.",
                to="flag",
                choices=("active", "published", "draft", "withdrawn"),
            ),
        ),
        lambda values, params: by_platform(
            values, params, what="A listing summary",
            commands=per_platform("listings", "summary", _ALL_PLATFORMS),
        ),
        read_only=True,
    ),
    action(
        "get_ebay_listing_performance",
        "Get eBay listing performance",
        "Impressions, click-through, views, conversion and sales of an eBay store's top listings, "
        "with what each listing is missing and which ones underperform.",
        (
            _STORE,
            Param("days", "integer", "How many days back.", to="flag"),
            Param("top_n", "integer", "How many top listings to audit.", to="flag"),
        ),
        runs("ebay-listings", "performance"),
        read_only=True,
    ),
    action(
        "list_draft_listings",
        "List draft listings",
        "A store's draft listings, not yet published, with whether each is ready and what blocks it.",
        (
            _STORE_FLAG,
            Param("limit", "integer", "Results per page.", to="flag"),
            Param("offset", "integer", "Results to skip.", to="flag"),
        ),
        runs("listings", "drafts"),
        read_only=True,
    ),
    action(
        "create_draft_listings",
        "Create draft listings",
        "Draft catalog products onto a store, any platform. Give each product its own title, "
        "description, images, attributes and category, and the platform's own fields once for the "
        "batch. Runs in the background; follow it with get_listing_job. Nothing is published.",
        (
            _STORE,
            Param(
                "products", "array",
                "Each {product_id, title?, description?, images?, attributes?, category_external_id?}; "
                "images in publish order, the first is the cover.",
                items="object",
            ),
            Param("product_ids", "array", "Catalog product ids to draft with the catalog's own text.", items="string"),
            Param(
                "channel", "object",
                "The platform's fields for the batch, e.g. eBay policy ids, condition and api_kind; "
                "Walmart item spec.",
            ),
        ),
        runs("listings", "create-drafts"),
        read_only=False,
    ),
    action(
        "check_listings_ready",
        "Check listings are ready",
        "Dry run: whether each listing can be published and what blocks it, with hints worth "
        "fixing first.",
        (_LISTING_IDS,),
        runs("listings", "readiness"),
        read_only=True,
    ),
    action(
        "delete_draft_listings",
        "Delete draft listings",
        "Delete drafts that were never published, or single variations of them. Live listings are "
        "left alone.",
        (
            Param("listing_ids", "array", "Whole drafts to delete.", items="string"),
            Param("variation_ids", "array", "Single draft variations to delete.", items="string"),
        ),
        runs("listings", "delete-drafts"),
        read_only=False,
        destructive=True,
    ),
    action(
        "update_listings",
        "Update listings",
        "Change many listings at once, drafts and live ones: title, description, prices and "
        "quantities by SKU, images, attributes. Edits to live listings go to the marketplace with "
        "the next publish_listings.",
        (
            Param(
                "items", "array",
                "Each {listing_id, patch: {title?, description?, sell_prices?, quantities?, images?, "
                "variation_images?, videos?, attributes?}}; sell_prices and quantities keyed by SKU.",
                required=True, items="object",
            ),
        ),
        runs("listings", "bulk-update"),
        read_only=False,
        destructive=True,
    ),
    action(
        "update_listing_stock",
        "Update listing stock",
        "Set stock, and optionally price, of live listings on a store by SKU; the marketplace is "
        "updated straight away.",
        (
            _STORE,
            Param(
                "items", "array", "Each {sku, quantity?, price?}.", required=True, items="object",
            ),
        ),
        lambda values, params: by_platform(
            values, params, what="Updating stock",
            commands=per_platform("listings", "sync-stock", _ALL_PLATFORMS),
        ),
        read_only=False,
        destructive=True,
    ),
    action(
        "publish_listings",
        "Publish listings",
        "Publish drafts, or send pending edits of live listings, to a store's marketplace: up to 25 "
        "per job, in the background. Listings that aren't ready are skipped and reported. Follow "
        "it with get_listing_job.",
        (
            _STORE,
            _LISTING_IDS,
            Param(
                "variation_ids",
                "array",
                "Withdrawn variations to bring back on sale (WooCommerce).",
                items="string",
            ),
        ),
        runs("listings", "bulk-publish", body={"kind": "publish"}),
        read_only=False,
        open_world=True,
    ),
    action(
        "withdraw_listings",
        "Withdraw listings",
        "Take live listings off sale on a store, up to 25 per job, in the background; they can be "
        "published again. Follow it with get_listing_job.",
        (_STORE, _LISTING_IDS),
        runs("listings", "bulk-publish", body={"kind": "withdraw"}),
        read_only=False,
        destructive=True,
    ),
    action(
        "delete_listings",
        "Delete listings",
        "Delete listings from the marketplace permanently. eBay, Wix, Shopify. Use only when the "
        "owner asked to delete rather than withdraw.",
        (_STORE, _LISTING_IDS),
        _delete_listings,
        read_only=False,
        destructive=True,
    ),
    action(
        "get_listing_job",
        "Get a listing job",
        "Progress of a drafting, publishing, withdrawing or attribute-filling job, and each "
        "listing's outcome: succeeded, failed with the marketplace's reason, or pending.",
        (_STORE, Param("job_id", "string", "The job's id.", required=True, to="path")),
        runs("listings", "bulk-job"),
        read_only=True,
    ),
    action(
        "get_publish_status",
        "Get publish status",
        "Where a submitted listing stands in the marketplace's own review. Amazon, Walmart.",
        (_STORE, Param("listing_id", "string", "The listing's id.", required=True, to="path")),
        lambda values, params: by_platform(
            values, params, what="Publish status",
            commands=per_platform("listings", "publish-status", ("amazon", "walmart")),
        ),
        read_only=True,
    ),
    action(
        "refresh_store_listings",
        "Refresh store listings",
        "Re-read a store's listings from its marketplace, after changes made there directly. Runs "
        "in the background.",
        (_STORE,),
        runs("listings", "sync"),
        read_only=False,
    ),
    action(
        "list_listing_problems",
        "List listing problems",
        "Listings that marketplaces refused or flagged across the stores — failed publishes, "
        "rejected price or stock updates, withdrawals that didn't land — with the reason. "
        "hidden=true lists the ones the owner hid.",
        (
            store_param(to="flag", key="sales_channel_id", required=False),
            Param("product_id", "string", "Only this catalog product.", to="flag"),
            Param("severity", "string", "error or warning.", to="flag", choices=("error", "warning")),
            Param("action", "string", "The attempt that hit it.", to="flag", choices=("publish", "sync", "withdraw")),
            Param("hidden", "boolean", "true for the hidden problems.", to="flag"),
        ),
        _problems,
        read_only=True,
    ),
    action(
        "set_listing_problems_hidden",
        "Hide or unhide listing problems",
        "Hide listing problems from the list and counters, or bring hidden ones back.",
        (
            Param("problem_ids", "array", "Problem ids from list_listing_problems.", required=True, items="string"),
            Param("hidden", "boolean", "true to hide, false to bring back.", required=True),
        ),
        _set_hidden,
        read_only=False,
    ),
    action(
        "find_amazon_catalog_item",
        "Find an Amazon catalog item",
        "Find the Amazon catalog item (ASIN) a product should be listed against, by barcode or "
        "keywords. Keyword matches are candidates: confirm the right one before drafting.",
        (
            _STORE,
            Param("keywords", "string", "Product name or search text."),
            Param("identifiers", "array", "Barcodes or ASINs for an exact match.", items="string"),
            Param(
                "identifiers_type", "string", "Kind of identifier.",
                choices=("ASIN", "UPC", "EAN", "GTIN", "ISBN", "JAN", "MINSAN", "SKU"),
            ),
            Param("limit", "integer", "Most candidates (1-20)."),
        ),
        runs("amazon-listings", "find-asin"),
        read_only=True,
        open_world=True,
    ),
    action(
        "suggest_category",
        "Suggest a category",
        "A shortlist of marketplace categories for a catalog product on a store.",
        (
            _STORE_BODY,
            Param("product_id", "string", "The catalog product.", required=True),
            Param("requires_variations", "boolean", "Only categories that take multi-variation listings."),
        ),
        runs("categories", "suggest"),
        read_only=True,
    ),
    action(
        "confirm_category",
        "Confirm a category",
        "Remember the category chosen for a product, so similar products on that store need no "
        "suggesting.",
        (
            _STORE_BODY,
            Param("product_id", "string", "The catalog product.", required=True),
            Param("category_id", "string", "The chosen category's category_id.", required=True),
        ),
        runs("categories", "confirm"),
        read_only=False,
    ),
    action(
        "search_categories",
        "Search categories",
        "Find a marketplace category you can publish into, by name, on a store.",
        (
            _STORE_FLAG,
            # No leaf_only: it is on by default and a false flag is never sent, so offering it would
            # promise a switch that does nothing. browse_categories walks the levels above.
            Param("q", "string", "Words from the category name or path.", required=True, to="flag"),
            Param("supports_variations", "boolean", "Only categories that take multi-variation listings.", to="flag"),
            Param("limit", "integer", "Most results.", to="flag"),
        ),
        runs("categories", "search"),
        read_only=True,
    ),
    action(
        "list_used_categories",
        "List used categories",
        "Categories a store already sells in, busiest first.",
        (_STORE_FLAG, Param("limit", "integer", "Most categories.", to="flag")),
        runs("categories", "used"),
        read_only=True,
    ),
    action(
        "browse_categories",
        "Browse categories",
        "A store's category tree one level at a time; without a parent, the top level and the "
        "trees the store uses.",
        (
            _STORE_FLAG,
            Param("parent_category_id", "string", "The parent's external_id.", to="flag", key="parent_external_id"),
            Param("tree_id", "string", "Which tree, when the store has several.", to="flag"),
        ),
        _browse_categories,
        read_only=True,
    ),
    action(
        "save_store_category",
        "Create or rename a store category",
        "Create a category on the owner's own store, or rename one by passing its id. WooCommerce, "
        "Wix, BigCommerce. A name the store already has is returned, not duplicated.",
        (
            _STORE_BODY,
            Param("name", "string", "The category's name.", required=True),
            Param("category_id", "string", "The external_id of the category to rename."),
            Param("parent_category_id", "string", "New category: the external_id to nest it under."),
        ),
        _save_category,
        read_only=False,
        destructive=True,
    ),
    action(
        "get_category_attributes",
        "Get category attributes",
        "The attributes a category requires or allows on a store's marketplace, which can vary by "
        "variation, and their allowed values.",
        (
            _STORE_BODY,
            Param("category_id", "string", "The category's external_id.", required=True, key="category_external_id"),
        ),
        runs("attributes", "schema"),
        read_only=True,
    ),
    action(
        "search_attribute_values",
        "Search attribute values",
        "Allowed values of one attribute in a category, such as Brand or Model.",
        (
            _STORE_BODY,
            Param("category_id", "string", "The category's external_id.", required=True, key="category_external_id"),
            Param("attribute", "string", "The attribute name, e.g. Country of Origin.", required=True),
            Param("q", "string", "Only values containing this text."),
            Param("limit", "integer", "Most values (1-200)."),
        ),
        runs("attributes", "values"),
        read_only=True,
    ),
    action(
        "fill_listing_attributes",
        "Fill listing attributes",
        "Fill the attributes of existing drafts from their products' own data, matched to each "
        "draft's category; on eBay it replaces the item specifics. Up to 10 products, in the "
        "background; follow it with get_listing_job.",
        (
            _STORE,
            Param(
                "product_ids",
                "array",
                "Catalog products whose drafts need attributes.",
                required=True,
                items="string",
            ),
        ),
        runs("attributes", "map"),
        read_only=False,
        destructive=True,
    ),
)
