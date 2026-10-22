from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sellercart-blog"

_LAYOUT_HELP = (
    "The article itself: an ordered list of blocks, as a page's layout is. An article takes "
    "richText, image, productGrid, imageText, faq, cta, steps, lookbook and banner — run "
    "`sellerclaw sellercart blocks` for their schemas. In richText, '## ' opens a section."
)

_LAYOUT_EXAMPLE = [
    {"type": "richText", "content": "## Why pans rust\n\nThe seasoning wears off where it is thin."},
    {"type": "image", "image_url": "https://…/rust.webp", "alt": "Rust on the rim of a pan"},
    {"type": "productGrid", "source": "skus", "skus": ["PAN-26"], "limit": 1, "columns": 2},
]

_STAGE_HELP = (
    "'planned' — a topic agreed for the plan: a title, a category and your notes, no text yet. "
    "'draft' — written, or being written."
)

_PUBLISH_AT_HELP = (
    "When it comes out, ISO 8601 with the owner's UTC offset. Left out: as soon as it is approved. "
    "An approved article with a later date stays off the blog until then."
)

_BRIEF_HELP = (
    "Your notes on the topic, never shown to buyers: start with 'Query: <phrase> (~N/mo)', then "
    "the angle, the questions to answer, the products and the sources."
)


def _post_fields(*, nullable: bool) -> tuple:
    """The fields an article is written with; on an edit ``null`` empties the optional ones."""
    return (
        body_field(
            "excerpt",
            help="Two or three sentences for its card on the blog and its search snippet.",
            nullable=nullable,
        ),
        body_field(
            "category",
            help="The one category it is filed under, in the shop's words. Reuse one from "
            "`sellercart-blog categories`.",
            example="Care",
            nullable=nullable,
        ),
        body_field("cover_url", help="Cover image — a URL from `sellercart-media`.", nullable=nullable),
        body_field("cover_alt", help="What the cover shows, in words.", nullable=nullable),
        body_field("layout", type=list, help=_LAYOUT_HELP, example=_LAYOUT_EXAMPLE),
        body_field(
            "seo",
            type=dict,
            help="Optional: title, description, og_image_url — what search and a shared link show.",
            nullable=nullable,
        ),
        body_field("publish_at", help=_PUBLISH_AT_HELP, nullable=nullable),
        body_field("brief", help=_BRIEF_HELP, nullable=nullable),
    )


SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/blog/posts",
        summary=(
            "Every article of the shop's blog, planned topics included, newest first. Each has "
            "status.state — planned, draft, waiting (the owner holds an ask to publish it), "
            "scheduled (approved, out on live_from), published — has_unpublished_changes, and "
            "brief: the first line of your notes. Read it before planning or writing, so no two "
            "articles chase the same query."
        ),
        flags=(flag("stage", choices=("planned", "draft"), help="Only planned topics, or only drafts."),),
    ),
    Cmd(
        "get",
        "GET",
        "/agent/sellercart/blog/posts/{slug}",
        summary=(
            "One article whole: its layout, your notes, where it stands, preview_url (the article "
            "as it would come out) and warnings — what is worth fixing before the owner is asked."
        ),
    ),
    Cmd(
        "categories",
        "GET",
        "/agent/sellercart/blog/categories",
        summary="The categories the blog files its articles under, busiest first.",
    ),
    Cmd(
        "create",
        "POST",
        "/agent/sellercart/blog/posts",
        summary=(
            "Start an article: a planned topic or a draft. Buyers see nothing new — an article "
            "reaches them only through `sellercart-blog publish`."
        ),
        body=(
            body_field(
                "slug",
                required=True,
                help="Its address: /blog/<slug>. Carry the search phrase, e.g. 'how-to-season-a-pan'.",
                example="how-to-season-a-cast-iron-pan",
            ),
            body_field("title", required=True, help="The article's title.", example="How to season a cast-iron pan"),
            body_field("stage", choices=("planned", "draft"), help=_STAGE_HELP),
            *_post_fields(nullable=False),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/sellercart/blog/posts/{slug}",
        summary=(
            "Edit an article. A field left out keeps its value; one sent as null is emptied; "
            "'layout' replaces the whole body. An article that is out keeps showing buyers its "
            "approved words until the owner approves the edit. Its address and date are fixed "
            "once buyers can read it."
        ),
        body=(
            body_field("slug", help="A new address — only for an article that was never out."),
            body_field("title", help="New title."),
            body_field("stage", choices=("planned", "draft"), help=_STAGE_HELP),
            *_post_fields(nullable=True),
            body_field(
                "mark_updated",
                type=bool,
                help=(
                    "Tell readers it was reworked (shows 'Updated <date>'). Only for a change to "
                    "what it says — never for a typo."
                ),
            ),
        ),
    ),
    Cmd(
        "delete",
        "DELETE",
        "/agent/sellercart/blog/posts/{slug}",
        summary=(
            "Delete a planned topic or a draft. One that is out is refused (post_is_live): take it "
            "off with `unpublish` first."
        ),
    ),
    Cmd(
        "discard",
        "POST",
        "/agent/sellercart/blog/posts/{slug}/discard",
        summary=(
            "Throw away an article's unpublished edits: back to the words buyers read. Cannot be "
            "undone."
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/sellercart/blog/publish",
        summary=(
            "Ask the owner to put these articles out — up to 10 in one approval, each on its "
            "publish_at or at once. The blog's own approval: the shop's draft is not needed and not "
            "touched. Answers pending_approval (buyers see nothing until the owner says yes), "
            "approved_queued (their setting answered it: say what came out) or published (the shop "
            "is closed, so the articles come out when it reopens). preview_urls has each article's "
            "link for the owner."
        ),
        body=(
            body_field(
                "slugs",
                type=str,
                repeatable=True,
                required=True,
                help="The articles to put out, by address. Repeat --slug for each.",
                example=["how-to-season-a-cast-iron-pan"],
                option="--slug",
            ),
            body_field(
                "summary",
                help="A few words naming them for the owner, e.g. 'Pan care, part 1'.",
                option="--summary",
            ),
        ),
    ),
    Cmd(
        "unpublish",
        "POST",
        "/agent/sellercart/blog/posts/{slug}/unpublish",
        summary=(
            "Ask the owner to take an article off the blog. Its text stays as a draft. Done at once "
            "on a closed shop."
        ),
    ),
    Cmd(
        "enable",
        "POST",
        "/agent/sellercart/blog/enable",
        summary=(
            "Turn the shop's blog on — only when the owner asked for it; they also have a button "
            "in the shop's Blog window. A blog turns on once the shop is open (shop_not_open "
            "before). While it is off, every write to the blog answers blog_off."
        ),
    ),
    Cmd(
        "disable",
        "POST",
        "/agent/sellercart/blog/disable",
        summary=(
            "Turn the shop's blog off — only when the owner asked for it. Buyers lose the blog, "
            "its articles and the menu items leading to it at once; the articles and the plan are "
            "kept for when it is back on. Asks about it the owner has not answered are withdrawn."
        ),
    ),
)

app = build_group(
    NAME,
    "The shop's blog: its on/off switch, articles, planned topics, and their publishing.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
