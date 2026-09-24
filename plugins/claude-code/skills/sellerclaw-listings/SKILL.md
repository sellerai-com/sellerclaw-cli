---
name: sellerclaw-listings
description: "Use when the user wants to list, publish, update, or withdraw a product on a marketplace or store through SellerClaw — Shopify, eBay, Amazon, Etsy, Walmart, TikTok Shop, WooCommerce, Wix or BigCommerce: create a listing, change price or stock, push a catalog product to a store, or work out why a marketplace refused one (category, item specifics, missing photo)."
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

## Listing ids: one per listing

Every listing command — the shared `listings` group and each store's own (`ebay-listings`,
`shopify-listings`, …) — takes the **listing's own id**: the `listing_id` on a list or search entry,
one per product however many variations it holds. A variation's id is refused with the listing id to
use instead (`use_instead` in the error); swap and re-send. Lists and write answers come back one
entry per listing, with `variations` naming each variation by its own `variation_id`. The few
per-variation commands take that id: a `delete-drafts` variation belongs in its own `variation_ids`
list, a publish brings one withdrawn size back by naming it there (WooCommerce, SellerCart), and one
Amazon offer alone is `amazon-listings update` with its `variation_id`, or `withdraw` with it in
`variation_ids`.

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

## Other storefronts and marketplaces

WooCommerce, Wix, BigCommerce, Walmart and TikTok Shop work the same way under
`woocommerce-listings` / `wix-listings` / `bigcommerce-listings` / `walmart-listings` /
`tiktok-shop-listings`: `draft`, then `publish`. `sellerclaw_describe` the group before the first
call. TikTok Shop wants a category and its attributes up front — `tiktok-shop-store categories` and
`category-attributes` — and Walmart reports the outcome asynchronously, so read `publish-status`
rather than assuming the publish call's answer was the last word.

The owner's own shop is not here: SellerCart has its own guide (`storefront`).

## When a marketplace refuses

A refused publish is a normal step, not a dead end. The reason is nearly always the category or the
item specifics, and there are commands for both — never guess a category id or invent an attribute
value.

```text
# 1. Where does this product belong on this store?  Pick from the shortlist, then remember it.
sellerclaw_run(group="categories", command="suggest",
  body={"store_id": STORE_ID, "product_id": PRODUCT_ID})
sellerclaw_run(group="categories", command="confirm",
  body={"store_id": STORE_ID, "product_id": PRODUCT_ID, "category_id": CATEGORY_ID})

# 2. What does that category demand, and what values are allowed?
sellerclaw_run(group="attributes", command="schema",
  body={"store_id": STORE_ID, "category_external_id": CATEGORY_EXTERNAL_ID})
sellerclaw_run(group="attributes", command="values",
  body={"store_id": STORE_ID, "category_external_id": CATEGORY_EXTERNAL_ID, "attribute": "Brand", "q": "acme"})

# 3. Fill the specifics of drafts that already exist, from each product's own attributes.
sellerclaw_run(group="attributes", command="map",
  positionals={"store_id": STORE_ID}, body={"product_ids": [PRODUCT_ID]})
```

`listings readiness` says whether a product is publishable before you try. Afterwards,
`listing-problems list` is the standing list of everything any channel refused or flagged across all
stores — work it top-down (errors first), and `hide` only what is genuinely dealt with.

## Missing photos

A listing with no image sells nothing and several marketplaces refuse it outright. `media
generate-image` returns a URL in the same turn, which can go straight into an `images` field. Product
photography invented by a model is a picture of something the owner does not sell — use it for
backgrounds, lifestyle scenes and banners, and ask before it stands in for the product itself.

## Watch for

- **Stock sync ≠ publish.** `create` / `publish` create the listing; `sync-stock` only updates
  quantities (and optional price).
- **`withdraw` is not `delete`.** `withdraw` takes a listing off the storefront and can be undone;
  `delete` destroys it — on Etsy the listing, its address and the reviews and favourites on it go
  with it, and re-listing costs a new listing fee. An unqualified "take this off my shop" means
  `withdraw`; only delete when the owner said to delete.
- **Raw fallback:** the `shopify` / `ebay` / `amazon` / `etsy` / `woocommerce` / `wix` /
  `bigcommerce` groups pass raw API calls through when no curated command fits.
