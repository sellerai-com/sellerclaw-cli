---
name: sellerclaw-catalog
description: "Use when the user wants to work with their own SellerClaw product catalog — find a product, add one from a supplier or by hand, edit its name, images or status, set the purchase price, or remove it."
---

# SellerClaw — internal catalog

The owner's own product catalog: what they sell, what it costs them, where it came from. Listings on
Shopify / eBay / Amazon are built from it — see the `listings` guide for publishing. Run the examples
directly; reach for `sellerclaw_describe` only for a command not shown here, or when a call errors on
a field.

## Find a product

```text
sellerclaw_run(group="catalog", command="overview")                                  # counts by status, out of stock
sellerclaw_run(group="catalog", command="search", flags={"q": "wireless mouse", "limit": 20})
sellerclaw_run(group="catalog", command="get", positionals={"product_id": PRODUCT_ID})

# Exact lookups (all criteria AND-combined)
sellerclaw_run(group="catalog", command="list", flags={"sku": "WM-01"})
sellerclaw_run(group="catalog", command="list",
  flags={"supplier_provider": "cj", "supplier_product_id": SUPPLIER_PRODUCT_ID})
```

## Add products

```text
# From a supplier item — the normal path for dropshipping. Pulls the product and its variants in one
# call; `destination` decides which warehouse's availability and cost are used.
sellerclaw_run(group="catalog", command="source-from-supplier",
  body={"supplier_provider": "cj", "supplier_product_id": SUPPLIER_PRODUCT_ID,
        "destination": {"country_code": "US", "zip_code": "10001"}})

# The owner's own goods — batch create.
sellerclaw_run(group="catalog", command="create",
  body={"items": [{"name": "Wireless Mouse", "description": "2.4 GHz, silent click",
                   "category": "Electronics",
                   "variations": [{"sku": "WM-01", "purchase_price": 9.5}]}]})
```

## Maintain

```text
sellerclaw_run(group="catalog", command="update", positionals={"product_id": PRODUCT_ID},
  body={"name": "Wireless Mouse (2026)", "status": "active"})

# Many products at once — same patch fields, up to 200 per call. One bad id is reported on its own
# line and the rest still apply, so the reply is {items: [{product_id, ok, error, product}]}.
sellerclaw_run(group="catalog", command="bulk-update",
  body={"items": [{"product_id": PRODUCT_ID, "patch": {"name": "Wireless Mouse (2026)"}},
                  {"product_id": OTHER_PRODUCT_ID, "patch": {"brand": "ACME"}}]})

# Supplier cost, not the buyer-facing price. One value for every variation…
sellerclaw_run(group="catalog", command="set-prices", positionals={"product_id": PRODUCT_ID},
  body={"purchase_price": 9.5})
# …or per variation.
sellerclaw_run(group="catalog", command="set-prices", positionals={"product_id": PRODUCT_ID},
  body={"variations": [{"supplier_variant_id": VARIANT_ID, "purchase_price": 9.5}]})

sellerclaw_run(group="catalog", command="delete", positionals={"product_id": PRODUCT_ID})
```

## Watch for

- **The catalog is not the storefront.** A listing keeps its own copy of the text and pictures, so
  `catalog update` changes nothing already published — push the change through the channel commands
  in the `listings` guide.
- **`set-prices` is the cost you pay the supplier**, which feeds margin and profit reporting. The
  buyer-facing price lives on the listing.
- **`weight_grams` is what a marketplace prices postage from.** eBay refuses a listing outright under
  a calculated-rate shipping policy without one. Set it on creation, or afterwards with `catalog
  update` (it applies to every variation); send `null` to clear a wrong one. Leave it out when the
  weight is genuinely unknown — a `0` or a guess is charged to a real buyer at checkout.
- **`list` with no criteria returns the whole catalog.** Pass `limit` (or a filter) — `total` still
  reports the full match count, so a small page is enough to answer "how many". When `total` is
  bigger than the page you asked for, walk the rest with `offset`; `list` and `search` both take it.
- **Editing a set of products is one call, not one call per product.** `update` takes a single
  `product_id`; `bulk-update` takes up to 200 patches at once. Past that it refuses and points at
  the `catalog-file` import, which is the path for loading or rewriting a whole catalog.
- Sourcing the same supplier product twice creates a duplicate. Check with
  `catalog list --supplier_product_id` first.
