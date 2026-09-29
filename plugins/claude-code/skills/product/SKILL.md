---
name: product
description: "A catalog product with its supplier, cost, stock and every store it is listed in."
argument-hint: "[name | SKU]"
disable-model-invocation: true
---

Show a catalog product: call `sellerclaw_products` with the owner's words as `query` — do not look it up first. No words → no arguments. Nothing found in the catalog → `sellerclaw_listings` with the same `query`.

Owner's words: $ARGUMENTS
