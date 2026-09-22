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
`withdraw`, `delete`, `list-drafts`, `create-drafts`, `publish-drafts`.

## eBay

```text
sellerclaw_run(group="ebay-listings", command="publish",
  positionals={"store_id": STORE_ID}, body={"listing_ids": ["1234567890"]})
sellerclaw_run(group="ebay-listings", command="withdraw",
  positionals={"store_id": STORE_ID}, body={"listing_ids": ["1234567890"]})
sellerclaw_run(group="ebay-listings", command="sync-stock",
  positionals={"store_id": STORE_ID}, body={"items": [{"sku": "WM-01", "quantity": 42}]})
```

eBay listings need business policies (payment/return/shipping) and a location — take their ids from
`ebay-store list-policies` / `ebay-store list-locations` and add whichever a field error asks for.
Those ids are SellerClaw's own, and they are what every field here expects; the marketplace's own ids
(`list-business-policies`, `list-raw-locations`) are a raw account read, not something to send back.
To stop being asked on every draft, pin the store's defaults once with `channels set-default-policies`
/ `channels set-default-warehouse` — the owner's call, so ask first. Drafts live under
`create-drafts` / `update-draft` / `publish` in the same group.

## Amazon

Same shape under `amazon-listings` — read offers and sync price/stock (`store_id` is the path
argument). `sellerclaw_describe` the exact command before the first call.

## Etsy

```text
sellerclaw_run(group="etsy-listings", command="draft",
  positionals={"store_id": STORE_ID}, body={"product_ids": [PRODUCT_ID]})
sellerclaw_run(group="etsy-listings", command="publish",
  positionals={"store_id": STORE_ID}, body={"listing_ids": [LISTING_ID]})
```

Etsy refuses a physical listing without a shipping profile and a processing profile (how long until
the item is ready to send). Leave them out and the shop's default — or its only one — is used; when
the shop has several, the drafts come back with a `needs_policies` question. Answer it for the whole
batch with `etsy-listings set-policies` (`shipping_profile_id`, `return_policy_id`,
`readiness_state_id`), taking the ids from `etsy-store list-policies` — SellerClaw's ids, not Etsy's.

## Other storefronts

WooCommerce, Wix and BigCommerce work the same way under `woocommerce-listings` / `wix-listings` /
`bigcommerce-listings`: `draft`, then `publish`. `sellerclaw_describe` the group before the first call.

## Watch for

- **Stock sync ≠ publish.** `create` / `publish` create the listing; `sync-stock` only updates
  quantities (and optional price).
- **`withdraw` is not `delete`.** `withdraw` takes a listing off the storefront and can be undone;
  `delete` destroys it — on Etsy the listing, its address and the reviews and favourites on it go
  with it, and re-listing costs a new listing fee. An unqualified "take this off my shop" means
  `withdraw`; only delete when the owner said to delete.
- **Raw fallback:** the `shopify` / `ebay` / `amazon` / `etsy` / `woocommerce` / `wix` /
  `bigcommerce` groups pass raw API calls through when no curated command fits.
