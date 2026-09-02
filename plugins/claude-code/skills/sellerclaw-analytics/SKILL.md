---
name: sellerclaw-analytics
description: "Use when the user asks how the business or a store is doing — sales, revenue, profit, margin, best sellers, what isn't selling, trends by week or month, where buyers are, what's out of stock or needs reordering, how much cash is tied up in inventory, or what needs attention today."
---

# SellerClaw — how the business is doing

Everything here is the `analytics` group, read-only. Run the examples directly; reach for
`sellerclaw_describe` only for a field not shown here, or when a call errors.

## Two things are the same in every command

**The period.** Pick exactly one form — mixing them is an error, not a guess:

| Ask | Flag |
| --- | --- |
| a rolling window ending now | `period`: `last_7d` `last_30d` `last_90d` `this_month` `last_month` `this_year` |
| "how was last week" | `week`: `0` = the last **finished** week, `1` = the one before |
| "how was March" | `month`: `0` = last month, `1` = the month before |
| an exact span | `from` + `to`, both `YYYY-MM-DD`, both ends included |

`last_7d` is a rolling seven days, **not** last week — use `week` when the user means a week.

**The stores.** The positional is a store id, or the literal `all` for every active store. Repeat
`store` in `flags` to pick an arbitrary set. The server recomputes over the combined data, so
**never add up two single-store answers yourself** — totals add, but averages, shares and rankings
do not. Three caveats on an aggregate:

- **The answer is in one currency, and it says which.** Stores that share a currency are reported
  in it; stores that do not are converted to **USD** at today's rate rather than summed at face
  value. `coverage.currency` is what the figures are denominated in, `coverage.source_currencies`
  what they were built from — when those differ, say the numbers were converted. Override with the
  `currency` flag. Stock health carries money too (`lost_revenue_per_day`), so it converts as well.
- **`store_id` is null for an aggregate.** It names a store only when the answer is about exactly
  one; `coverage.store_ids` is always the honest list of what it covers.
- **The same SKU across stores merges into one row.** Right for "what sold"; misleading for stock —
  60 units in each of two stores reads as 120, though neither can ship the other's orders.

## Sales, profit, best sellers

```text
sellerclaw_run(group="channels", command="list")                       # store ids
sellerclaw_run(group="analytics", command="metrics",
  positionals={"store_id": STORE_ID}, flags={"month": 0, "top": 5})    # last month, top 5
sellerclaw_run(group="analytics", command="metrics",
  positionals={"store_id": "all"}, flags={"period": "this_year"})      # whole business, YTD
```

Gives revenue, orders, AOV, trend vs the previous equal window, gross profit and margin, ABC tiers,
sales mix by category, top SKUs by revenue and by profit, and how many listed SKUs sold nothing.

Add `"with_fees": true` for a `net` block — real marketplace fees subtracted (eBay, Shopify, Etsy).
It is a live call per store, one after another, so it is slow; the block is simply absent when a
store's fees can't be read (Amazon and friends). Fees are dated when the platform charged them and
revenue when the order was placed, so on a window of a week or less treat `net_profit` as close
rather than exact.

## Trends, stock, geography, tied-up cash

```text
sellerclaw_run(group="analytics", command="timeseries",
  positionals={"store_id": STORE_ID}, flags={"granularity": "month", "buckets": 12})
sellerclaw_run(group="analytics", command="inventory", positionals={"store_id": STORE_ID})
sellerclaw_run(group="analytics", command="geography", positionals={"store_id": "all"})
sellerclaw_run(group="analytics", command="capital", positionals={"store_id": STORE_ID})
sellerclaw_run(group="analytics", command="operations-digest", positionals={"store_id": STORE_ID})
```

- **timeseries** — revenue/orders per bucket. The period says *which span*, `granularity` how finely
  to cut it (`month: 0` + `granularity: day` charts last month day by day); `buckets` instead fixes
  the count ("the last 12 months").
- **inventory** — what is selling out while still listed, and what to reorder.
- **geography** — which countries and regions the orders go to, and how the mix shifted.
- **capital** — cash tied up in stock, and the slice that hasn't sold in `dead_after` days. No
  period: stock is only ever "as of now". Counts only stock the owner paid for — a dropshipper's
  warehouse comes back apart, as `supplier_stock_units` / `supplier_stock_providers`. So
  `tied_up_value: 0` beside a large supplier figure means "none of your money is on a shelf", not
  "we could not work it out".
- **operations-digest** — one store, right now: unshipped orders, stockouts, and on eBay also
  parcels, disputes and account health. Best answer to "anything urgent today".

## Watch for

- **Say when the data is incomplete.** Every answer carries `coverage`. `history_status: "syncing"`
  means the store is still importing its sales history — the figures are real but partial, so say so
  instead of presenting them as the full picture.
- **Gross is not net.** Profit is revenue minus cost of goods; marketplace fees are not in it unless
  you passed `with_fees`. And cost exists only for supplier-sourced products, so when
  `cost_coverage_pct` is low, call it "profit on sourced products", not whole-store profit.
- **Never invent a figure.** Restate what came back; if a field is `null` (AOV with zero orders,
  margin with no cost data), say it isn't available rather than printing a zero.
- **`report` is delivery, not data.** It queues a narrated report that reaches the owner later. When
  you need numbers to answer now, use `metrics`.
