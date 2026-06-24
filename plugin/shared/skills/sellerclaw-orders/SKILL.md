---
name: sellerclaw-orders
description: "Use when the user wants to view, fulfill, ship, track, or cancel orders across their SellerClaw stores (Shopify, eBay, Amazon) or the internal SellerClaw order list."
---

# SellerClaw — orders

Finding orders and moving them through fulfillment via `sellerclaw_run`. Run the examples directly;
reach for `sellerclaw_describe` only for a command not shown here, or when a call errors on a field.

## Find the order

```text
sellerclaw_run(group="channels", command="list")                                  # store ids
sellerclaw_run(group="shopify-orders", command="list", positionals={"store_id": STORE_ID})
sellerclaw_run(group="shopify-orders", command="sync", positionals={"store_id": STORE_ID})  # pull fresh first
```

## Fulfill & ship (Shopify)

```text
# Create a fulfillment. tracking: {number (required), company, url}. line_items: each
# {remote_line_item_id (required), quantity} — omit line_items to fulfill the whole order.
sellerclaw_run(group="shopify-orders", command="create-fulfillment",
  positionals={"store_id": STORE_ID, "order_id": ORDER_ID},
  body={"tracking": {"number": "1Z999AA10123456784", "company": "UPS"}})

# Update tracking on an existing fulfillment (second path arg is the fulfillment id).
sellerclaw_run(group="shopify-orders", command="update-tracking",
  positionals={"store_id": STORE_ID, "fulfillment_id": FULFILLMENT_ID},
  body={"tracking": {"number": "1Z999AA10123456784", "company": "UPS"}})

# Cancel an order
sellerclaw_run(group="shopify-orders", command="cancel",
  positionals={"store_id": STORE_ID, "order_id": ORDER_ID})
```

## eBay & Amazon

```text
sellerclaw_run(group="ebay-orders",   command="list", positionals={"store_id": STORE_ID})
sellerclaw_run(group="amazon-orders", command="list", positionals={"store_id": STORE_ID})
```

`ebay-orders` and `amazon-orders` mirror the same flow (fulfill / confirm shipment) — Amazon
distinguishes merchant-fulfilled shipments; `sellerclaw_describe` the confirm command for its fields.

## Watch for

- **Read money elsewhere.** `shopify-finances` / `ebay-finances` are read-only payouts/fees;
  `analytics` for sales. Don't reach for them to change an order.
- An empty `list` / `search` result is a normal "none found", not an error.
