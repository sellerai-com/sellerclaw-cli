# SellerClaw — suppliers & dropshipping

Finding supplier products, checking stock and shipping, and placing dropship orders via
`sellerclaw_read` and `sellerclaw_write`. Run the examples directly; reach for `sellerclaw_describe` only for a command not
shown here, or when a call errors on a field. Every command takes the **provider slug** (e.g. `cj`)
as its first positional.

## Find the product

```text
sellerclaw_read(group="suppliers", command="list-accounts")                       # which providers are connected
sellerclaw_read(group="suppliers", command="search-products",
  positionals={"provider": "cj"}, flags={"query": "wireless mouse", "page_size": 20})

# The user pasted a supplier link? Turn it into ids first.
sellerclaw_read(group="suppliers", command="resolve-url", flags={"url": "https://…"})
```

**Two different countries live in this group — keep them apart.** `--stocked-in` on a search says
where the goods already **sit** (a warehouse filter); `--to-country` on `inspect` and `destination`
on the shipping commands say where they are **going**. Answers about origin come back as
`stock.by_country` and `shipping.from_country_code`.

**Asking for a kind of product? Use the category, not the keyword.** A supplier catalogue is
enormous and its search matches product *names*, so "leather belt" comes back full of belted dresses
and pet leashes and no re-phrasing separates them. Find the category once, then filter by it:

```text
sellerclaw_read(group="suppliers", command="categories",
  positionals={"provider": "cj"}, flags={"search": "belt"})     # → id of "…> Men's Accessories > Belts"

sellerclaw_read(group="suppliers", command="search-products",
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
sellerclaw_read(group="suppliers", command="inspect-batch", positionals={"provider": "cj"},
  body={"product_ids": [PID_1, PID_2, PID_3],
        "destination": {"country_code": "US", "zip_code": "10001"}})

# One product, with its description and full variant list.
sellerclaw_read(group="suppliers", command="inspect",
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
sellerclaw_read(group="suppliers", command="check-stock-by-product",
  positionals={"provider": "cj", "product_id": PRODUCT_ID})

# "What would shipping cost to this buyer?" — country + zip is enough, no address, no method.
sellerclaw_read(group="suppliers", command="quote-shipping", positionals={"provider": "cj"},
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
sellerclaw_write(group="suppliers", command="create-order", positionals={"provider": "cj"},
  body={"items": [{"variant_id": VARIANT_ID, "quantity": 1, "shipping_method": "CJPacket Ordinary"}],
        "shipping_address": {"country_code": "US", "province": "NY", "city": "New York",
                             "zip_code": "10001", "address_line": "5 Main St",
                             "full_name": "Jane Buyer", "phone": "+12125550100"},
        "internal_order_id": SELLERCLAW_ORDER_ID})

sellerclaw_write(group="suppliers", command="confirm-order", positionals={"provider": "cj", "order_id": ORDER_ID})
sellerclaw_write(group="suppliers", command="pay-order",     positionals={"provider": "cj", "order_id": ORDER_ID})
sellerclaw_read(group="suppliers", command="get-tracking",  positionals={"provider": "cj", "order_id": ORDER_ID})
```

`get-balance` tells you whether paying will go through; `get-order` re-reads one order's state.

Calling a purchase back — the owner cancelled, or shipped it themselves:

```text
sellerclaw_write(group="suppliers", command="cancel-order",
  positionals={"provider": "cj", "order_id": ORDER_ID},
  body={"internal_order_id": SELLERCLAW_ORDER_ID})
```

## Warehouses of the owner's own suppliers

A supplier with no integration (its rows in `list-accounts` have `"platform": "offline"`) leaves
"where do the goods ship from?" to us, so it can have warehouses — each catalog product of it ships
from one. CJ and Amazon have none: they choose the origin themselves.

```text
sellerclaw_read(group="suppliers", command="list-warehouses", positionals={"supplier_id": SUPPLIER_ID})
sellerclaw_write(group="suppliers", command="create-warehouse", positionals={"supplier_id": SUPPLIER_ID},
  body={"name": "Main", "country_code": "US", "postal_code": "10001"})
sellerclaw_write(group="catalog", command="set-supplier-warehouse", positionals={"product_id": PRODUCT_ID},
  body={"supplier_warehouse_id": WAREHOUSE_ID})
```

The first warehouse becomes the warehouse of every product of that supplier (`products` in the
answer). Once there are several, binding a product to the supplier — `catalog set-supplier`,
`catalog create`, `price-list create-products` — needs `supplier_warehouse_id`, and is refused with
the list otherwise: ask the owner which one, never pick. A warehouse products ship from cannot be
deleted until they are moved.

### Shipping rates

A warehouse can be given what it charges to ship one unit to a country, as weight bands — "up to
500 g costs 5.00, up to 1 kg 8.00". Prices are in the supplier's currency (set one with
`update-account` first if the supplier has none). Setting a country replaces its whole table.

```text
sellerclaw_write(group="suppliers", command="set-warehouse-rates",
  positionals={"supplier_id": SUPPLIER_ID, "warehouse_id": WAREHOUSE_ID, "country_code": "US"},
  body={"bands": [{"max_weight_grams": 500, "price": "5.00"}, {"max_weight_grams": 1000, "price": "8.00"}]})
```

A store selling to that country then prices those products' shipping with the rate for the parcel
(the product's weight plus its box's own weight) instead of the product's own `shipping_cost`; live
listings follow within an hour. With no rate for the country, no product weight, or a parcel heavier
than the last band, the product's own `shipping_cost` is used — `catalog get` says which and why in
`warehouse_shipping`. Enter the rates from the supplier's own price table; never invent them.

## Watch for

- **Ordering is three steps.** `create-order` alone reserves nothing useful — confirm, then pay, or
  the supplier never ships it.
- **Pass `internal_order_id` when the purchase fulfills a SellerClaw order.** It links the two and
  makes the call idempotent, so a retry cannot buy the same goods twice.
- **`cancel-order` calls off the purchase, not the sale.** The buyer keeps their order and their
  goods — cancelling that is a separate decision, made on the order itself. Pass
  `internal_order_id` so the SellerClaw order stops pointing at a purchase that no longer exists;
  without it the owner is left looking at a payment page for goods nobody will ship.
- **An order from the owner's own shop names its delivery.** Its `shipping_choice.parcels[]` holds,
  per supplier, the `service` the buyer paid for and where it `ships_from`: pass them as
  `shipping_method` and `from_country_code` — together, or the parcel leaves from the default
  warehouse.
- **Otherwise the warehouse is chosen for you** — the cheapest in-stock one nearest the buyer, which
  is often not China. Only pass `from_country_code` when the owner wants a specific origin.
- **Spending money is the owner's call.** Confirm the total (product + shipping) with them before
  `pay-order` unless they already told you to buy.
- To sell a supplier product rather than just buy it, add it to the catalog first — see the
  `catalog` guide (`source-from-supplier`).
