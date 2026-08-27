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

**Two different countries live in this group — keep them apart.** `--stocked-in` on a search says
where the goods already **sit** (a warehouse filter); `--to-country` on `inspect` and `destination`
on the shipping commands say where they are **going**. Answers about origin come back as
`stock.by_country` and `shipping.from_country_code`.

**Asking for a kind of product? Use the category, not the keyword.** A supplier catalogue is
enormous and its search matches product *names*, so "leather belt" comes back full of belted dresses
and pet leashes and no re-phrasing separates them. Find the category once, then filter by it:

```text
sellerclaw_run(group="suppliers", command="categories",
  positionals={"provider": "cj"}, flags={"search": "belt"})     # → id of "…> Men's Accessories > Belts"

sellerclaw_run(group="suppliers", command="search-products",
  positionals={"provider": "cj"}, flags={"category": CATEGORY_ID, "sort": "listings", "order_by": "desc"})
```

`query` is optional once `category` is set — that browses the category whole, sorted by how many
shops already sell each item. Rows whose `is_searchable` is false are branches to browse into
(`flags={"parent": "…"}`), not ids to filter by. Add `country` only to *narrow* a result set you
already have: it drops everything without a warehouse in that country, which for dropship goods is
most of the catalogue.

## Read the candidates — one call for the whole shortlist

```text
# Several products at once: price, per-warehouse stock and shipping for each. This is the one to
# reach for after a search. Up to 20 ids.
sellerclaw_run(group="suppliers", command="inspect-batch", positionals={"provider": "cj"},
  body={"product_ids": [PID_1, PID_2, PID_3],
        "destination": {"country_code": "US", "zip_code": "10001"}})

# One product, with its description and full variant list.
sellerclaw_run(group="suppliers", command="inspect",
  positionals={"provider": "cj", "product_id": PRODUCT_ID},
  flags={"to_country": "US", "to_zip": "10001", "max_variants": 20})
```

**Never loop a per-product command over a shortlist.** Ten `inspect` calls cost ten round trips
where `inspect-batch` costs one, and each round trip re-sends everything read so far.

Both carry `stock` (total plus a per-country split) — the same figure `check-stock-by-product`
returns, so there is nothing to ask for afterwards. `inspect-batch` leaves out descriptions,
attributes and variant lists unless `include` names them; ask for those once a candidate is picked.

## Stock and shipping on their own

```text
# Every variant's stock for ONE product, split per warehouse.
sellerclaw_run(group="suppliers", command="check-stock-by-product",
  positionals={"provider": "cj", "product_id": PRODUCT_ID})

# "What would shipping cost to this buyer?" — country + zip is enough, no address, no method.
sellerclaw_run(group="suppliers", command="quote-shipping", positionals={"provider": "cj"},
  body={"items": [{"variant_id": VARIANT_ID, "quantity": 1}],
        "destination": {"country_code": "US", "zip_code": "10001"}})
```

**A quote with no methods is an answer, not a bad request.** Every shipping reply is
`{"quotes": [...], "unavailable": ...}`. When `unavailable.retryable` is `false` — an oversized item
the supplier will not carry, an id it does not know — that is final: say so and move on. Changing
the shipping method or the address will not produce a price, and the supplier is never sent a
method on a quote anyway.

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

Calling a purchase back — the owner cancelled, or shipped it themselves:

```text
sellerclaw_run(group="suppliers", command="cancel-order",
  positionals={"provider": "cj", "order_id": ORDER_ID},
  body={"internal_order_id": SELLERCLAW_ORDER_ID})
```

## Watch for

- **Ordering is three steps.** `create-order` alone reserves nothing useful — confirm, then pay, or
  the supplier never ships it.
- **Pass `internal_order_id` when the purchase fulfills a SellerClaw order.** It links the two and
  makes the call idempotent, so a retry cannot buy the same goods twice.
- **`cancel-order` calls off the purchase, not the sale.** The buyer keeps their order and their
  goods — cancelling that is a separate decision, made on the order itself. Pass
  `internal_order_id` so the SellerClaw order stops pointing at a purchase that no longer exists;
  without it the owner is left looking at a payment page for goods nobody will ship.
- **The warehouse is chosen for you** — the cheapest in-stock one nearest the buyer, which is often
  not China. Only pass `from_country_code` when the owner wants a specific origin.
- **Spending money is the owner's call.** Confirm the total (product + shipping) with them before
  `pay-order` unless they already told you to buy.
- To sell a supplier product rather than just buy it, add it to the catalog first — see the
  `catalog` guide (`source-from-supplier`).
