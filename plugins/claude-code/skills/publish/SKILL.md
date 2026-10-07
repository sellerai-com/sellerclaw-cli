---
name: publish
description: "List a product for sale in one of your stores."
argument-hint: "[product] [store]"
disable-model-invocation: true
---

List a product for sale in one of the owner's stores. Work from the listings guide — `sellerclaw_guide(topic="listings")` — and the catalog guide (`topic="catalog"`) to find the product.

- The product and the store come from the owner's words. No store → ask which, from `sellerclaw_read(group="channels", command="list")`. No product → ask which.
- A marketplace refuses it (category, item specifics, a photo) → fix it as the guide says and send it again.

Owner's words: $ARGUMENTS
