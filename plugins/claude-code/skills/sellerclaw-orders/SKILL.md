---
name: sellerclaw-orders
description: "Use when the user wants to view, fulfill, ship, track, or cancel orders across their SellerClaw stores (Shopify, eBay, Amazon) or the internal SellerClaw order list."
---

# SellerClaw — orders

Finding orders and moving them through fulfillment via `sellerclaw_read` and `sellerclaw_write`. Run
the examples directly; reach for `sellerclaw_describe` only for a command not shown here, or when a call errors on a field.

## Find the order

```text
sellerclaw_read(group="channels", command="list")                                  # store ids
sellerclaw_read(group="orders", command="list", flags={"awaiting_shipment": True})  # no tracking yet, every store
sellerclaw_read(group="orders", command="list", flags={"status": "open"})          # not fulfilled or cancelled yet
sellerclaw_read(group="shopify-orders", command="list", positionals={"store_id": STORE_ID})
sellerclaw_write(group="shopify-orders", command="sync", positionals={"store_id": STORE_ID})  # pull fresh first
```

## Fulfill & ship (Shopify)

```text
# Create a fulfillment. tracking: {number (required), company, url}. line_items: each
# {remote_line_item_id (required), quantity} — omit line_items to fulfill the whole order.
sellerclaw_write(group="shopify-orders", command="create-fulfillment",
  positionals={"store_id": STORE_ID, "order_id": ORDER_ID},
  body={"tracking": {"number": "1Z999AA10123456784", "company": "UPS"}})

# Update tracking on an existing fulfillment (second path arg is the fulfillment id).
sellerclaw_write(group="shopify-orders", command="update-tracking",
  positionals={"store_id": STORE_ID, "fulfillment_id": FULFILLMENT_ID},
  body={"tracking": {"number": "1Z999AA10123456784", "company": "UPS"}})

# Cancel an order
sellerclaw_write(group="shopify-orders", command="cancel",
  positionals={"store_id": STORE_ID, "order_id": ORDER_ID})
```

## Close the SellerClaw order (always, on every channel)

Creating the fulfillment tells the *channel* and the buyer. The SellerClaw order row is closed
separately — do it right after, or the order stays in the seller's open work:

```text
# ORDER_ID: the SellerClaw order id, or the order number the owner quotes (#1001).
sellerclaw_write(group="orders", command="set-shipped", positionals={"order_id": ORDER_ID},
  body={"tracking_number": "1Z999AA10123456784", "tracking_carrier": "UPS"})
```

Every field is optional — an order the channel marked sent without a number is shipped all the same.
Repeating the call is safe. Do **not** close the order with `orders update` instead: that leaves the
status where it was.

## Ship it yourself: buy a courier label

For an order the seller ships themselves (their own stock, an offline supplier's warehouse) and only
when they connected Shippo: `orders get` → `shipping_label_offer.available` says whether a label can
be bought, and `reason` why not. CJ and Amazon FBA orders are shipped by the supplier — no label.

```text
# The rates, with the label drafted from the order — warehouse, address, weight and box.
sellerclaw_read(group="shipping-labels", command="quote", positionals={"order_id": ORDER_ID})
# Change only what is wrong, in millimetres and grams:
sellerclaw_read(group="shipping-labels", command="quote", positionals={"order_id": ORDER_ID},
  body={"parcel": {"weight_grams": 1250}, "signature": "ADULT"})
# Buy by the chosen rate — goes to the owner for approval (money).
sellerclaw_write(group="shipping-labels", command="buy", positionals={"order_id": ORDER_ID},
  body={"rate_id": RATE_ID})
```

Prefer the rate with `buyer_chose: true` (what the buyer paid for), else the cheapest that arrives in
time. A 422 from `quote` lists `details.missing` — ask the owner for exactly that (a missing sender
name goes into `shipping-labels update-sender`). Once bought, the order is marked shipped and the
store gets the tracking: do **not** run `set-shipped` or a channel's fulfillment for it. The label —
file link, tracking, delivery status — is `shipping_label` in `orders get`.

## eBay & Amazon

```text
sellerclaw_read(group="ebay-orders",   command="list", positionals={"store_id": STORE_ID})
sellerclaw_read(group="amazon-orders", command="list", positionals={"store_id": STORE_ID})
```

`ebay-orders` and `amazon-orders` mirror the same flow (fulfill / confirm shipment) — Amazon
distinguishes merchant-fulfilled shipments; `sellerclaw_describe` the confirm command for its fields.

## Watch for

- **Read money elsewhere.** `shopify-finances` / `ebay-finances` are read-only payouts/fees;
  `analytics` for sales. Don't reach for them to change an order.
- An empty `list` / `search` result is a normal "none found", not an error.
