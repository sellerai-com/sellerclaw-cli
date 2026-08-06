---
name: sellerclaw-suppliers
description: "Use when the user wants to find products at a supplier, check supplier stock or shipping cost, or place and pay for a dropship order through SellerClaw."
---

# SellerClaw — suppliers & dropshipping

Finding supplier products, checking stock and shipping, and placing dropship orders via
`sellerclaw_run`. Run the examples directly; reach for `sellerclaw_describe` only for a command not
shown here, or when a call errors on a field. Every command takes the **provider slug** (e.g. `cj`)
as its first positional.

## Find the product

```text
sellerclaw_run(group="suppliers", command="list-accounts")                       # which providers are connected
sellerclaw_run(group="suppliers", command="search-products",
  positionals={"provider": "cj"}, flags={"query": "wireless mouse", "page_size": 20})

# The user pasted a supplier link? Turn it into ids first.
sellerclaw_run(group="suppliers", command="resolve-url", flags={"url": "https://…"})
```

## Read one product properly

```text
# One call for the whole card: product + variants + a shipping quote. Prefer it over chaining
# get-product / get-variants / quote-shipping by hand.
sellerclaw_run(group="suppliers", command="inspect",
  positionals={"provider": "cj", "product_id": PRODUCT_ID},
  flags={"country": "US", "zip": "10001", "max_variants": 20})
```

## Stock and shipping before you commit

```text
# Every variant's stock in one call, split per warehouse.
sellerclaw_run(group="suppliers", command="check-stock-by-product",
  positionals={"provider": "cj", "product_id": PRODUCT_ID})

# "What would shipping cost to this buyer?" — country + zip is enough.
sellerclaw_run(group="suppliers", command="quote-shipping", positionals={"provider": "cj"},
  body={"items": [{"variant_id": VARIANT_ID, "quantity": 1}],
        "destination": {"country_code": "US", "zip_code": "10001"}})
```

## Place a dropship order

```text
sellerclaw_run(group="suppliers", command="create-order", positionals={"provider": "cj"},
  body={"items": [{"variant_id": VARIANT_ID, "quantity": 1, "shipping_method": "CJPacket Ordinary"}],
        "shipping_address": {"country_code": "US", "province": "NY", "city": "New York",
                             "zip_code": "10001", "address_line": "5 Main St",
                             "full_name": "Jane Buyer", "phone": "+12125550100"},
        "internal_order_id": SELLERCLAW_ORDER_ID})

sellerclaw_run(group="suppliers", command="confirm-order", positionals={"provider": "cj", "order_id": ORDER_ID})
sellerclaw_run(group="suppliers", command="pay-order",     positionals={"provider": "cj", "order_id": ORDER_ID})
sellerclaw_run(group="suppliers", command="get-tracking",  positionals={"provider": "cj", "order_id": ORDER_ID})
```

`get-balance` tells you whether paying will go through; `get-order` re-reads one order's state.

## Watch for

- **Ordering is three steps.** `create-order` alone reserves nothing useful — confirm, then pay, or
  the supplier never ships it.
- **Pass `internal_order_id` when the purchase fulfills a SellerClaw order.** It links the two and
  makes the call idempotent, so a retry cannot buy the same goods twice.
- **The warehouse is chosen for you** — the cheapest in-stock one nearest the buyer, which is often
  not China. Only pass `from_country_code` when the owner wants a specific origin.
- **Spending money is the owner's call.** Confirm the total (product + shipping) with them before
  `pay-order` unless they already told you to buy.
- To sell a supplier product rather than just buy it, add it to the catalog first — see the
  `catalog` guide (`source-from-supplier`).
