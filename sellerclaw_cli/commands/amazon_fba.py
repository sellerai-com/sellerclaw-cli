from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "amazon-fba"

SPECS = (
    Cmd(
        "connect",
        "POST",
        "/agent/supplier-accounts/amazon-fba",
        summary=(
            "Let one connected Amazon store ship orders that came from other channels. Nothing is "
            "authorized here — the store's own connection already carries the right — so this only "
            "records which store ships. Ask the owner which one when they have several; it decides "
            "which country parcels leave from. The warehouse is read straight away."
        ),
        body=(
            body_field(
                "sales_channel_id",
                required=True,
                help="The connected Amazon store that ships (from `channels list`).",
            ),
        ),
    ),
    Cmd(
        "status",
        "GET",
        "/agent/supplier-accounts/amazon-fba",
        summary=(
            "Which store ships for this seller, if any. 404 means none has been named yet, which "
            "is the ordinary state — not a fault."
        ),
    ),
    Cmd(
        "disconnect",
        "DELETE",
        "/agent/supplier-accounts/amazon-fba",
        summary=(
            "Stop shipping other channels' orders out of Amazon. The store itself stays connected, "
            "and products already bound to the warehouse keep their binding."
        ),
    ),
    Cmd(
        "list-stock",
        "GET",
        "/agent/amazon/stores/{store_id}/fba/inventory",
        summary=(
            "What this store holds in Amazon's fulfilment centres, as of the last read. Each row "
            "carries 'synced_at' — a quantity without its age cannot be judged. A quantity of null "
            "means Amazon reported no figure for that bucket, which is not zero. "
            "'fulfillment_options' says whether this warehouse may ship for other channels and, "
            "when it may not, why: report that reason as it stands, do not soften it."
        ),
    ),
    Cmd(
        "refresh-stock",
        "POST",
        "/agent/amazon/stores/{store_id}/fba/refresh",
        summary=(
            "Re-read the warehouse from Amazon now — for a shipment that just landed, or a store "
            "connected minutes ago. Amazon serves these figures from a cache it refreshes about "
            "once a day, so calling this repeatedly returns the same numbers: it is for 'something "
            "just changed', never for polling."
        ),
    ),
    Cmd(
        "preview-binding",
        "GET",
        "/agent/amazon/fba/binding",
        summary=(
            "Which catalog products Amazon could ship, and what stands in the way of the rest. "
            "Writes nothing. Only products the warehouse actually holds something of are listed; "
            "the rest of the catalog is counted in 'not_in_warehouse'. Every row carries a "
            "'message' written for the owner — show those words rather than the 'outcome' code, "
            "and take the ones that are not 'matched' to the owner as a question."
        ),
        flags=(
            flag(
                "limit",
                type=int,
                help="Products to report on.",
                minimum=1,
                maximum=200,
                default=50,
            ),
        ),
    ),
    Cmd(
        "bind",
        "POST",
        "/agent/amazon/fba/binding/apply",
        summary=(
            "Make Amazon the supplier of the products named here, so their orders can be shipped "
            "out of its warehouse. Name only products preview-binding called 'matched', and never "
            "decide an ambiguous one on the owner's behalf. Every product named gets an answer: "
            "check 'bound_product_ids' against what you sent, and read the rest as refusals. "
            "Running it again is harmless."
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help="Catalog product ids to bind (at most 100 per call).",
                example=["3f1a…", "9c22…"],
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Amazon's warehouse as a supplier: what it holds, and which products it ships for other channels.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
