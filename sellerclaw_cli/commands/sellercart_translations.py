from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sellercart-translations"

#: The same sentence for every write that changes what buyers see — see `sellercart changes`.
_NOTE_HELP = (
    "One sentence for the owner about why, in their language — shown beside this change while it "
    "waits in the draft of a live shop, and kept with the version it is published in. Ignored "
    "before the shop first opens."
)

SPECS = (
    Cmd(
        "get",
        "GET",
        "/agent/sellercart/translations",
        summary=(
            "The shop's texts buyers read — pages, menus, category names, the catalog's product "
            "button; never products or the blog — each with its translation into one of the shop's "
            "extra languages and its status: 'missing' (buyers read the shop's own text), "
            "'outdated' (the text changed since; buyers still read the old translation) or "
            "'fresh'. Translate each 'source' and send it back with `update` under its 'key' and "
            "'source_hash'. Hidden pages are listed only when --scope names one."
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
                help="Only texts in this state; repeat for several (missing and outdated = what is left).",
            ),
            flag("scope", help="Only one place: page:<slug>, menu:header, menu:footer, category or shop."),
            flag("limit", type=int, minimum=1, maximum=200, default=200, help="Max texts; 'more' says how many are left."),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/sellercart/translations",
        summary=(
            "Save translations by key. Each text is checked on its own — a refused one says why "
            "('unknown_key', 'source_changed': read it again, 'empty', 'too_long', "
            "'links_changed': a markdown text must keep every link and picture) and the rest are "
            "saved. On a live shop they wait in the draft: translate before asking to publish."
        ),
        body=(
            body_field("language", required=True, help="One of the shop's extra languages.", example="de"),
            body_field(
                "texts",
                type=list,
                required=True,
                help=(
                    "Up to 200 objects with 'key' and 'source_hash' as `get` gave them and 'text', "
                    "the translation (null forgets it: buyers read the shop's own text there again)."
                ),
                example=[
                    {
                        "key": "page:home#0:hero:headline",
                        "source_hash": "3f2a9c1b7d4e",
                        "text": "Frischer Kaffee",
                    }
                ],
            ),
            body_field("note", help=_NOTE_HELP, example="Translated the home page into German"),
        ),
    ),
)

app = build_group(NAME, "The shop's texts in its extra languages.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
