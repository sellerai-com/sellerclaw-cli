---
name: sellerclaw-listings
description: "Use when the user wants to list, publish, update or withdraw products on their stores through SellerClaw — Shopify, eBay, Amazon, Walmart, WooCommerce, Wix or BigCommerce — change price or stock, or find out why a marketplace refused a listing."
---

# SellerClaw — listings

## Find listings

- `search_listings` finds listings across every store: by text, SKU, store, product, status, or
  whether shoppers can buy them. "What isn't selling?" is `sale_state: ["out_of_stock",
  "not_selling"]` — a live listing nobody can buy still has the status `active`.
- `get_listing` reads one listing with all its variations.
- `list_listing_problems` lists what marketplaces refused or flagged, with the reason.

## Put a catalog product on a store

1. `suggest_category` for the product on that store, then `confirm_category` with the one chosen.
   `search_categories` when the owner names a category.
2. `create_draft_listings` for the store. Write each product's own title and description; pass the
   platform's fields once in `channel` (eBay policy ids from `list_store_policies` and a location
   from `list_store_locations`, unless the store has defaults). On Amazon, find the catalog item
   first with `find_amazon_catalog_item` and confirm it with the owner.
3. Read the job with `get_listing_job`. Drafts that came back short on attributes:
   `fill_listing_attributes`, then `get_category_attributes` / `search_attribute_values` for what is
   still missing, and `update_listings` to set it.
4. `check_listings_ready`, fix what blocks, then `publish_listings` and `get_listing_job` until
   nothing is pending.
5. Open the result: `sellerclaw_listings` with the listing id.

## Change live listings

- Text, images, prices, quantities: `update_listings`, then `publish_listings` to send the edits to
  the marketplace.
- Stock or price by SKU, straight to the marketplace: `update_listing_stock`.
- Off sale: `withdraw_listings` (it can come back). Delete for good only when the owner says so:
  `delete_listings`.
- Changes made on the marketplace directly: `refresh_store_listings`.

## Watch for

- Amazon and Walmart review a listing after it is submitted: `get_publish_status`.
- Publishing and withdrawing take up to 25 listings per job.
- Store defaults (policies, location, lead time) are the owner's choice — ask before
  `update_store_settings`.
