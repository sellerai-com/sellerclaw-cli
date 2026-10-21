from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "sellercart-delivery"

_ZONE = (
    "<zone> is the zone's name or key, as `list` shows it; a name nobody has used yet opens a new "
    "zone under it."
)
_METHOD = (
    "<method> is the method's name or key within the zone; a name the zone does not have adds a new "
    "method under it."
)
_KEEP = "Fields left out keep their current value."

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/delivery",
        summary=(
            "Every delivery zone of the shop — its countries, its methods and their prices — and "
            "'warnings' naming what still stops buyers checking out. Read it before changing "
            "anything, and repeat the warnings to the owner. 'shipping_included_in_price' true means "
            "product prices already hold the supplier's delivery, so a method charges only the cost "
            "beyond that and a method priced 0 is free at no loss."
        ),
    ),
    Cmd(
        "set-zone",
        "PUT",
        "/agent/sellercart/delivery/zones/{zone}",
        summary=(
            "Open a delivery zone — a group of countries priced alike — or change one. A new zone "
            "needs 'countries' (or 'everywhere_else') and delivers nowhere until `set-method` gives "
            f"it a method. A country can be in one zone only. {_ZONE} {_KEEP}"
        ),
        body=(
            body_field(
                "countries",
                type=list,
                help="Two-letter country codes. Replaces the zone's whole list.",
                example=["US", "CA"],
            ),
            body_field(
                "everywhere_else",
                type=bool,
                help=(
                    "true: this zone covers every country no other zone names (it then names none "
                    "itself). One such zone per shop."
                ),
            ),
            body_field(
                "free_over",
                type=float,
                nullable=True,
                help=(
                    "Goods total, in the shop's currency, from which the zone's cheapest method is "
                    "free. null withdraws the offer."
                ),
                example=75,
            ),
            body_field("name", help="Rename the zone.", example="European Union"),
        ),
    ),
    Cmd(
        "delete-zone",
        "DELETE",
        "/agent/sellercart/delivery/zones/{zone}",
        summary=(
            "Remove a zone and its methods: buyers in its countries can no longer check out. "
            f"Refused while it is the last way a live shop delivers. {_ZONE}"
        ),
    ),
    Cmd(
        "set-method",
        "PUT",
        "/agent/sellercart/delivery/zones/{zone}/methods/{method}",
        summary=(
            "Add a delivery method to a zone — \"Standard\", \"Express\" — or change one; up to 5 "
            "per zone. Fixed: the buyer pays 'price', raised to the real delivery cost when that is "
            "higher, so the seller never pays for delivery. Calculated: the buyer pays the real cost "
            "from the supplier (CJ, Amazon, Shippo, the warehouse's rates) plus the extras, and "
            "'price' when no cost can be had. Ask the owner for prices — never invent them. "
            f"{_ZONE} {_METHOD} {_KEEP}"
        ),
        body=(
            body_field(
                "price",
                type=float,
                help=(
                    "In the shop's currency. Fixed: its price (0 = free), required for a new one. "
                    "Calculated: what the buyer pays when no cost can be worked out — left out on "
                    "a new one, there is none, and such an order is not offered this method."
                ),
                example=9.99,
            ),
            body_field(
                "calculated",
                type=bool,
                help="true: priced from the real delivery cost plus the extras. Default false.",
            ),
            body_field(
                "pick",
                choices=("cheapest", "fastest"),
                help=(
                    "Which of the supplier's services this method stands for — and the one bought "
                    "when the order is placed. Default cheapest; Express is fastest."
                ),
            ),
            body_field(
                "extra_percent",
                type=float,
                help="Calculated only: a share of the real cost added on top, e.g. 10.",
            ),
            body_field(
                "extra_amount",
                type=float,
                help="Calculated only: a flat amount added once per order, in the shop's currency.",
            ),
            body_field(
                "days_min",
                type=int,
                nullable=True,
                help=(
                    "The seller's promised term in business days, with days_max. Leave both out to "
                    "show the supplier's own estimate; null for both drops a promise."
                ),
                example=2,
            ),
            body_field("days_max", type=int, nullable=True, help="See days_min.", example=4),
            body_field(
                "service",
                nullable=True,
                help=(
                    "A supplier's own service this method stands for, by name — Amazon's "
                    "Standard, Expedited or Priority. A parcel offering it goes by it; others by "
                    "'pick'. null drops it."
                ),
                example="Expedited",
            ),
            body_field("name", help="Rename the method.", example="Express"),
        ),
    ),
    Cmd(
        "delete-method",
        "DELETE",
        "/agent/sellercart/delivery/zones/{zone}/methods/{method}",
        summary=(
            "Remove one method from a zone. Refused while it is the last way a live shop delivers: "
            f"add the replacement first. {_ZONE} {_METHOD}"
        ),
    ),
)

app = build_group(
    NAME,
    "Where the shop delivers: zones of countries, and the methods priced in each.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
