"""Discovery commands for agents, driven by the live command REGISTRY (no OpenAPI spec).

Replaces the old spec-based `_generic.py`. Commands:
- `guide`    — onboarding: conventions, group list, how to call commands.
- `groups`   — every group with a one-line summary and command count.
- `commands` — flat command list, optionally filtered by `--group`.
- `describe` — full detail for one `<group> <command>`: positionals, flags, body, example.
"""

from __future__ import annotations

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
    app.command("groups", help="List every command group with a one-line summary and command count.")(
        groups_cmd
    )
    app.command("commands", help="List commands; filter to one group with --group.")(commands_cmd)
    app.command(
        "describe",
        help="Show full detail for one command: positional args, flags, body, and an example.",
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
    if cmd.body:
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
            "`sellerclaw groups` — all groups.",
            "`sellerclaw commands --group <group>` — commands in a group.",
            "`sellerclaw describe <group> <command>` — positionals, flags, body fields, example.",
            "`sellerclaw <group> --help` — the same via Typer help.",
        ],
        "fixing_errors": [
            "Errors are JSON on stderr: read `error.message` — it names the exact problem and the fix.",
            "Bad `-b` body? The CLI checks it locally first and lists the allowed fields plus the "
            "closest match (e.g. unknown 'note' (did you mean 'message'?)). Run "
            "`sellerclaw describe <group> <command>` and resend with the listed `body_fields`.",
            "`No such command` / `No such option`? The message suggests the closest name — or run "
            "`sellerclaw commands --group <group>` / `sellerclaw <group> --help`.",
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
    data = [
        {"group": g.name, "summary": g.help, "command_count": len(g.commands)}
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


def describe_cmd(
    ctx: typer.Context,
    group: str = typer.Argument(..., help="Group name (see `sellerclaw groups`)."),
    command: str = typer.Argument(..., help="Command name (see `sellerclaw commands --group <group>`)."),
) -> None:
    matched_group = next((g for g in REGISTRY if g.name == group), None)
    if matched_group is None:
        emit_error(UserInputError(f"unknown group: {group!r}. Run `sellerclaw groups`."))
        return
    cmd = next((c for c in matched_group.commands if c.name == command), None)
    if cmd is None:
        emit_error(
            UserInputError(
                f"unknown command {command!r} in group {group!r}. "
                f"Run `sellerclaw commands --group {group}`."
            )
        )
        return
    print_ok(
        {
            "group": matched_group.name,
            "command": cmd.name,
            "method": cmd.method,
            "path": cmd.path,
            "summary": cmd.summary,
            "positionals": positionals_of(cmd.path),
            "flags": _flag_repr(matched_group.name, cmd),
            "body": cmd.takes_body,
            "body_fields": _body_repr(cmd),
            "body_strict": cmd.body_strict if cmd.body else None,
            "body_freeform": cmd.takes_body and not cmd.body,
            "example": _example(matched_group.name, cmd),
        },
        fmt=_fmt(ctx),
    )
