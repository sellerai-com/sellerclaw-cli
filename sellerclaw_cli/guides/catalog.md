# SellerClaw — internal catalog

The owner's own product catalog: what they sell, what it costs them, where it came from. Listings on
Shopify / eBay / Amazon are built from it — see the `listings` guide for publishing. Run the examples
directly; reach for `sellerclaw_describe` only for a command not shown here, or when a call errors on
a field.

## Find a product

```text
sellerclaw_read(group="catalog", command="overview")                                  # counts by status, out of stock
sellerclaw_read(group="catalog", command="search", flags={"q": "wireless mouse", "limit": 20})
sellerclaw_read(group="catalog", command="get", positionals={"product_id": PRODUCT_ID})

# Exact lookups (all criteria AND-combined). A list checks a batch in one call; the values
# missing from the answer are not in the catalog.
sellerclaw_read(group="catalog", command="list", flags={"sku": "WM-01"})
sellerclaw_read(group="catalog", command="list",
  flags={"supplier_provider": "cj", "supplier_product_id": [SUPPLIER_PRODUCT_ID, OTHER_ID]})

# Not on sale in one store (`published_in` is the opposite). A row's `store_listing_status` is
# `draft` or `withdrawn` when such a listing exists there.
sellerclaw_read(group="catalog", command="list", flags={"not_published_in": STORE_ID, "limit": 50})

# One supplier: price-list suppliers all share the provider "offline", `supplier_id` tells them apart
sellerclaw_read(group="catalog", command="list", flags={"supplier_id": SUPPLIER_ID})
```

## Add products

```text
# From a supplier item — the normal path for dropshipping. Pulls the product and its variants in one
# call; `destination` decides which warehouse's availability and cost are used.
sellerclaw_write(group="catalog", command="source-from-supplier",
  body={"supplier_provider": "cj", "supplier_product_id": SUPPLIER_PRODUCT_ID,
        "destination": {"country_code": "US", "zip_code": "10001"}})

# The owner's own goods — batch create.
sellerclaw_write(group="catalog", command="create",
  body={"items": [{"name": "Wireless Mouse", "description": "2.4 GHz, silent click",
                   "category": "Electronics",
                   "variations": [{"sku": "WM-01", "purchase_price": 9.5}]}]})
```

## A whole catalog from a spreadsheet

When the owner has their goods in a file rather than at a supplier with an API, take the file — don't
retype it into `create` row by row.

```text
sellerclaw_read(group="catalog-file", command="template")                 # blank file + column notes
sellerclaw_read(group="files", command="list", flags={"limit": 10})       # what they have uploaded
sellerclaw_write(group="files", command="from-url", body={"url": "https://..."})    # or pull one in
sellerclaw_read(group="catalog-file", command="check",   body={"file_id": FILE_ID})
sellerclaw_read(group="catalog-file", command="preview", body={"file_id": FILE_ID})
sellerclaw_write(group="catalog-file", command="apply",   body={"file_id": FILE_ID})
```

Every step takes a `file_id`, so the file has to reach SellerClaw first: either the owner uploads it
in the web app, or it is somewhere with a URL and `files from-url` fetches it. A spreadsheet attached
to this conversation is not reachable from here — ask for a link, or ask them to add it to their file
library.

Always `check` then `preview` before `apply`, and show the owner the preview: it says what would be
created, what would change and which rows could not be read, with row numbers. A refusal quotes the
heading row back, which is what you write `columns` from when their file uses its own wording. A
supplier's own price list (no API, prices that move) is the same shape under `price-list` — see the
`suppliers` guide.

## Maintain

```text
sellerclaw_write(group="catalog", command="update", positionals={"product_id": PRODUCT_ID},
  body={"name": "Wireless Mouse (2026)", "status": "active"})

# Many products at once — same patch fields, up to 200 per call. One bad id is reported on its own
# line and the rest still apply, so the reply is {items: [{product_id, ok, error, product}]}.
sellerclaw_write(group="catalog", command="bulk-update",
  body={"items": [{"product_id": PRODUCT_ID, "patch": {"name": "Wireless Mouse (2026)"}},
                  {"product_id": OTHER_PRODUCT_ID, "patch": {"brand": "ACME"}}]})

# Supplier cost, not the buyer-facing price. One value for every variation…
sellerclaw_write(group="catalog", command="set-prices", positionals={"product_id": PRODUCT_ID},
  body={"purchase_price": 9.5})
# …or per variation.
sellerclaw_write(group="catalog", command="set-prices", positionals={"product_id": PRODUCT_ID},
  body={"variations": [{"supplier_variant_id": VARIANT_ID, "purchase_price": 9.5}]})

sellerclaw_write(group="catalog", command="delete", positionals={"product_id": PRODUCT_ID})
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
