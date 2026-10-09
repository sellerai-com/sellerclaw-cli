---
name: sellerclaw-orders
description: "Use when the user wants to find, fulfill, ship, track or cancel orders across their SellerClaw stores, or place the supplier order behind a dropshipped sale."
---

# SellerClaw — orders

## Find the order

- `sellerclaw_orders` shows the order board, or one order by the number the owner quotes. The board
  is a queue, longest wait first; pass `sort: "newest"` for the latest orders.
- `list_orders` with `awaiting_shipment: true` is the shipping queue; `search_orders` finds one by
  number, buyer or item. They hold open orders; `list_store_orders` reads older and shipped ones
  from the marketplace.
- `get_order` reads one order in full: items, buyer, address, supplier order, tracking.

## Ship it

1. `ship_order` with the tracking number and carrier sends it to the marketplace, which notifies the
   buyer. The same tool works on every platform; Amazon and eBay need the carrier's name. Pass
   `line_items` only to ship part of the order.
2. `mark_order_shipped` closes it in SellerClaw — always, right after, or the order stays in the
   owner's open work. If it shipped on the marketplace by hand, this is the only step.
3. Open `sellerclaw_orders` with the order to show the result.

## Dropshipping: buy it from the supplier

1. `check_supplier_stock` and `quote_supplier_shipping` to the buyer's address.
2. `create_supplier_order` with the buyer's address and the order's id, then
   `confirm_supplier_order`, then `pay_supplier_order` (it may wait for the owner's approval).
3. `get_supplier_order` for its status and, once shipped, the tracking to pass to `ship_order`.

If the marketplace did not send the buyer's address, fill it in with `update_order` before buying.

## Cancel

`cancel_order` cancels on the marketplace (Shopify, Wix, WooCommerce), optionally refunding and
restocking. A supplier order placed for it is cancelled separately with `cancel_supplier_order`.
