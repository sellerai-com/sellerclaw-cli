---
name: fix-listings
description: "Find out why listings are not selling, and fix them."
argument-hint: "[store]"
disable-model-invocation: true
---

Find out why listings are not selling, and fix what can be fixed.

1. Show them: `sellerclaw_listings(sale_state=["out_of_stock", "not_selling"])`, with `store` if the owner named one (its name, or its platform).
2. Group them by cause — out of stock, refused by the marketplace, hidden or under review — and read the refusals with the listings guide (`sellerclaw_guide(topic="listings")`).
3. Propose the fixes, biggest group first, and apply the ones the owner agrees to.

Owner's words: $ARGUMENTS
