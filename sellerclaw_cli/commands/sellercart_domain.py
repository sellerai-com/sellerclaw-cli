from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "sellercart-domain"

SPECS = (
    Cmd(
        "status",
        "GET",
        "/agent/sellercart/domain",
        summary=(
            "The shop's custom domain and how far it is from live, or that this deployment has none. "
            "'available': false means custom domains are switched off here — say so rather than "
            "walking the seller into a step that cannot finish."
        ),
    ),
    Cmd(
        "connect",
        "POST",
        "/agent/sellercart/domain",
        summary=(
            "Attach a domain the seller already owns and get back the DNS record that brings it live. "
            "Read 'dns_records' out to them verbatim — name, type and value — because they type it "
            "into their registrar by hand, and a value you paraphrase never verifies."
        ),
        body=(
            body_field(
                "hostname",
                required=True,
                help="The domain or subdomain to point at the shop.",
                example="shop.example.com",
            ),
        ),
    ),
    Cmd(
        "check",
        "POST",
        "/agent/sellercart/domain/check",
        summary=(
            "Force a re-check against the provider, after the seller says they added the DNS record. "
            "DNS takes minutes to hours to spread, so a domain still 'pending' here is normal rather "
            "than a fault — check again later instead of re-connecting it."
        ),
    ),
    Cmd(
        "disconnect",
        "DELETE",
        "/agent/sellercart/domain",
        summary=(
            "Detach the custom domain. The shop reverts to its <slug>.sellercart.shop address and "
            "nothing else changes — but every link the seller published on the old domain dies, so "
            "confirm with them first."
        ),
    ),
)

app = build_group(NAME, "The shop's own domain name.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
