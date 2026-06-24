---
name: sellerclaw-listings
description: "Use when the user wants to list, publish, update, or withdraw a product on Shopify, eBay, or Amazon through SellerClaw — create a listing, change price or stock, fix a draft, or push a catalog product to a store."
---

# SellerClaw — listings

Publishing and maintaining marketplace listings via `sellerclaw_run`. Run the examples directly; reach
for `sellerclaw_describe` only for a command not shown here, or when a call errors on a field.

## Find the store and product

```text
sellerclaw_run(group="channels", command="list")                       # store ids
sellerclaw_run(group="listings", command="search", flags={"q": "wireless mouse"})   # find across all stores
sellerclaw_run(group="shopify-listings", command="summary", positionals={"store_id": STORE_ID})
```

## Shopify

```text
# Publish products as listings. Each item: title (required), plus optional body_html, vendor,
# product_type, tags[], status, images[] (URLs), variants[{sku, title, barcode, price, compare_at_price}].
sellerclaw_run(group="shopify-listings", command="create",
  positionals={"store_id": STORE_ID},
  body={"items": [{"title": "Wireless Mouse", "vendor": "Acme",
                   "images": ["https://cdn.example.com/mouse.jpg"],
                   "variants": [{"sku": "WM-01", "price": "19.99"}]}]})

# Update stock (and optionally price). Each item: sku (required), quantity (required), remote_id?,
# price?, compare_at_price?.
sellerclaw_run(group="shopify-listings", command="sync-stock",
  positionals={"store_id": STORE_ID},
  body={"items": [{"sku": "WM-01", "quantity": 42}]})
```

Other Shopify commands (confirm fields with `sellerclaw_describe` if unsure): `update`, `publish`,
`unpublish`, `delete`, `list-drafts`, `create-drafts`, `publish-drafts`.

## eBay

```text
sellerclaw_run(group="ebay-listings", command="publish",
  positionals={"store_id": STORE_ID}, body={"listing_ids": ["1234567890"]})
sellerclaw_run(group="ebay-listings", command="withdraw",
  positionals={"store_id": STORE_ID}, body={"listing_ids": ["1234567890"]})
sellerclaw_run(group="ebay-listings", command="sync-stock",
  positionals={"store_id": STORE_ID}, body={"items": [{"sku": "WM-01", "quantity": 42}]})
```

eBay listings need business policies (payment/return/shipping) and a location — get their ids from the
`ebay-store` group and add whichever a field error asks for. Drafts live under `create-drafts` /
`update-draft` / `publish` in the same group.

## Amazon

Same shape under `amazon-listings` — read offers and sync price/stock (`store_id` is the path
argument). `sellerclaw_describe` the exact command before the first call.

## Watch for

- **Stock sync ≠ publish.** `create` / `publish` create the listing; `sync-stock` only updates
  quantities (and optional price).
- **Raw fallback:** the `shopify` / `ebay` / `amazon` groups pass raw API calls through when no curated
  command fits.
