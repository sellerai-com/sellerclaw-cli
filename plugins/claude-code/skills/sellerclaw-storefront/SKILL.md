---
name: sellerclaw-storefront
description: "Use when the user wants to work on their own SellerCart storefront — create the shop, change its look, pages, menus or images, put products on its shelves, set delivery and Stripe payouts, connect a domain they own, preview it, or publish it live."
---

# SellerClaw — storefront (SellerCart)

The owner's own shop: the one storefront that is ours end to end, at `<slug>.sellercart.shop` or a
domain they own. One shop per seller. Everything below is `sellerclaw_read` or
`sellerclaw_write`; run the examples directly.

Always start by reading what already exists — a shop, a draft, or nothing at all:

```text
sellerclaw_read(group="sellercart", command="status")
```

## Creating one

```text
sellerclaw_read(group="sellercart", command="options")                                  # suffix, currencies, languages
sellerclaw_read(group="sellercart", command="check-slug", flags={"slug": "acme-tools"})  # free?
sellerclaw_write(group="sellercart", command="create",
  body={"name": "Acme Tools", "slug": "acme-tools", "currency": "USD", "language": "en"})
```

`create` also makes the shop's sales channel and its default pages (home, catalog, about, delivery,
returns, contacts) as drafts. The address and the currency are the owner's to choose — propose, don't
pick for them. `markup_percent` is what every price is computed from: their margin, so never a number
you invented.

## The draft rule, and how to look before you leap

On a live shop **every edit waits in the draft** until it is published — buyers keep seeing the old
version. That is a feature: build the whole change, look at it, then publish once. Products are the
exception: each goes on sale when it is published itself (below), not with the shop.

```text
sellerclaw_read(group="sellercart", command="changes")      # what the draft would change, item by item
sellerclaw_read(group="sellercart", command="preview")      # secret link for the owner to look
sellerclaw_read(group="sellercart", command="screenshot", body={"page": "home"})   # look at it yourself
```

Take the screenshot before telling the owner it looks good. `discard` throws the draft away and
cannot be undone — only ever when they ask for it in so many words.

## Look and feel

```text
sellerclaw_read(group="sellercart", command="presets")                      # ready-made looks
sellerclaw_write(group="sellercart", command="apply-preset", body={"preset": PRESET_ID})
sellerclaw_write(group="sellercart", command="theme", body={"accent": "#0f7b6c"})
```

`apply-preset` overwrites every style token (the logo and favicon survive); `theme` patches
individual ones. Images live in `sellercart-media` — `add` copies one in by URL and returns a
permanent link, which is what a block or a theme field should point at, never someone else's server.

## Pages, blocks and navigation

```text
sellerclaw_read(group="sellercart", command="blocks")                       # every block type + its props
sellerclaw_read(group="sellercart-pages", command="get", positionals={"slug": "home"})
sellerclaw_write(group="sellercart-pages", command="update",
  positionals={"slug": "home"}, body={"layout": [ ... ]})
sellerclaw_write(group="sellercart-menus", command="update",
  positionals={"location": "header"}, body={"items": [{"label": "Catalog", "href": "/catalog"}]})
```

Read `blocks` before writing a page: a block type that is not in that list cannot render. Both
`layout` and menu `items` **replace the whole list** — send back everything you mean to keep.

## Products on the shelf

```text
sellerclaw_write(group="sellercart-products", command="add", body={"product_ids": [PRODUCT_ID]})
sellerclaw_write(group="listings", command="bulk-publish", positionals={"store_id": STORE_ID},
  body={"kind": "publish", "listing_ids": [LISTING_ID]})
sellerclaw_read(group="sellercart-products", command="list")
sellerclaw_write(group="sellercart-products", command="seo",
  positionals={"reference": PRODUCT_REF}, body={"title": "...", "description": "..."})
```

Products come from the owner's catalog, one listing per variation, priced from the shop's markup over
cost unless `prices` says otherwise. `add` stages them as drafts, which no one sees — not buyers, not
the preview; putting a product on the shop ends with `bulk-publish` on the shop's `store_id`
(`channels list`). That publish needs no approval and does not open the shop: on a shop not yet open
the product shows in the preview and reaches buyers when the shop opens.

The list answers **one entry per product** — its `listing_id` is what a publish, a
`listings bulk-update` and a withdraw take, and `variations[]` inside it names each variation by its
own id with its sku and stock. `remove` takes that **variation's own id** and
takes just that size off, reversibly; `seo` takes the **listing's** id (or the catalog product's) —
those words speak for the whole product. `delete` is not reversible, so only on an explicit word,
and it takes the listing's id too: the whole product goes.

## Getting paid — check this before promising a working shop

```text
sellerclaw_read(group="sellercart-payouts", command="status")
sellerclaw_write(group="sellercart-payouts", command="connect")    # Stripe link for the owner
sellerclaw_write(group="sellercart-payouts", command="refresh")    # after they say they finished
```

Checkout opens only when Stripe is connected and cleared **and** delivery is set up (`delivers`).
Stripe onboarding is identity verification — the owner does it themselves and nobody can do it for
them.

## Delivery — zones, and the methods priced in each

```text
sellerclaw_read(group="sellercart-delivery", command="list")
sellerclaw_write(group="sellercart-delivery", command="set-zone", positionals={"zone": "North America"},
  body={"countries": ["US", "CA"], "free_over": 75})
sellerclaw_write(group="sellercart-delivery", command="set-method",
  positionals={"zone": "North America", "method": "Standard"}, body={"price": 0})
sellerclaw_write(group="sellercart-delivery", command="set-method",
  positionals={"zone": "North America", "method": "Express"},
  body={"price": 15, "calculated": True, "pick": "fastest", "extra_percent": 10})
```

A zone is a group of countries priced alike; a country is in one zone only, and
`everywhere_else: true` makes a zone for every country no other zone names. A zone delivers nowhere
until it has a method. Ask the owner which countries and what each option costs — never invent a
delivery price.

- **Fixed** method: the buyer pays `price`, raised to the real delivery cost when that is higher —
  the seller never pays for delivery. `price: 0` is free delivery.
- **Calculated** method: the buyer pays the real cost from the supplier (CJ, Amazon, Shippo, the
  warehouse's rates) plus `extra_percent` / `extra_amount`, and `price` when no cost can be had.
- `pick` is the supplier service the method stands for — `cheapest` or `fastest` — and the one to buy
  when the order is placed. `free_over` makes the zone's cheapest method free from that goods total.
- `list` says whether product prices already include the supplier's delivery
  (`shipping_included_in_price`): then a method charges only the cost beyond that. Read its
  `warnings` out to the owner.

Changes reach buyers at once, with no publish. Fields left out of `set-zone` / `set-method` keep
their value; `null` clears one (`free_over`, the days).

## Going live

```text
sellerclaw_write(group="sellercart", command="publish", body={"summary": "New home page and header menu"})
```

Publishing is gated: it answers `pending_approval` or, on a connection the owner has set to not ask,
`approved_queued`. Write a `summary` that says what actually changed — it is what they see, and what
lands in the shop's version history (`versions`). `unpublish` closes the shop and is gated the same
way.

A shop opens only on a domain the owner owns, once that domain is live: until then the first
`publish` answers `domain_required`. Connect the domain early (below) — DNS takes time.

## A domain they own

```text
sellerclaw_write(group="sellercart-domain", command="connect", body={"hostname": "shop.acme.com"})
sellerclaw_write(group="sellercart-domain", command="check")     # after they added the DNS record
```

Read the returned `dns_records` out **verbatim** — name, type and value. DNS takes minutes to hours,
so a domain still pending is waiting, not broken.

## Afterwards

`sellercart traffic` is the shop's own counter: visitors, what they looked at, where they came from
and what each source actually sold. `sellercart-products seo` and `store-audit onpage` are where a
shop nobody finds gets fixed.

## Watch for

- **Draft vs live.** `sellercart-products list` shows what a buyer sees, so a shelf staged on an
  unpublished draft reads as empty. Pass the status flag rather than concluding nothing is there.
- **The markup is the owner's margin.** Propose a number, never choose one.
- **Deleting an image leaves a hole.** Nothing checks whether a page still points at it — look at the
  pages first, or screenshot afterwards.
- **`discard` and `delete` are the irreversible pair.** Everything else here can be walked back.
