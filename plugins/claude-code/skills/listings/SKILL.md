---
name: listings
description: "Your listings: find one, or see which ones shoppers cannot buy and why."
argument-hint: "[title | SKU | item number | not selling]"
disable-model-invocation: true
---

Show the listings: call `sellerclaw_listings` with the owner's words — do not look anything up first.

- A title, a SKU or a marketplace item number → `query`.
- "Not selling" or "out of stock" → `sale_state`: `["out_of_stock", "not_selling"]` for both.
- A store (its name, or its platform) → `store`.
- No words → no arguments.

Owner's words: $ARGUMENTS
