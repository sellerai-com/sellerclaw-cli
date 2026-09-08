from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "attributes"

# Every marketplace lets a category define which attributes a listing may carry, splits them into
# variation axes (Colour/Size) vs shared vs per-variation, and often fixes their allowed values.
# Drafting fills what follows from the product's own attributes and stops there, so a batch answers
# in one command; `map` is the model pass that finishes the job on the drafts it left short — it
# matches each product's attributes onto its category and writes the result onto the rows. `schema`
# shows what a category expects, with each attribute's values when the list is short enough to read.
# The long ones (Brand runs to ~13 800 entries, Country of Origin to 244) come back as a count
# instead; `values` searches those.
#
# Flow: `listings create-drafts` -> read `needs_attributes` -> `attributes map` on exactly those
# products -> set by hand whatever the finished job still names -> publish.
SPECS = (
    Cmd(
        "map",
        "POST",
        "/agent/stores/{store_id}/bulk-listing-jobs",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        # The endpoint is the generic bulk-job one; this verb is its mapping shape, so the caller
        # never states the kind.
        body_const=(("kind", "map_attributes"),),
        summary=(
            "Fill the item specifics of drafts that already exist: match each product's own "
            "attributes onto its listing's category and write the result onto the rows. One product "
            "costs about a minute of model time, so this is a background job — poll it with "
            "'listings bulk-job', or --wait for the finished answer. Each product comes back with "
            "'filled_attributes' and a fresh 'needs_attributes' (what is still yours to set with "
            "'listings bulk-update'). Max 10 products, and eBay only: elsewhere the specifics are "
            "settled when the draft is created."
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help=(
                    "Catalog products whose drafts came back short — the ones the draft response "
                    "named in 'needs_attributes', not the whole batch."
                ),
            ),
        ),
    ),
    Cmd(
        "schema",
        "POST",
        "/agent/attributes/schema",
        summary="Show the system attributes a category allows (required, variation-eligible, values).",
        body=(
            body_field("store_id", required=True, help="Store whose marketplace to read."),
            body_field(
                "category_external_id",
                required=True,
                help="Marketplace category id (the `external_id` from `categories suggest`/`search`).",
            ),
        ),
    ),
    Cmd(
        "values",
        "POST",
        "/agent/attributes/values",
        summary="Search one attribute's allowed values (Brand, Country of Origin, Model).",
        body=(
            body_field("store_id", required=True, help="Store whose marketplace to read."),
            body_field(
                "category_external_id",
                required=True,
                help="Marketplace category id (the `external_id` from `categories suggest`/`search`).",
            ),
            body_field(
                "attribute",
                required=True,
                help="Attribute name, spelled as `schema` reports it (e.g. \"Country of Origin\").",
            ),
            body_field(
                "q",
                help="Keep only values containing this text, case-insensitive. Omit for the first page.",
            ),
            body_field("limit", type=int, help="How many values to return (1-200, default 50)."),
        ),
    ),
)

app = build_group(
    NAME,
    "Fill and inspect the item specifics a marketplace category expects — stop guessing them.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
