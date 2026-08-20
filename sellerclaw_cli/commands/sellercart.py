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
            body_field("currency", help="ISO currency the shop prices in. Permanent — ask first.", example="USD"),
            body_field(
                "language",
                help=(
                    "What the shop says to buyers in its own words — the cart, the buttons, the "
                    "checkout, the empty shelf — and the titles of the six pages it starts with. "
                    "ISO 639-1; `options` lists what is accepted. Read it off the seller rather "
                    "than asking: the language they write to you in is the one their buyers read. "
                    "Omitted, the shop speaks English, so a Russian shop gets English buttons over "
                    "Russian pages. Changeable later, unlike the currency."
                ),
                example="ru",
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
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/sellercart",
        summary=(
            "Rename the shop, change the language it speaks, change the markup its prices are "
            "computed from, or stop it selling online. The address and the currency are deliberately "
            "not changeable: buyers and search engines already hold the one, and every price on the "
            "shelf is denominated in the other."
        ),
        body=(
            body_field("name", help="Shop name shown to buyers.", example="Acme Gear"),
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
                "markup_percent",
                type=float,
                help="Markup percent over catalog cost, e.g. 30 for +30% (0-500).",
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
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/sellercart/publish",
        summary="Take the storefront live. Refused until the home page is published — its address would 404 otherwise.",
    ),
    Cmd(
        "unpublish",
        "POST",
        "/agent/sellercart/unpublish",
        summary=(
            "Take the shop off the air. Pages, images and products survive; buyers stop seeing it. "
            "Reversible with `publish`. Closing a shop for good is the seller's own button in "
            "SellerClaw and has no command here."
        ),
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
    ),
    Cmd(
        "screenshot",
        "POST",
        "/agent/sellercart/screenshot",
        summary=(
            "A picture of one page of this shop, drafts included — look at what you built instead of "
            "imagining it. The preview secret is added server-side, so nothing has to be published "
            "first. Costs credits, so shoot when the answer matters (before publishing, after a "
            "theme change), not routinely."
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
        summary="Apply a ready-made look. Overwrites every style token; keeps the shop's logo and favicon.",
        body=(
            body_field(
                "preset",
                required=True,
                help="Preset id from `sellercart presets`.",
                example="boutique",
            ),
        ),
    ),
)

app = build_group(NAME, "The seller's own storefront: create it, theme it, take it live.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
