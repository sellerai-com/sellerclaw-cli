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
            "Let a connected Amazon store's warehouse ship orders that came from other channels. "
            "Nothing is authorized here — the store's own connection already carries the right. "
            "Each Amazon store has its own warehouse, and a product ships from the one that holds "
            "it; linking one leaves the others as they are, and linking one that already ships "
            "answers with it. The warehouse is read straight away."
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
            "The Amazon stores whose warehouses ship for this seller, one row per store. Empty "
            "means none yet, which is the ordinary state — not a fault. A row's 'id' is what "
            "`suppliers` commands take as --supplier-id when there are several."
        ),
    ),
    Cmd(
        "disconnect",
        "DELETE",
        "/agent/supplier-accounts/amazon-fba",
        summary=(
            "Stop one store's warehouse shipping other channels' orders. The store itself stays "
            "connected. Refused while catalog products are still bound to that warehouse."
        ),
        flags=(
            flag(
                "store_id",
                param="sales_channel_id",
                help=(
                    "The Amazon store whose warehouse to stop (from `status`). May be left out "
                    "while only one warehouse ships."
                ),
            ),
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
        "list-inbound",
        "GET",
        "/agent/amazon/stores/{store_id}/fba/inbound",
        summary=(
            "What the seller is sending into Amazon's warehouse — read live from Amazon on every "
            "call, so it is never stale and never stored. The status is Amazon's own word, matching "
            "what Seller Central shows; pass it on as it stands. Use it to answer 'when will I have "
            "stock again' next to what is on the shelf now."
        ),
        flags=(
            flag("limit", type=int, help="Consignments to return.", minimum=1, maximum=20, default=20),
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
            "out of its warehouse. Name only products preview-binding called 'matched' — or "
            "'ambiguous' ones together with the store the owner chose — and never decide an "
            "ambiguous one on the owner's behalf. Every product named gets an answer: check "
            "'bound_product_ids' against what you sent, and read the rest as refusals. Running it "
            "again is harmless."
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help="Catalog product ids to bind (at most 100 per call).",
                example=["3f1a…", "9c22…"],
            ),
            body_field(
                "sales_channel_id",
                help=(
                    "The owner's answer to an 'ambiguous' product: the store (one of its "
                    "'candidate_channel_ids') whose warehouse ships it. A product only one "
                    "warehouse holds ships from that one regardless."
                ),
                example="7b2e…",
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
