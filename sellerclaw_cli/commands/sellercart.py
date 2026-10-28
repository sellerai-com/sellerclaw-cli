from __future__ import annotations

import typer

from sellerclaw_cli._command_group import (
    LONG_TIMEOUT_SECONDS,
    Cmd,
    body_field,
    build_group,
    flag,
)

NAME = "sellercart"

#: The same sentence for every write that changes what buyers see — see `sellercart changes`.
_NOTE_HELP = (
    "One sentence for the owner about why, in their language — shown beside this change while it "
    "waits in the draft of a live shop, and kept with the version it is published in. Ignored "
    "before the shop first opens."
)

#: The typefaces a shop may use. A whitelist server-side (every name becomes a Google Fonts request
#: from the buyer's browser), enumerated here so a wrong one is refused locally instead of costing a
#: round-trip. Keep in step with the API.
FONTS = (
    "Inter",
    "Manrope",
    "Lora",
    "Playfair Display",
    "Roboto Mono",
    "Cormorant Garamond",
    "Libre Baskerville",
    "DM Serif Display",
    "Source Serif 4",
    "Space Grotesk",
)

#: The variants of each part of a layout — how the header, a product card and a product page are
#: arranged. Mirrors the API's own lists, so a wrong one is refused locally. Keep in step with it.
_HEADER_STYLES = ("classic", "centered", "compact", "split", "bold")
_CARD_STYLES = ("classic", "portrait", "dense", "framed", "deal")
_PRODUCT_PAGE_STYLES = ("classic", "stacked", "specs", "editorial", "focus", "longform")
#: How much of a product page the photos take — `auto` is the layout's own size.
_PRODUCT_PHOTO_SIZES = ("auto", "small", "medium", "large")

SPECS = (
    Cmd(
        "status",
        "GET",
        "/agent/sellercart",
        summary=(
            "Show the seller's SellerCart storefront: address, live/draft state, theme, custom domain, "
            "preview link, the markup its prices are computed from, and whether `publish` would be "
            "accepted right now. Returns null when they have none yet."
        ),
    ),
    Cmd(
        "options",
        "GET",
        "/agent/sellercart/options",
        summary=(
            "What a shop may be created with: the address suffix every shop ends in, every currency "
            "`create` accepts, and every language it can be served in. Read it before offering the "
            "seller a currency — the currency is permanent once the shop exists."
        ),
    ),
    Cmd(
        "traffic",
        "GET",
        "/agent/sellercart/traffic",
        summary=(
            "How many people came to the shop, what they looked at, where they came from, and what "
            "each source actually sold. The shop's own counter on its own domain, so it answers "
            "even for an owner with no Google Analytics and is not the half of the truth ad "
            "blockers leave behind. `views` counts pages and `visitors` counts people — different "
            "questions. A null source means unknown, never 'direct'."
        ),
        flags=(
            flag(
                "days",
                type=int,
                minimum=1,
                maximum=90,
                help="How many days back, counting today. Default 7.",
            ),
        ),
    ),
    Cmd(
        "check-slug",
        "GET",
        "/agent/sellercart/slug-check",
        summary=(
            "Is this address free? Ask before proposing one to the seller, rather than after `create` "
            "refuses it. A malformed address is refused with the reason: 'not allowed' and 'somebody "
            "has it' need different answers, and only one is fixed by trying another name."
        ),
        flags=(
            flag(
                "slug",
                required=True,
                help="Address to test: lowercase letters, digits and hyphens, 3-63 characters.",
            ),
        ),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/sellercart",
        summary="Create the storefront. One per seller. Also creates its sales channel and its default pages (home, catalog, about, delivery, returns, contacts) as drafts.",
        body=(
            body_field("name", required=True, help="Shop name shown to buyers.", example="Acme Gear"),
            body_field(
                "slug",
                required=True,
                help="Address of the shop: <slug>.sellercart.shop. Lowercase letters, digits, hyphens.",
                example="acme-gear",
            ),
            body_field(
                "currency",
                help=(
                    "ISO currency the shop prices in. Treat it as permanent and ask first: it can "
                    "only be changed while the shop has priced nothing, and the first drafted "
                    "product closes that window for good."
                ),
                example="USD",
            ),
            body_field(
                "language",
                help=(
                    "What the shop says to buyers in its own words — the cart, the buttons, the "
                    "checkout, the empty shelf — and the titles of the six pages it starts with. "
                    "ISO 639-1; `options` lists what is accepted. Read it off the seller rather "
                    "than asking: the language they write to you in is the one their buyers read. "
                    "Omitted, the shop speaks English, so a Russian shop gets English buttons over "
                    "Russian pages. Changeable later whatever the shop is selling, unlike the "
                    "currency."
                ),
                example="ru",
            ),
            body_field(
                "display_currencies",
                repeatable=True,
                help=(
                    "Up to four extra currencies buyers may *read* prices in, beside `currency`. "
                    "Display only: the shop still prices and charges in `currency`, buyers get a "
                    "switcher, and the basket says what they will be charged. Optional — set it "
                    "only when the owner sells abroad or asks."
                ),
                example=["EUR", "GBP"],
            ),
            body_field(
                "markup_percent",
                type=float,
                help=(
                    "Markup percent over catalog cost, e.g. 30 for +30% (0-500). Optional — a shop "
                    "starts with no markup, and products aren't priced until you set one."
                ),
                example=30,
            ),
            body_field(
                "sells_online",
                type=bool,
                help=(
                    "Omit for a shop with a basket and checkout. False opens it as a catalog — "
                    "prices and stock, no basket, no payment step — only when the owner asked for one."
                ),
                example=False,
            ),
            body_field(
                "source_store_id",
                help=(
                    "The owner's Amazon store the shop starts from (its id from `channels list`). "
                    "The shop remembers it so its products step knows where they come from; the "
                    "name, currency and language are still the values sent here."
                ),
                example="3f1c2a9e-5b7d-4c8e-9a10-6d2b4e8f7c31",
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/sellercart",
        summary=(
            "Rename or move the shop, change the language it speaks, propose the markup its prices "
            "are computed from, set its delivery margin or its Shippo prices, or stop it selling "
            "online. Moving is real — the old address stops "
            "answering and every product link is rewritten — and the currency only moves while the "
            "shop has priced nothing, because a shelf price is a number *in* one."
        ),
        body=(
            body_field("name", help="Shop name shown to buyers.", example="Acme Gear"),
            body_field(
                "slug",
                help=(
                    "Move the shop to this address. The old one stops answering the moment this "
                    "returns, and every product link is rewritten to the new one — so send it when "
                    "the owner has renamed their shop and wants the address to follow, not to tidy "
                    "a spelling somebody may already have bookmarked or linked to. An address "
                    "someone else holds comes back as slug_taken; check first with `check-slug`. A "
                    "shop on its own domain keeps being reached by that domain either way."
                ),
                example="tihiy-dom",
            ),
            body_field(
                "currency",
                help=(
                    "Change what the shop prices in. Accepted only while nothing has been priced in "
                    "the old one: a shelf price is a number *in* a currency and is held nowhere "
                    "else, so relabelling a stocked shop would turn a $20 item into a EUR20 one at "
                    "no notice. Past the first drafted product this comes back as currency_locked, "
                    "and the only way across is to take the products off and re-add them — say that "
                    "cost out loud rather than offering the change as a setting. `options` lists "
                    "what is accepted."
                ),
                example="EUR",
            ),
            body_field(
                "language",
                help=(
                    "What the shop says to buyers from the next page load: the cart, the buttons, "
                    "the checkout, the empty shelf. ISO 639-1; `options` lists what is accepted. It "
                    "rewrites nothing the seller already wrote — pages, blocks and menus stay in the "
                    "language they were authored in — so switching a shop whose pages are English to "
                    "'ru' leaves Russian buttons over English copy until the pages are redone. Say "
                    "that when you switch it."
                ),
                example="ru",
            ),
            body_field(
                "display_currencies",
                repeatable=True,
                help=(
                    "The shop's FULL list of extra currencies buyers may *read* prices in (up to "
                    "four, not counting `currency`). It REPLACES the current list — to add or drop "
                    "one currency, send add_display_currencies / remove_display_currencies instead. "
                    "[] goes back to one price. Display only and never locked by the shelf. This, "
                    "not `currency`, is the answer to 'let buyers see prices in euros'. A currency "
                    "no rate source can quote "
                    "today comes back as display_currency_unavailable."
                ),
                example=["GBP", "EUR", "JPY"],
            ),
            body_field(
                "add_display_currencies",
                repeatable=True,
                help=(
                    "Extra currencies to add to the ones the shop already shows, e.g. [\"JPY\"] "
                    "for 'add the yen'. Everything already on the list stays; a code already there "
                    "is kept once. Can go with remove_display_currencies, not with "
                    "display_currencies."
                ),
                example=["JPY"],
            ),
            body_field(
                "remove_display_currencies",
                repeatable=True,
                help=(
                    "Extra currencies to stop showing; the rest stay. A code the shop does not show "
                    "is ignored. Can go with add_display_currencies, not with display_currencies."
                ),
                example=["GBP"],
            ),
            body_field(
                "markup_percent",
                type=float,
                help=(
                    "Markup percent over catalog cost, e.g. 30 for +30% (0-500). Because it is what "
                    "the owner earns on everything the shop sells, this does not change it: it "
                    "raises an approval for them and answers 202 with status pending_approval, and "
                    "the shop prices by it once they approve. Send it on its own — mixed with a "
                    "rename or sells_online the call is refused."
                ),
                example=45,
            ),
            body_field(
                "sells_online",
                type=bool,
                help=(
                    "False turns the shop into a catalog: prices and stock, no basket, no checkout. "
                    "A legitimate shape for a shop, not a half-built one. Delivery terms and Stripe "
                    "are kept, so turning it back on restores the shop instead of restarting setup."
                ),
                example=False,
            ),
            body_field(
                "show_sold_out",
                type=bool,
                help=(
                    "True keeps sold-out products on the shelf, marked 'Sold'. False is the normal "
                    "state and needs no call: a sold-out product leaves every list, category and the "
                    "sitemap by itself and comes back when restocked. Send it only when the owner "
                    "asks to show them. On a live shop it waits in the draft."
                ),
                example=True,
            ),
            body_field(
                "product_cta_label",
                help=(
                    "The seller's own button where 'Add to cart' would be on a catalog shop, e.g. "
                    "'Ask about this'. Send it together with product_cta_href; empty strings clear "
                    "both. Unset, products show no button at all — better than one that guesses."
                ),
                example="Ask about this",
                clearable=True,
            ),
            body_field(
                "product_cta_href",
                help="Where that button goes: a page on the shop ('/contacts') or a full link.",
                example="/contacts",
                clearable=True,
            ),
            body_field(
                "return_policy",
                type=dict,
                nullable=True,
                help=(
                    "The machine-readable half of the Returns page, told to search engines and "
                    "shopping assistants as the shop's promise — so only what the owner said. "
                    "{accepted, days, fees}: days from delivery (1-365, required when accepted); "
                    "fees 'free' or 'buyer_pays', left out when the owner did not say who pays. "
                    '{"accepted": false} takes nothing back. Replaces the policy whole and applies '
                    "at once, like delivery; null removes it. Rewrite the Returns page to match."
                ),
                example={"accepted": True, "days": 30, "fees": "free"},
            ),
            body_field(
                "delivery_margin_percent",
                type=float,
                help=(
                    "The shop's margin on what CJ, Amazon or the seller's Shippo charge to deliver "
                    "a parcel: a share of it (0-1000). Added only when the buyer pays for that "
                    "delivery at all, never on the seller's own prices. Only what the owner asked "
                    "for. Applies at once."
                ),
                example=10,
            ),
            body_field(
                "delivery_margin_amount",
                type=float,
                help="With it: an amount per parcel, in the shop's currency.",
                example=1,
            ),
            body_field(
                "analytics",
                type=dict,
                help=(
                    "The shop's measurement tags, changed key by key: ga4_measurement_id "
                    "(G-XXXXXXXXXX), google_ads_conversion_id (AW-123456789) with "
                    "google_ads_purchase_label, google_tag_manager_id (GTM-XXXXXXX), meta_pixel_id "
                    "(digits), google_site_verification (the content value of Search Console's meta "
                    "tag) and consent_banner (true asks buyers before anything measures them — what "
                    "a shop selling into the EU needs). A key left out stays; an empty string "
                    "removes one. Applies at once. A wrong shape comes back as invalid_analytics."
                ),
                example={"ga4_measurement_id": "G-ABC1234567", "consent_banner": True},
            ),
            body_field(
                "analytics_secrets",
                type=dict,
                help=(
                    "Keys that report the shop's sales from our server too: meta_capi_access_token "
                    "(minted against the pixel above) and ga4_api_secret (Measurement Protocol, "
                    "against the GA4 id above) — set the identifier first. Write-only, never read "
                    "back; an empty string revokes one."
                ),
                example={"ga4_api_secret": "…"},
            ),
            body_field(
                "shippo_rates",
                type=bool,
                help=(
                    "true: the checkout prices the goods the seller sends themselves through their "
                    "connected Shippo account — only on the owner's own yes; 409 "
                    "shippo_not_connected without one. false stops it. Applies at once."
                ),
            ),
            body_field("note", help=_NOTE_HELP, example="Led with free delivery, as you asked"),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/sellercart/publish",
        summary=(
            "Ask the owner to put the shop's draft live — every change at once — or to open a shop "
            "that is not open yet. Nothing buyers see changes here: it raises an approval carrying "
            "the change list and the preview link and answers 202 with status pending_approval (or "
            "approved_queued when the owner's Autopilot answers it). If the owner asked for this "
            "publish, their message is the answer: hand it to `action-requests confirm` instead of "
            "asking them again. Refused before asking: nothing_to_publish, home_page_required, "
            "payments_required, domain_required (first opening requires the owner's live custom "
            "domain; reopening a deliberately closed shop does not), publish_already_pending."
        ),
        body=(
            body_field(
                "summary",
                option="--summary",
                help="A few words naming this version for the owner, e.g. 'Summer sale look'.",
                example="Summer sale look",
            ),
        ),
    ),
    Cmd(
        "unpublish",
        "POST",
        "/agent/sellercart/unpublish",
        summary=(
            "Ask the owner to close the shop temporarily: answers 202 pending_approval, or "
            "approved_queued under Autopilot. Buyers see a temporarily closed page with the owner's "
            "message and can still write to the shop. Pages, images and products survive. "
            "On a closed shop it changes the notice under approval: a field left out keeps its "
            "value, null clears it; with nothing to change it answers 200 with nothing asked. "
            "publish reopens it without requiring a custom "
            "domain; Stripe must still be verified. The reopening date is display only. "
            "Deleting the shop is the owner's own button in SellerClaw."
        ),
        body=(
            body_field('buyer_note', option='--buyer-note', nullable=True,
                       help='What buyers read on the closed shop, up to 280 characters. null removes it.'),
            body_field('reopens_on', option='--reopens-on', nullable=True,
                       help='The day the owner plans to reopen, YYYY-MM-DD. Shown to buyers only. '
                            'null removes it.'),
        ),
    ),
    Cmd(
        "changes",
        "GET",
        "/agent/sellercart/changes",
        summary=(
            "What the draft changes compared with what buyers see, change by change, with your notes "
            "and the preview link. On a live shop every edit waits here until the owner approves a "
            "publish. pending_request_id is your publish ask still waiting for them."
        ),
    ),
    Cmd(
        "discard",
        "POST",
        "/agent/sellercart/discard",
        summary=(
            "Throw the draft away: the shop goes back to exactly what buyers see. Cannot be undone — "
            "only when the owner asks for it. Answers with what was discarded; say it back to them. "
            "Any publish ask still waiting is withdrawn. never_published: the shop has never been "
            "open, so there is no version to go back to."
        ),
    ),
    Cmd(
        "versions",
        "GET",
        "/agent/sellercart/versions",
        summary=(
            "The shop's published versions, newest first: what each one changed, and whether the "
            "owner published it, approved your ask, or it was the shop as it stood when versions "
            "arrived."
        ),
        flags=(flag("limit", type=int, minimum=1, maximum=50, default=10, help="How many."),),
    ),
    Cmd(
        "preview",
        "POST",
        "/agent/sellercart/preview",
        summary=(
            "The secret link that shows the shop including its drafts — hand it to the seller to look "
            "before going live. Append the token to any page as '?preview=<token>'. Asking again "
            "returns the same token, so a preview tab they left open keeps working."
        ),
        read_only=True,
    ),
    Cmd(
        "screenshot",
        "POST",
        "/agent/sellercart/screenshot",
        summary=(
            "A picture of one page of this shop, drafts included — look at what you built instead of "
            "imagining it. The preview secret is added server-side, so nothing has to be published "
            "first. Costs credits, so shoot when the answer matters (before publishing, after a "
            "theme change), not routinely. Answers with screenshot_url — a link, not a file."
        ),
        body=(
            body_field(
                "page",
                help="Page slug to shoot: home, catalog, delivery... Defaults to home.",
                example="home",
            ),
            body_field(
                "path",
                help=(
                    "Any path on the shop instead of a page slug — a product page, say. Mutually "
                    "exclusive with page."
                ),
                example="/products/42",
            ),
            body_field(
                "width",
                type=int,
                help=(
                    "Viewport width in pixels, 320-2560 (default 1280). 390 photographs the shop as "
                    "a phone receives it, layout and all."
                ),
                example=1280,
            ),
            body_field(
                "full",
                type=bool,
                help=(
                    "Capture the whole page instead of the first screen. For a picture the SELLER "
                    "opens: a full-page shot of a long page is too tall for you to read back, and "
                    "comes back as nothing. Scroll the viewport instead when you need to look."
                ),
                example=False,
            ),
        ),
        # A render is a page load in somebody else's browser: the default budget refuses a call
        # that is still working.
        timeout=LONG_TIMEOUT_SECONDS,
        read_only=True,
        save_url_field="screenshot_url",
    ),
    Cmd(
        "blocks",
        "GET",
        "/agent/sellercart/blocks",
        summary="List every block a page can be built from, with the schema of each block's props. Read this before writing a page: a block type that is not here cannot be saved.",
    ),
    Cmd(
        "theme",
        "PATCH",
        "/agent/sellercart/theme",
        summary=(
            "Set design tokens. Omitted fields keep their current value; heading_font, background, "
            "ink, accent and custom_css also take an empty string, which clears them back to the "
            "shop's own default."
        ),
        body=(
            body_field(
                "primary",
                help="Brand color, hex: buttons, links, the loud things.",
                example="#1f4d3a",
            ),
            body_field("neutral", help="Neutral color for text and surfaces, hex.", example="#64748b"),
            body_field(
                "accent",
                help=(
                    "Second color for details the primary should not shout over — prices, badges, "
                    "step numbers. Empty string clears it back to the primary."
                ),
                example="#b08d57",
                clearable=True,
            ),
            body_field(
                "background",
                help=(
                    "The page's own surface color. Set it together with `ink` and every panel, border "
                    "and level of text is mixed from the pair. Empty string clears it."
                ),
                example="#faf6ee",
                clearable=True,
            ),
            body_field(
                "ink",
                help="The page's own text color, paired with `background`. Empty string clears it.",
                example="#231f1c",
                clearable=True,
            ),
            body_field("font", help="Body typeface.", choices=FONTS),
            body_field(
                "heading_font",
                help=(
                    "Typeface for headings. A serif display over a sans body is what makes a shop look "
                    "designed rather than generated. Empty string clears it."
                ),
                choices=FONTS,
                clearable=True,
            ),
            body_field("radius", help="Corner rounding.", choices=("none", "sm", "md", "lg", "xl")),
            body_field("logo_url", help="Logo image path (copy it in with `sellercart-media add`)."),
            body_field("favicon_url", help="Favicon image path."),
            body_field(
                "custom_css",
                help=(
                    "The shop's own stylesheet, written against the documented sc-* class names only. "
                    "Refused with the reason if it is not safe to serve. Empty string clears it."
                ),
                clearable=True,
            ),
            body_field(
                "currency_switcher",
                help=(
                    "Where buyers switch the currency prices are shown in, once the shop has "
                    "display_currencies: the header, next to the price on a product page, or both. "
                    "Restyle it with custom_css on sc-header__currency / sc-product__currency."
                ),
                choices=("header", "product", "both"),
            ),
            body_field(
                "header",
                help=(
                    "One part of the layout: how the header is arranged. For mixing two layouts on the "
                    "owner's request; a whole layout is `apply-layout`. Never changes the look."
                ),
                choices=_HEADER_STYLES,
            ),
            body_field(
                "product_card",
                help="One part of the layout: how a product looks on a shelf.",
                choices=_CARD_STYLES,
            ),
            body_field(
                "product_page",
                help=(
                    "One part of the layout: how a product's own page is arranged. `longform` is "
                    "on no ready-made layout — the classic page with the description and the "
                    "specifications moved under the photos, for products with a lot to say; only "
                    "on the owner's request."
                ),
                choices=_PRODUCT_PAGE_STYLES,
            ),
            body_field(
                "product_photo_size",
                help=(
                    "How much of a product page the photos take on a computer: small, medium or "
                    "large (two fifths, a half or three fifths of the row beside the buy box), or "
                    "auto — the size the layout draws them at. Phones always show them full width; "
                    "neither a look nor a layout changes it. The way to resize product photos — "
                    "not custom_css."
                ),
                choices=_PRODUCT_PHOTO_SIZES,
            ),
            body_field("note", help=_NOTE_HELP, example="Led with free delivery, as you asked"),
        ),
    ),
    Cmd(
        "presets",
        "GET",
        "/agent/sellercart/presets",
        summary=(
            "The ready-made looks, each with the exact colors and typefaces it would set. A starting "
            "point, not a straitjacket: apply one, then patch what needs to differ with `theme`."
        ),
    ),
    Cmd(
        "apply-preset",
        "POST",
        "/agent/sellercart/presets/apply",
        summary=(
            "Apply a ready-made look: overwrites every colour, typeface and corner token. Keeps the "
            "shop's logo, favicon and layout (`apply-layout`)."
        ),
        body=(
            body_field(
                "preset",
                required=True,
                help="Preset id from `sellercart presets`.",
                example="boutique",
            ),
            body_field("note", help=_NOTE_HELP, example="Led with free delivery, as you asked"),
        ),
    ),
    Cmd(
        "layouts",
        "GET",
        "/agent/sellercart/layouts",
        summary=(
            "The ready-made layouts: how each arranges the header, product cards and product page, "
            "and the blocks its home page is built from (`home_recipe`, top to bottom). A layout is "
            "the shape, a look (`presets`) the paint; they combine freely."
        ),
    ),
    Cmd(
        "apply-layout",
        "POST",
        "/agent/sellercart/layouts/apply",
        summary=(
            "Put the shop on a ready-made layout: its header, product cards and product page change "
            "at once. Keeps the look. Touches no page — rebuild the home page to the layout's "
            "`home_recipe` next, keeping the owner's own words and pictures."
        ),
        body=(
            body_field(
                "layout",
                required=True,
                help="Layout id from `sellercart layouts`.",
                example="gallery",
            ),
            body_field("note", help=_NOTE_HELP, example="Bigger photos for the new collection"),
        ),
    ),
)

app = build_group(NAME, "The seller's own storefront: create it, theme it, take it live.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
