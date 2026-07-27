"""Discovery commands for agents, driven by the live command REGISTRY (no OpenAPI spec).

Replaces the old spec-based `_generic.py`. Commands:
- `guide`    — onboarding: conventions, group list, how to call commands.
- `groups`   — every group with a one-line summary and command count.
- `commands` — flat command list, optionally filtered by `--group`.
- `describe` — full detail for one `<group> <command>`: positionals, flags, body, example.
"""

from __future__ import annotations

import difflib
import json

import typer

from sellerclaw_cli import __version__
from sellerclaw_cli._command_group import REGISTRY, Cmd, positionals_of
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli._output import OutputFormat, print_ok
from sellerclaw_cli._runtime import emit_error


def register(app: typer.Typer) -> None:
    app.command("guide", help="Onboarding for AI agents: conventions, group list, how to call commands.")(
        guide_cmd
    )
    app.command("groups", help="List every command group with a one-line summary and its commands.")(
        groups_cmd
    )
    app.command("commands", help="List commands; filter to one group with --group.")(commands_cmd)
    app.command(
        "describe",
        help=(
            "Show full detail — positionals, flags, body, example — for one command, or for every "
            "command in a group when the command is omitted."
        ),
    )(describe_cmd)


def _fmt(ctx: typer.Context) -> OutputFormat:
    return ctx.obj.get("format", OutputFormat.JSON) if ctx.obj else OutputFormat.JSON


def _flag_repr(group: str, cmd: Cmd) -> list[dict[str, object]]:
    repr_: list[dict[str, object]] = []
    for f in cmd.flags:
        item: dict[str, object] = {
            "flag": f.primary_option,
            "type": f.type.__name__,
            "required": f.required,
            "repeatable": f.repeatable,
            "help": f.help,
        }
        if f.aliases:
            item["aliases"] = list(f.aliases)
        if f.query_key != f.name:
            item["query_param"] = f.query_key
        if f.choices:
            item["choices"] = list(f.choices)
        if f.minimum is not None:
            item["minimum"] = f.minimum
        if f.maximum is not None:
            item["maximum"] = f.maximum
        if f.default is not None:
            item["default"] = f.default
        repr_.append(item)
    return repr_


def _body_repr(cmd: Cmd) -> list[dict[str, object]]:
    repr_: list[dict[str, object]] = []
    for f in cmd.body:
        item: dict[str, object] = {
            "field": f.name,
            "type": f.type.__name__,
            "required": f.required,
            "repeatable": f.repeatable,
            "help": f.help,
        }
        if f.choices:
            item["choices"] = list(f.choices)
        repr_.append(item)
    return repr_


def _body_example(cmd: Cmd) -> dict[str, object]:
    """A minimal example object: required fields (or all, if none are required)."""
    chosen = [f for f in cmd.body if f.required] or list(cmd.body)
    out: dict[str, object] = {}
    for f in chosen:
        if f.example is not None:
            out[f.name] = f.example
        elif f.choices:
            out[f.name] = f.choices[0]
        else:
            placeholder = f"<{f.name}>"
            out[f.name] = [placeholder] if f.repeatable else placeholder
    return out


def _example(group: str, cmd: Cmd) -> str:
    parts = [f"sellerclaw {group} {cmd.name}"]
    parts += [f"<{p}>" for p in positionals_of(cmd.path)]
    parts += [f"--{f.name.replace('_', '-')} <{f.name}>" for f in cmd.flags if f.required]
    if cmd.query_body:
        parts.append("-q '<graphql document>'")
    elif cmd.body:
        parts.append("-b '" + json.dumps(_body_example(cmd), ensure_ascii=False) + "'")
    elif cmd.takes_body:
        parts.append("-b @body.json")
    return " ".join(parts)


def guide_cmd(ctx: typer.Context) -> None:
    payload = {
        "tool": "sellerclaw",
        "version": __version__,
        "what": (
            "Hand-curated CLI over the SellerClaw Agent API. JSON on stdout; structured errors on "
            "stderr with non-zero exit codes (1=user/api, 2=server/network, 3=auth)."
        ),
        "conventions": [
            "Invoke as `sellerclaw <group> <command> [POSITIONAL ...] [--flags] [-b BODY]`.",
            "Verbs are consistent across groups: list, get, create, update, delete, plus domain "
            "verbs (publish, sync, launch, search, pay).",
            "Path / parent ids are POSITIONAL, in path order "
            "(e.g. `sellerclaw shopify-listings list <store_id>`).",
            "Filters are `--flags`. A JSON body uses `-b` (literal JSON, `@file.json`, or `@-` stdin).",
            "Most groups have an `overview` command for a one-call summary.",
        ],
        "discovery": [
            "`sellerclaw describe <group>` — every command in the group with its positionals, "
            "flags, body fields and a ready example. One call; prefer it over the ladder below.",
            "`sellerclaw describe <group> <command>` — the same for a single command.",
            "`sellerclaw groups` — every group with its command names (this payload has them too).",
            "`sellerclaw commands --group <group>` — a flat command list.",
        ],
        "finding_things": [
            "By SellerClaw id: `listings get <listing_id>`, `orders get <order_id>`, "
            "`catalog get <product_id>` — these work across every store; the per-channel groups "
            "(`shopify-listings`, `ebay-orders`, …) do not read a row by id.",
            "Listings of a catalog product (a multi-variant publish makes one listing per variant): "
            "`listings search --product-id <product_id>`. Also `--store-id`, `--sku`, `--remote-id`, "
            "`--platform`, `--status`.",
            "Catalog product by name/SKU/supplier item: `catalog search --q <text>`, "
            "`catalog list --sku <sku>`, `catalog list --supplier-provider cj "
            "--supplier-product-id <id>` (the 'do I already have this?' check).",
            "Orders: `orders search --q <text>` (order number, marketplace id, customer, line-item "
            "SKU/title) or `orders list --product-id <product_id>` (who bought this).",
            "Free-text search accepts any spelling of the flag: --q / --query / --search / --text.",
        ],
        "fixing_errors": [
            "Errors are JSON on stderr: read `error.message` — it names the exact problem and the fix.",
            "Bad `-b` body? The CLI checks it locally first and lists the allowed fields plus the "
            "closest match (e.g. unknown 'note' (did you mean 'message'?)). Run "
            "`sellerclaw describe <group> <command>` and resend with the listed `body_fields`.",
            "`No such command`? The message lists the group's real commands, and says so when the "
            "verb belongs to another group (`shopify-listings get` -> `listings get`).",
        ],
        "auth": {
            "env": ["SELLERCLAW_TOKEN", "SELLERCLAW_API_URL"],
            "commands": ["sellerclaw auth whoami", "sellerclaw auth login", "sellerclaw auth logout"],
        },
        "fallback": (
            "When no curated command fits a Shopify task, run a raw Admin GraphQL query/mutation with "
            "`sellerclaw shopify graphql <store_id> -b '{\"query\": \"...\", \"variables\": {...}}'`."
        ),
        "groups": [
            {"group": g.name, "summary": g.help, "commands": [c.name for c in g.commands]}
            for g in sorted(REGISTRY, key=lambda x: x.name)
        ],
    }
    print_ok(payload, fmt=_fmt(ctx))


def groups_cmd(ctx: typer.Context) -> None:
    # Carry the command names, not just a count: a count tells the caller nothing and forces a
    # second call to find out whether the verb they want even exists here.
    data = [
        {
            "group": g.name,
            "summary": g.help,
            "commands": [c.name for c in g.commands],
        }
        for g in sorted(REGISTRY, key=lambda x: x.name)
    ]
    print_ok(data, fmt=_fmt(ctx))


def commands_cmd(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group", help="Filter to one group."),
) -> None:
    groups = [g for g in REGISTRY if group is None or g.name == group]
    if group is not None and not groups:
        emit_error(UserInputError(f"unknown group: {group!r}. Run `sellerclaw groups`."))
        return
    data = [
        {"group": g.name, "command": c.name, "method": c.method, "summary": c.summary}
        for g in sorted(groups, key=lambda x: x.name)
        for c in g.commands
    ]
    print_ok(data, fmt=_fmt(ctx))


def _command_detail(group: str, cmd: Cmd) -> dict[str, object]:
    """Everything needed to call one command correctly, without a second lookup."""
    return {
        "group": group,
        "command": cmd.name,
        "method": cmd.method,
        "path": cmd.path,
        "summary": cmd.summary,
        "positionals": positionals_of(cmd.path),
        "flags": _flag_repr(group, cmd),
        "body": cmd.takes_body,
        "body_fields": _body_repr(cmd),
        "body_strict": cmd.body_strict if cmd.body else None,
        "body_freeform": cmd.takes_body and not cmd.body and not cmd.query_body,
        "query_body": cmd.query_body,
        # How long this command may legitimately run. A caller that wraps us in a deadline of its own
        # (a shell timeout, an agent's exec budget) has no other way to know that publishing takes
        # minutes where a list takes a moment — and kills a working call for lack of that.
        "timeout_seconds": cmd.effective_timeout,
        "example": _example(group, cmd),
    }


def describe_cmd(
    ctx: typer.Context,
    group: str = typer.Argument(..., help="Group name (see `sellerclaw groups`)."),
    command: str | None = typer.Argument(
        None,
        help="Command name. Omit it to describe every command in the group in one call.",
    ),
) -> None:
    """Describe one command, or — with no command — the whole group at once.

    Describing a whole group is the cheap path: one call returns every command's positionals, flags,
    body fields and a ready example, so nothing else has to be guessed or looked up.
    """
    matched_group = next((g for g in REGISTRY if g.name == group), None)
    if matched_group is None:
        near = difflib.get_close_matches(group, [g.name for g in REGISTRY], n=3, cutoff=0.6)
        suggestion = f" Did you mean: {', '.join(near)}?" if near else ""
        emit_error(
            UserInputError(f"unknown group: {group!r}.{suggestion} Run `sellerclaw groups`.")
        )
        return
    if command is None:
        print_ok(
            {
                "group": matched_group.name,
                "summary": matched_group.help,
                "commands": [
                    _command_detail(matched_group.name, cmd) for cmd in matched_group.commands
                ],
            },
            fmt=_fmt(ctx),
        )
        return
    cmd = next((c for c in matched_group.commands if c.name == command), None)
    if cmd is None:
        names = [c.name for c in matched_group.commands]
        emit_error(
            UserInputError(
                f"unknown command {command!r} in group {group!r}. "
                f"Commands in `{group}`: {', '.join(names)}."
            )
        )
        return
    print_ok(_command_detail(matched_group.name, cmd), fmt=_fmt(ctx))
