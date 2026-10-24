from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "shipping-labels"

# A courier label for an order the seller ships themselves (their own stock, an offline supplier's
# warehouse — never a CJ or Amazon FBA order, those suppliers ship on their own), bought through the
# seller's own Shippo account. The server fills the label from what it holds: the warehouse the goods
# sit in, the order's address, the products' weight and box, and the customs lines for a parcel going
# abroad. 'quote' asks every carrier in the account; 'buy' asks the owner to approve one rate. Once
# bought, the order is marked shipped and its tracking goes to the store — nothing more to do.

_LABEL_FORMATS = ("PDF_4x6", "PDF_4x8", "PDF", "PDF_A4", "PDF_A6", "PNG", "ZPLII")

SPECS = (
    Cmd(
        "quote",
        "POST",
        "/agent/orders/{order_id}/shipping-label/quote",
        summary=(
            "What every carrier in the seller's Shippo account charges to ship this order, cheapest "
            "first: each rate's 'rate_id', title ('UPS Ground'), amount, currency, estimated_days, "
            "badges (cheapest/fastest/best_value) and 'buyer_chose' — the service the buyer paid for "
            "at the shop's checkout. Send no body to quote the label exactly as SellerClaw fills it; "
            "send only what to change otherwise. 'draft' in the answer is the label as priced. A "
            "label that cannot be priced yet answers 422 listing what is missing (details.missing) — "
            "e.g. the parcel's weight, or the sender's name ('shipping-labels update-sender'). The "
            "order id may be our id, its number ('#1001') or the marketplace's id. Changes nothing; "
            "rates stay buyable for 7 days."
        ),
        read_only=True,
        timeout=60,
        body=(
            body_field(
                "warehouse_id",
                help="Ship from this warehouse of the seller's (default: where the goods are stocked).",
            ),
            body_field(
                "ship_from",
                type=dict,
                help=(
                    "Sender fields to change — name, company, phone, email — or, with street1, city, "
                    "state, zip or country, a one-off address to ship from."
                ),
                example={"name": "Nest Supply Co."},
            ),
            body_field(
                "ship_to",
                type=dict,
                help=(
                    "Recipient fields to change for this label only: name, company, street1, "
                    "street2, city, state, zip, country (two letters), phone, email."
                ),
                example={"street2": "Apt 4"},
            ),
            body_field(
                "parcel",
                type=dict,
                help=(
                    "The parcel, in millimetres and grams: box_id (one of 'shipping-boxes list'), "
                    "length_mm, width_mm, height_mm, weight_grams (box included). Omitted figures "
                    "keep the products' weight and box."
                ),
                example={"box_id": "6f1c…", "weight_grams": 1250},
            ),
            body_field(
                "customs_items",
                type=list,
                help=(
                    "Corrections to the customs lines of a parcel going abroad, by the order line's "
                    "id: line_id, and any of description, unit_value, unit_weight_grams, "
                    "origin_country (two letters), tariff_number (HS code)."
                ),
                example=[{"line_id": "10", "tariff_number": "6912.00"}],
            ),
            body_field(
                "signature",
                choices=("STANDARD", "ADULT"),
                help="Have the carrier collect a signature at delivery.",
            ),
            body_field(
                "insurance",
                type=dict,
                help="Insure the parcel for this value: amount, currency (three letters).",
                example={"amount": "50.00", "currency": "USD"},
            ),
            body_field(
                "shipment_date",
                help="The day the parcel goes to the carrier, YYYY-MM-DD (default: today).",
                example="2026-10-27",
            ),
        ),
    ),
    Cmd(
        "buy",
        "POST",
        "/agent/orders/{order_id}/shipping-label",
        summary=(
            "Ask the owner to approve buying the label by one of the order's rates (from "
            "'shipping-labels quote'). Nothing is bought by this call: it answers 202 with "
            "status 'pending_approval' (waiting for the owner) or 'approved_queued' (their approval "
            "setting answered; it is bought within moments). Once bought, the order is marked "
            "shipped and its tracking goes to the store — do not run 'orders set-shipped' or a "
            "channel's create-fulfillment for it. Read the label back from 'orders get' "
            "(shipping_label). A second ask for an order that already has one waiting is refused."
        ),
        timeout=60,
        body=(
            body_field(
                "rate_id",
                required=True,
                help="The rate to buy the label by — 'rate_id' from 'shipping-labels quote'.",
                example="9f2c…",
            ),
            body_field(
                "label_file_type",
                choices=_LABEL_FORMATS,
                help=(
                    "Label format: PDF_4x6 or PDF_4x8 (thermal labels), PDF (Letter paper), PDF_A4, "
                    "PDF_A6, PNG, ZPLII (Zebra printers). Default: the seller's sender profile."
                ),
            ),
        ),
    ),
    Cmd(
        "get-sender",
        "GET",
        "/agent/shipping/sender",
        summary=(
            "Who the seller's labels name as the sender: 'profile' (null until the owner confirms "
            "one) and 'suggestion' (built from their account, used meanwhile) — name, company, "
            "email, phone, label_file_type. The address is the warehouse each parcel leaves from."
        ),
    ),
    Cmd(
        "update-sender",
        "PUT",
        "/agent/shipping/sender",
        summary=(
            "Save the sender the owner confirmed: the name printed on every label, and the email and "
            "phone carriers need for parcels going abroad. Replaces the whole profile."
        ),
        body=(
            body_field(
                "name",
                required=True,
                help="The name printed as the sender.",
                example="Nest Supply Co.",
            ),
            body_field("company", help="Company name, if different."),
            body_field("email", help="Sender's email."),
            body_field("phone", help="Sender's phone."),
            body_field(
                "label_file_type",
                choices=_LABEL_FORMATS,
                help="The label format the seller's printer takes. Kept as it was when omitted.",
            ),
        ),
    ),
)

app = build_group(NAME, "Courier labels for orders the seller ships, via their Shippo account.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
