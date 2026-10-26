from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "shipping-labels"

# A courier label for an order the seller ships themselves (their own stock, an offline supplier's
# warehouse — never a CJ or Amazon FBA order, those suppliers ship on their own), bought through the
# seller's own Shippo account. The server fills the label from what it holds: the sender address of
# the warehouse the goods sit in (else the default one), the order's address, the products' weight
# and box, and the customs lines for a parcel going abroad. 'quote' asks every carrier in the
# account; 'buy' asks the owner to approve one rate. Once bought, the order is marked shipped and its
# tracking goes to the store — nothing more to do.
#
# Shippo is used for nothing until one sender address is complete: street, city, postal code,
# country (and state in the US and Canada), and who the parcels are from — name, phone, email.

_LABEL_FORMATS = ("PDF_4x6", "PDF_4x8", "PDF", "PDF_A4", "PDF_A6", "PNG", "ZPLII")

# The fields of a sender address, shared by adding and changing one. A warehouse's address keeps
# its place in the warehouse: street, city, state, zip, country, phone and label change the warehouse.
_ADDRESS_FIELDS = (
    body_field(
        "label",
        help="What to call it ('Garage'); for a warehouse's address, the warehouse's name.",
    ),
    body_field("street1", help="Street and number.", example="215 Clayton St"),
    body_field("street2", help="Apartment, suite, unit."),
    body_field("city", help="City."),
    body_field("state", help="State or region; required in the US and Canada.", example="NY"),
    body_field("zip", help="Postal code."),
    body_field("country", help="Two-letter country code.", example="US"),
    body_field("name", help="Who the parcels are from, as printed on the label."),
    body_field("company", help="Company name, if any."),
    body_field("phone", help="Sender's phone."),
    body_field("email", help="Sender's email."),
)

#: The parcel of a split order a label is for (the order's 'shipments'); its only one otherwise.
_SHIPMENT_FLAG = flag(
    "shipment_id",
    help=(
        "The parcel the label ships, for an order that leaves in several ('shipments' on "
        "'orders get'). Leave it out for an order that ships as one."
    ),
)

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
            "send only what to change otherwise. 'draft' in the answer is the label as priced "
            "(draft.sender_address_id: the address it ships from). A label that cannot be priced "
            "yet answers 422 listing what is missing (details.missing) — e.g. the parcel's weight. "
            "409 shippo_sender_address_required: no sender address is complete — ask the owner "
            "and finish one ('shipping-labels list-addresses', 'update-address'). The order id may "
            "be our id, its number ('#1001') or the marketplace's id. Changes nothing; rates stay "
            "buyable for 7 days."
        ),
        read_only=True,
        timeout=60,
        flags=(_SHIPMENT_FLAG,),
        body=(
            body_field(
                "sender_address_id",
                help=(
                    "Ship from this sender address ('shipping-labels list-addresses'). Default: the "
                    "address of the warehouse the goods are in when complete, else the default one."
                ),
            ),
            body_field(
                "warehouse_id",
                help="Ship from this warehouse of the seller's (its sender address).",
            ),
            body_field(
                "ship_from",
                type=dict,
                help=(
                    "Sender fields to change for this label only — name, company, phone, email — "
                    "or, with street1, city, state, zip or country, a one-off address to ship from. "
                    "To keep an address for every label, add it with 'shipping-labels add-address'."
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
        flags=(_SHIPMENT_FLAG,),
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
                    "PDF_A6, PNG, ZPLII (Zebra printers). Default: the seller's ('get-sender')."
                ),
            ),
        ),
    ),
    Cmd(
        "list-addresses",
        "GET",
        "/agent/shipping/sender-addresses",
        summary=(
            "Where the seller's parcels ship from, the default first: each address's id, title, "
            "origin (warehouse — its place is that warehouse's; store_location; manual), address "
            "(street, city, state, zip, country, name, company, phone, email), is_default, and "
            "'missing' — what it still needs. 'ready' is false until one is complete: until then "
            "nothing can be quoted or bought, and the shop prices no delivery through Shippo."
        ),
        read_only=True,
    ),
    Cmd(
        "add-address",
        "POST",
        "/agent/shipping/sender-addresses",
        summary=(
            "Add a sender address the owner gave. With warehouse_id it is that warehouse's address "
            "(the place given is written into the warehouse). make_default is refused (422 "
            "sender_address_incomplete, details.missing) unless the address is complete."
        ),
        body=(
            *_ADDRESS_FIELDS,
            body_field("warehouse_id", help="Add this warehouse of the seller's as an address."),
            body_field("make_default", type=bool, help="Make it the default."),
        ),
    ),
    Cmd(
        "update-address",
        "PATCH",
        "/agent/shipping/sender-addresses/{address_id}",
        summary=(
            "Finish or correct a sender address with what the owner said; omitted fields stay as "
            "they are, an empty string clears one. A warehouse's place, phone and label go to the "
            "warehouse itself. Answers the address with what it still misses."
        ),
        body=_ADDRESS_FIELDS,
    ),
    Cmd(
        "set-default-address",
        "POST",
        "/agent/shipping/sender-addresses/{address_id}/default",
        summary=(
            "Make a complete sender address the one parcels leave from when the goods' warehouse "
            "has none on the list."
        ),
    ),
    Cmd(
        "remove-address",
        "DELETE",
        "/agent/shipping/sender-addresses/{address_id}",
        summary=(
            "Take a sender address off the list (a warehouse it stood for stays). Only when the "
            "owner asked for it."
        ),
    ),
    Cmd(
        "get-sender",
        "GET",
        "/agent/shipping/sender",
        summary=(
            "The label format the seller's printer takes (label_file_type), with the sender "
            "details new addresses start from: 'profile' (null until saved) and 'suggestion'. Who "
            "a parcel is from is its sender address's ('shipping-labels list-addresses'). "
            "'couriers': the carriers of the seller's Shippo account, each 'enabled' when "
            "SellerClaw prices shop parcels and buys labels with it (null when Shippo could not be "
            "read)."
        ),
    ),
    Cmd(
        "update-sender",
        "PUT",
        "/agent/shipping/sender",
        summary=(
            "Save the label format the owner's printer takes, the sender details new addresses "
            "start from, or the carriers SellerClaw uses. Who a parcel is from is changed on its "
            "address ('update-address')."
        ),
        body=(
            body_field(
                "name",
                help="The name new sender addresses start with.",
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
            body_field(
                "enabled_couriers",
                type=list,
                help=(
                    "The carriers ('couriers' ids from 'get-sender') SellerClaw prices shop parcels "
                    "and buys labels with — only the ones the owner named. Replaces the choice, at "
                    "least one; a carrier added to Shippo later stays off until chosen. Kept as it "
                    "was when omitted."
                ),
                example=["a1b2c3d4e5f6"],
            ),
        ),
    ),
)

app = build_group(NAME, "Courier labels for orders the seller ships, via their Shippo account.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
