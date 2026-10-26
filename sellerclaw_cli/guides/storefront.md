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
individual ones. How much of a product page the photos take is `theme`'s `product_photo_size`
(`small`, `medium`, `large`, or `auto` for the layout's own) — the way to make them smaller or bigger. Images live in `sellercart-media` — `add` copies one in by URL and returns a
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

## Discounts — a percentage off, for a period

```text
sellerclaw_read(group="sellercart-discounts", command="list")
sellerclaw_write(group="sellercart-discounts", command="set",
  body={"target": "shop", "percent": 20, "ends_at": "2026-12-01T00:00:00-05:00"})
sellerclaw_write(group="sellercart-discounts", command="set",
  body={"target": "category", "category": "Mugs", "percent": 30, "label": "Black Friday",
        "starts_at": "2026-11-27T00:00:00-05:00", "ends_at": "2026-11-30T00:00:00-05:00"})
sellerclaw_write(group="sellercart-discounts", command="set",
  body={"target": "product", "listing_id": LISTING_ID, "percent": 15, "ends_at": "..."})
sellerclaw_write(group="sellercart-discounts", command="remove", positionals={"discount_id": ID})
```

One `set` for every target: `shop`, a `category` by the shop's own name for it, a `product` by its
`listing_id` (every variant), a `variant` by its `variation_id`. A whole percent off the regular price,
rounded down to the tenth; the regular price keeps following cost and markup, and the sale follows
it. Buyers see the new price, the regular one struck through and a badge with the percent. It
applies from `starts_at` (now when left out) until `ends_at` — the first moment it no longer applies —
with no publish. Times carry the owner's UTC offset; ask for their time zone if you do not know it.

Where several cover one variant, the narrowest wins (variant > product > category > shop), and of two
of one kind the later-started one. Run one only when the owner asks for it, and never raise a price
just before discounting it. Tell the owner the answer's `below_cost` (variants that now sell for less
than they cost) and `warnings`; the discount stands. `sellercart-products list` names what sells at a
discount now in `sales`. `remove` stops a running discount at once.

## Getting paid — check this before promising a working shop

```text
sellerclaw_read(group="sellercart-payouts", command="status")
sellerclaw_write(group="sellercart-payouts", command="connect")    # Stripe link for the owner
sellerclaw_write(group="sellercart-payouts", command="refresh")    # after they say they finished
```

Checkout opens only when Stripe is connected and cleared **and** delivery is set up (`delivers`).
Stripe onboarding is identity verification — the owner does it themselves and nobody can do it for
them.

## Delivery — who prices each parcel, zones, and the seller's own methods

```text
sellerclaw_read(group="sellercart-delivery", command="list")
sellerclaw_write(group="sellercart-delivery", command="set-zone", positionals={"zone": "North America"},
  body={"countries": ["US", "CA"], "free_over": 75})
sellerclaw_write(group="sellercart-delivery", command="set-method",
  positionals={"zone": "North America", "method": "Standard"},
  body={"price": 6.95, "days_min": 3, "days_max": 5,
        "weight_bands": [{"up_to_grams": 500, "price": 4}, {"up_to_grams": 2000, "price": 7}, {"price": 12}],
        "origins": [{"country": "CN", "price": 3, "days_min": 10, "days_max": 20}]})
sellerclaw_write(group="sellercart", command="update",
  body={"delivery_margin_percent": 10, "delivery_margin_amount": 1})
sellerclaw_write(group="sellercart", command="update", body={"shippo_rates": True})   # owner's yes only
```

An order is split into parcels by who sends them, and the buyer picks an option for each:

- **CJ and Amazon** goods go only with the supplier, at its price: CJ's cheapest ("Standard") and its
  fastest ("Express", when really faster), Amazon's own speeds. Nothing to set for them.
- **The seller's own goods** go at their Shippo account's live rates when the shop agreed to it
  (`shippo_rates: true`) and the product has a weight and a box — otherwise at the zone's methods.
  `list` shows the `shippo` state and a `breakdown` of the shelf, with the products Shippo can't
  price for want of a weight (`no_weight`), a box (`no_box`), or a sender address in the country
  their warehouse is in (`abroad` — Shippo never prices goods kept abroad from an address at home).

A zone is a group of countries; a country is in one zone only, and `everywhere_else: true` makes a
zone for every country no other zone names. A method prices only the seller's own goods: `price`
(required, `0` is free), optional `weight_bands` (parcel weight = goods + box, or the box by volume
when that weighs more; the last step has no `up_to_grams`), the promised `days_min`/`days_max`, and
`origins` — its own line for parcels leaving from a country. Ask the owner which countries and what
each option costs — never invent a delivery price.

`free_over` makes a parcel's cheapest option free from that goods total, counted per parcel. The
margin (`delivery_margin_percent`, `delivery_margin_amount` per parcel) rides only on CJ's, Amazon's
and Shippo's prices, and only when the buyer pays for that delivery. `list` says whether product
prices already include the supplier's delivery (`shipping_included_in_price`): then a supplier's
parcel charges only the cost beyond that. Read its `warnings` out to the owner.

Changes reach buyers at once, with no publish. Fields left out of `set-zone` / `set-method` keep
their value; `null` clears one (`free_over`, the days); a list sent replaces the whole list.

## Going live

```text
sellerclaw_write(group="sellercart", command="publish", body={"summary": "New home page and header menu"})
```

Publishing is gated: it answers `pending_approval` or, on a connection the owner has set to not ask,
`approved_queued`. Write a `summary` that says what actually changed — it is what they see, and what
lands in the shop's version history (`versions`). `unpublish` closes the shop and is gated the same
way.

While closed, `status` carries `closed_at`, `closed_note` and `reopens_on`. Buyers see a temporarily
closed page and can still write to the shop; its basket and checkout refuse orders. Close with
`sellerclaw sellercart unpublish --buyer-note "On holiday" --reopens-on 2026-11-03`. On a closed
shop the same command changes the notice under approval: a field left out keeps its value, `null`
clears it. The date is shown only and never opens the shop automatically. `publish` reopens it without requiring a custom domain; Stripe must still
be verified.

A shop opens only on a domain the owner owns, once that domain is live: until then the first
`publish` answers `domain_required`. Connect the domain early (below) — DNS takes time.

## Buyers' messages

Command `sellerclaw sellercart-messages list --waiting` lists conversations waiting for an answer.
Command `sellerclaw sellercart-messages get <conversation_id>` reads every message and attachment
metadata. Neither clears the owner's unread mark.

Command `sellerclaw sellercart-messages reply <conversation_id> --text "<answer>"` proposes an answer
under the owner's `CUSTOMER_REPLY` policy. `pending_approval` waits for the owner;
`approved_queued` means the answer is going out from the shop's address. `reply_already_pending`
means an answer is already waiting: do not propose another. If the owner answers first, the pending
agent answer stays unsent.

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
