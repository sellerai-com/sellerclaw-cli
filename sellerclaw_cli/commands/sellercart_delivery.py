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
            "How the shop's checkout prices delivery, and where it delivers. Each parcel is priced "
            "by whoever sends it: CJ's and Amazon's goods at the supplier's own price (CJ's cheapest "
            "and fastest, Amazon's speeds), the goods the seller sends themselves through their "
            "Shippo when the shop agreed to it ('shippo'), otherwise at the zone's methods — which "
            "price only those. 'breakdown' counts the shelf that way, with the products Shippo "
            "cannot price for want of a weight or a box. The margin — 'margin_percent' of the price, "
            "then 'margin_amount' added to each parcel — rides on the suppliers' and Shippo's prices "
            "only. Read it before changing anything, and repeat the 'warnings' to the owner."
        ),
    ),
    Cmd(
        "set-zone",
        "PUT",
        "/agent/sellercart/delivery/zones/{zone}",
        summary=(
            "Open a delivery zone — a group of countries priced alike — or change one. A new zone "
            "needs 'countries' (or 'everywhere_else'); CJ's and Amazon's goods are delivered there at "
            "once, the seller's own goods once `set-method` prices them. A country can be in one "
            f"zone only. {_ZONE} {_KEEP}"
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
                    "Goods total, in the shop's currency, from which a parcel's cheapest option is "
                    "free — each parcel of an order counts its own goods. null withdraws the offer."
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
            "Add a delivery method for the goods the seller sends themselves — \"Standard\", "
            "\"Express\" — or change one; up to 5 per zone. The buyer pays 'price', or the "
            "'weight_bands' step their parcel's weight falls in (goods and box, or the box by volume "
            "when that weighs more), with no margin on top. A parcel leaving from a country in "
            "'origins' goes by that line instead. CJ's and Amazon's goods never go by these. Ask the "
            f"owner for prices — never invent them. {_ZONE} {_METHOD} {_KEEP}"
        ),
        body=(
            body_field(
                "price",
                type=float,
                help=(
                    "In the shop's currency, 0 = free; required for a new method. With "
                    "'weight_bands', what a parcel of unknown weight costs."
                ),
                example=6.95,
            ),
            body_field(
                "weight_bands",
                type=list,
                help=(
                    "Prices by parcel weight, ascending: objects with 'up_to_grams' and 'price'; "
                    "the last has no 'up_to_grams' (\"and heavier\"). Replaces the whole list; [] "
                    "drops it."
                ),
                example=[
                    {"up_to_grams": 500, "price": 4},
                    {"up_to_grams": 2000, "price": 7},
                    {"price": 12},
                ],
            ),
            body_field(
                "days_min",
                type=int,
                nullable=True,
                help=(
                    "The seller's promised term in business days, with days_max — both or neither; "
                    "null for both drops it."
                ),
                example=3,
            ),
            body_field("days_max", type=int, nullable=True, help="See days_min.", example=5),
            body_field(
                "origins",
                type=list,
                help=(
                    "Lines for parcels leaving from one country: objects with 'country' (two "
                    "letters), 'price', and optionally 'weight_bands', 'days_min', 'days_max'. "
                    "Every other parcel goes by the method's own line. Replaces the whole list; [] "
                    "drops them."
                ),
                example=[{"country": "CN", "price": 3, "days_min": 10, "days_max": 20}],
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
    "Where the shop delivers: zones of countries, and the seller's own methods priced in each.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
