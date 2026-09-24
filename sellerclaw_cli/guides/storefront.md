# SellerClaw — storefront (SellerCart)

The owner's own shop: the one storefront that is ours end to end, at `<slug>.sellercart.shop` or a
domain they own. One shop per seller. Everything below is `sellerclaw_run`; run the examples
directly.

Always start by reading what already exists — a shop, a draft, or nothing at all:

```text
sellerclaw_run(group="sellercart", command="status")
```

## Creating one

```text
sellerclaw_run(group="sellercart", command="options")                                  # suffix, currencies, languages
sellerclaw_run(group="sellercart", command="check-slug", flags={"slug": "acme-tools"})  # free?
sellerclaw_run(group="sellercart", command="create",
  body={"name": "Acme Tools", "slug": "acme-tools", "currency": "USD", "language": "en"})
```

`create` also makes the shop's sales channel and its default pages (home, catalog, about, delivery,
returns, contacts) as drafts. The address and the currency are the owner's to choose — propose, don't
pick for them. `markup_percent` is what every price is computed from: their margin, so never a number
you invented.

## The draft rule, and how to look before you leap

On a live shop **every edit waits in the draft** until it is published — buyers keep seeing the old
version. That is a feature: build the whole change, look at it, then publish once.

```text
sellerclaw_run(group="sellercart", command="changes")      # what the draft would change, item by item
sellerclaw_run(group="sellercart", command="preview")      # secret link for the owner to look
sellerclaw_run(group="sellercart", command="screenshot", body={"page": "home"})   # look at it yourself
```

Take the screenshot before telling the owner it looks good. `discard` throws the draft away and
cannot be undone — only ever when they ask for it in so many words.

## Look and feel

```text
sellerclaw_run(group="sellercart", command="presets")                      # ready-made looks
sellerclaw_run(group="sellercart", command="apply-preset", body={"preset": PRESET_ID})
sellerclaw_run(group="sellercart", command="theme", body={"accent": "#0f7b6c"})
```

`apply-preset` overwrites every style token (the logo and favicon survive); `theme` patches
individual ones. Images live in `sellercart-media` — `add` copies one in by URL and returns a
permanent link, which is what a block or a theme field should point at, never someone else's server.

## Pages, blocks and navigation

```text
sellerclaw_run(group="sellercart", command="blocks")                       # every block type + its props
sellerclaw_run(group="sellercart-pages", command="get", positionals={"slug": "home"})
sellerclaw_run(group="sellercart-pages", command="update",
  positionals={"slug": "home"}, body={"layout": [ ... ]})
sellerclaw_run(group="sellercart-menus", command="update",
  positionals={"location": "header"}, body={"items": [{"label": "Catalog", "href": "/catalog"}]})
```

Read `blocks` before writing a page: a block type that is not in that list cannot render. Both
`layout` and menu `items` **replace the whole list** — send back everything you mean to keep.

## Products on the shelf

```text
sellerclaw_run(group="sellercart-products", command="add", body={"product_ids": [PRODUCT_ID]})
sellerclaw_run(group="sellercart-products", command="list")
sellerclaw_run(group="sellercart-products", command="seo",
  positionals={"reference": PRODUCT_REF}, body={"title": "...", "description": "..."})
```

Products come from the owner's catalog, one listing per variation, priced from the shop's markup over
cost unless `prices` says otherwise. The list answers **one entry per product** — its `listing_id`
is what a publish, a `listings bulk-update` and a withdraw take, and `variations[]` inside it names
each variation by its own id with its sku and stock. `remove` takes that **variation's own id** and
takes just that size off, reversibly; `seo` takes the **listing's** id (or the catalog product's) —
those words speak for the whole product. `delete` is not reversible, so only on an explicit word,
and it takes the listing's id too: the whole product goes.

## Getting paid — check this before promising a working shop

```text
sellerclaw_run(group="sellercart-payouts", command="status")
sellerclaw_run(group="sellercart-payouts", command="connect")    # Stripe link for the owner
sellerclaw_run(group="sellercart-payouts", command="refresh")    # after they say they finished
sellerclaw_run(group="sellercart-payouts", command="delivery",
  body={"shipping_amount": 4.90, "shipping_countries": ["US", "CA"]})
```

Checkout opens only when Stripe is connected and cleared **and** delivery is answered. Stripe
onboarding is identity verification — the owner does it themselves and nobody can do it for them. An
unanswered delivery price is not the same as free shipping.

## Going live

```text
sellerclaw_run(group="sellercart", command="publish", body={"summary": "New home page and 12 products"})
```

Publishing is gated: it answers `pending_approval` or, on a connection the owner has set to not ask,
`approved_queued`. Write a `summary` that says what actually changed — it is what they see, and what
lands in the shop's version history (`versions`). `unpublish` closes the shop and is gated the same
way.

## A domain they own

```text
sellerclaw_run(group="sellercart-domain", command="connect", body={"hostname": "shop.acme.com"})
sellerclaw_run(group="sellercart-domain", command="check")     # after they added the DNS record
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
