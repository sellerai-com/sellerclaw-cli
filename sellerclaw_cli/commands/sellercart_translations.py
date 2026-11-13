from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sellercart-translations"

#: Kept for older callers: a translation is live, so there is no draft change to explain.
_NOTE_HELP = "Ignored: a translation is live at once and adds nothing to the shop's draft."

SPECS = (
    Cmd(
        "get",
        "GET",
        "/agent/sellercart/translations",
        summary=(
            "The shop's texts buyers read, each with its translation into one of the shop's extra "
            "languages and its status: 'missing' (buyers read the shop's own text), 'outdated' (a "
            "product reworded since; the server is making the new translation) or 'fresh'. "
            "Everything is translated by the server on its own and kept current — you do not "
            "translate. Read this to answer the owner, to change a translation they want worded "
            "differently, or to finish a text the server gave up on (translations_need_agent). "
            "Without --scope: pages, menus, category names and the catalog's product button, with "
            "who wrote each translation ('origin'), plus 'products' (how far the server has got, "
            "and whether it is 'paused') and 'rules' (the owner's rules for translating). Products: "
            "--scope products, terms (shared option and spec words) or product:<listing id>. Hidden "
            "pages are listed only when --scope names one. The blog is never translated."
        ),
        flags=(
            flag(
                "language",
                required=True,
                help="One of the shop's extra languages (display_languages), e.g. de.",
            ),
            flag(
                "status",
                repeatable=True,
                choices=("missing", "outdated", "fresh"),
                help="Only texts in this state; repeat for several.",
            ),
            flag(
                "scope",
                help=(
                    "Only one place: page:<slug>, menu:header, menu:footer, category or shop — or the "
                    "products: products (every product's title, description and SEO title), terms "
                    "(option and spec words, shared by every product) or product:<listing id> (one "
                    "product and its terms)."
                ),
            ),
            flag("limit", type=int, minimum=1, maximum=200, default=200, help="Max texts; 'more' says how many are left."),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/sellercart/translations",
        summary=(
            "Save translations by key — only for words the owner asked for, or a text the server "
            "gave up on. Each text is checked on its own — a refused one says why ('unknown_key', "
            "'source_changed': read it again, 'empty', 'too_long', 'links_changed': a markdown text "
            "must keep every link and picture, an html description every tag) and the rest are "
            "saved. Live at once and kept by the text it translates: a page's new wording in the "
            "draft shows translated when it is published, nothing waits for a publish. It stays "
            "until its text is reworded, then the server translates the new wording — put lasting "
            "wishes in translation_rules."
        ),
        body=(
            body_field("language", required=True, help="One of the shop's extra languages.", example="de"),
            body_field(
                "texts",
                type=list,
                required=True,
                help=(
                    "Up to 200 objects with 'key' and 'source_hash' as `get` gave them and 'text', "
                    "the translation (null forgets it, and the server translates the text afresh)."
                ),
                example=[
                    {
                        "key": "page:home#0:hero:headline",
                        "source_hash": "3f2a9c1b7d4e",
                        "text": "Frischer Kaffee",
                    }
                ],
            ),
            body_field("note", help=_NOTE_HELP),
        ),
    ),
    Cmd(
        "retranslate",
        "POST",
        "/agent/sellercart/translations/retranslate",
        summary=(
            "Ask the server to translate texts again, replacing their stored translations — after "
            "the owner changed translation_rules (all_products, terms, shop_texts), for some "
            "products by id, or to give a text the server gave up on another chance. A reworded "
            "text needs no request: the server redoes it on its own. The old translation stays until "
            "the new one is in (within minutes); anything you write with `update` meanwhile wins. "
            "Spends the owner's credits."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                help="The products, by any id the shop knows them by (up to 200).",
                example=["3b9c1e2a-5d7f-4a6b-9c8d-1e2f3a4b5c6d"],
            ),
            body_field(
                "all_products",
                type=bool,
                help="Every product on the shop instead of listing_ids.",
                example=True,
            ),
            body_field(
                "languages",
                repeatable=True,
                help="Default: every extra language the shop offers.",
                example=["de"],
            ),
            body_field(
                "fields",
                repeatable=True,
                help="Default: all three — title, description, seo.title.",
                example=["description"],
            ),
            body_field(
                "terms",
                type=bool,
                help="Also the option and spec words those products use (shared by every product).",
                example=True,
            ),
            body_field(
                "shop_texts",
                type=bool,
                help="Every one of the shop's own texts: pages, menus, categories, delivery methods, the product button.",
                example=True,
            ),
        ),
    ),
)

app = build_group(NAME, "The shop's texts in its extra languages.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
