from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "shipping-boxes"

# A box is the size half of every parcel the seller sends: catalog products and listings name one by
# its id ('box_id'), and a box's sides and own weight are read at publish rather than copied — so
# editing a box moves the parcel of everything packed in it.

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/shipping-boxes",
        summary=(
            "The seller's standard shipping boxes, oldest first: outer sides in millimetres, the "
            "empty box's own weight in grams (null when not stated) and which one is the default. "
            "A product or listing names its box by the 'id' here, as 'box_id'."
        ),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/shipping-boxes",
        summary=(
            "Add a box the seller packs orders into. When a parcel is sent its sides are the "
            "parcel's size and its own weight is added to the goods' weight. The seller's first box "
            "becomes the default unless is_default is false; a new product with no supplier that "
            "names no box is packed in the default one."
        ),
        body=(
            body_field(
                "name",
                required=True,
                help="What the seller calls the box (1-100 characters).",
                example="Small mailer",
            ),
            body_field(
                "length_mm",
                type=int,
                required=True,
                help="Outer length in millimetres (1-5000).",
                example=300,
            ),
            body_field(
                "width_mm",
                type=int,
                required=True,
                help="Outer width in millimetres (1-5000).",
                example=200,
            ),
            body_field(
                "height_mm",
                type=int,
                required=True,
                help="Outer height in millimetres (1-5000).",
                example=100,
            ),
            body_field(
                "weight_grams",
                type=int,
                help=(
                    "The empty box's own weight in grams (0-100000). Omit it when unknown — then "
                    "nothing is added to the goods' weight."
                ),
            ),
            body_field(
                "is_default",
                type=bool,
                help=(
                    "true makes this the box new products get. Omitted: only the seller's first box "
                    "becomes the default."
                ),
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/shipping-boxes/{box_id}",
        summary=(
            "Edit a box; a field left out keeps its value. New sides or own weight reach every "
            "product and listing packed in this box — a live listing's marketplace is sent the new "
            "parcel on its own (TikTok Shop: with the next publish)."
        ),
        body=(
            body_field("name", help="New name."),
            body_field("length_mm", type=int, help="Outer length in millimetres (1-5000)."),
            body_field("width_mm", type=int, help="Outer width in millimetres (1-5000)."),
            body_field("height_mm", type=int, help="Outer height in millimetres (1-5000)."),
            body_field(
                "weight_grams",
                type=int,
                nullable=True,
                help="The empty box's own weight in grams (0-100000); null clears it to unknown.",
            ),
            body_field(
                "is_default",
                type=bool,
                help=(
                    "true makes this the default box; false on the current default leaves the "
                    "seller with none. Existing products keep their box either way."
                ),
            ),
        ),
    ),
    Cmd(
        "delete",
        "DELETE",
        "/agent/shipping-boxes/{box_id}",
        summary=(
            "Delete a box. Refused with 'shipping_box_in_use' and the counts ('products', "
            "'listings') while anything is packed in it: move those to another box first "
            "(`catalog bulk-update` / `listings bulk-update` with box_id)."
        ),
    ),
)

app = build_group(NAME, "The seller's shipping boxes: the size and own weight of a parcel.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
