---
name: orders
description: "Your orders, or one order by its number, buyer or item."
argument-hint: "[#order | buyer | SKU | status | store]"
disable-model-invocation: true
---

Show the orders: call `sellerclaw_orders` with the owner's words as they are — do not look anything up first.

- One order (#1001, a marketplace order id) → `order`.
- A status (new, approved, purchased, shipped, fulfilled, cancelled, failed) → `status`.
- A store (its name, or its platform) → `store`, with the rest of the words as above.
- Anything else (a buyer, an email, a SKU, an item) → `query`.
- No words → no arguments: the whole board.

Owner's words: $ARGUMENTS
