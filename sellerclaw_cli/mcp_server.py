"""MCP (Model Context Protocol) server exposing the SellerClaw CLI to any MCP client.

Why a *proxy*, not one tool per command
---------------------------------------
The CLI carries ~250 commands across ~45 groups. Emitting one MCP tool per command would
swamp any client (huge tool list, poor selection, wasted context). Instead this mirrors the
CLI's own agent-first discovery model with **three thin tools**:

* ``sellerclaw_groups``   — list command groups and the commands inside each;
* ``sellerclaw_describe`` — full schema for one command (positionals, flags, body fields);
* ``sellerclaw_run``      — invoke a command.

A client (e.g. Claude) discovers commands at runtime exactly as the OpenClaw agent does via
``sellerclaw groups`` -> ``describe`` -> invoke. New CLI commands appear automatically with no
change here, and the MCP surface can never drift from the CLI because both read the same live
``REGISTRY`` and execute through the same :class:`~sellerclaw_cli._client.Client` (auth, retries,
structured errors).

Running
-------
The ``mcp`` SDK is an optional dependency (imported lazily, so the core CLI never depends on it)::

    pip install 'sellerclaw-cli[mcp]'
    sellerclaw mcp            # subcommand on the main binary
    # or the dedicated console script:
    sellerclaw-mcp

The server speaks MCP over **stdio**, which is what Claude Desktop / Claude Code / the Agent SDK
launch. Authentication is inherited from the usual CLI config — ``SELLERCLAW_TOKEN`` +
``SELLERCLAW_API_URL`` (or a prior ``sellerclaw auth login``) — so calls act as that agent/user.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sellerclaw_cli._client import Client
from sellerclaw_cli._command_group import REGISTRY, Cmd, Flag, GroupSpec, positionals_of
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.commands._discover import _body_example

if TYPE_CHECKING:
    import typer

SERVER_NAME = "sellerclaw"

SERVER_INSTRUCTIONS = (
    "SellerClaw e-commerce control over the seller's stores, orders, listings, ads, suppliers, "
    "email and research. The surface is large, so discover before you call:\n"
    "1. `sellerclaw_groups` — list command groups and their commands.\n"
    "2. `sellerclaw_describe(group, command)` — exact positionals, flags and JSON body fields, "
    "plus a ready `call_example` for `sellerclaw_run`.\n"
    "3. `sellerclaw_run(group, command, positionals, flags, body)` — invoke it.\n"
    "Always describe a command before running it the first time. Some actions (e.g. sending email "
    "or marketing campaigns) are gated server-side and need the owner's approval."
)

_GROUPS_TOOL_DESC = (
    "List every SellerClaw command group (stores, orders, listings, ads, suppliers, email, "
    "research, …) with the commands inside each. Start here, then call sellerclaw_describe."
)
_DESCRIBE_TOOL_DESC = (
    "Full schema for one command: HTTP method, positional arguments (in order), query flags "
    "(with types/choices/ranges), JSON body fields, and a ready-to-use call_example for "
    "sellerclaw_run. Call this before sellerclaw_run the first time you use a command."
)
_RUN_TOOL_DESC = (
    "Invoke a SellerClaw command. `positionals` is a {name: value} map for the path arguments, "
    "`flags` a {name: value} map of filters, and `body` the JSON payload for write commands. "
    "Use sellerclaw_describe to learn the exact names. Returns the API response JSON."
)


def _resolve(group: str, command: str) -> tuple[GroupSpec, Cmd]:
    """Find the (group, command) pair in the registry, or raise an actionable error."""
    matched = next((g for g in REGISTRY if g.name == group), None)
    if matched is None:
        names = ", ".join(sorted(g.name for g in REGISTRY))
        raise UserInputError(f"unknown group {group!r}. Call sellerclaw_groups. Available: {names}.")
    cmd = next((c for c in matched.commands if c.name == command), None)
    if cmd is None:
        names = ", ".join(sorted(c.name for c in matched.commands))
        raise UserInputError(
            f"unknown command {command!r} in group {group!r}. Commands: {names}."
        )
    return matched, cmd


def _flag_schema(f: Flag) -> dict[str, Any]:
    """One flag rendered as a `sellerclaw_run` input key (snake_case ``name``), with constraints."""
    item: dict[str, Any] = {
        "name": f.name,
        "type": f.type.__name__,
        "required": f.required,
        "repeatable": f.repeatable,
        "help": f.help,
    }
    if f.choices:
        item["choices"] = list(f.choices)
    if f.minimum is not None:
        item["minimum"] = f.minimum
    if f.maximum is not None:
        item["maximum"] = f.maximum
    if f.default is not None:
        item["default"] = f.default
    return item


def _body_schema(b: Any) -> dict[str, Any]:
    """One declared body field rendered as a `sellerclaw_run` ``body`` key."""
    item: dict[str, Any] = {
        "name": b.name,
        "type": b.type.__name__,
        "required": b.required,
        "repeatable": b.repeatable,
        "help": b.help,
    }
    if b.choices:
        item["choices"] = list(b.choices)
    return item


def _call_example(group: str, cmd: Cmd) -> dict[str, Any]:
    """A concrete `sellerclaw_run` argument object teaching the exact call shape."""
    example: dict[str, Any] = {"group": group, "command": cmd.name}
    positionals = positionals_of(cmd.path)
    if positionals:
        example["positionals"] = {p: f"<{p}>" for p in positionals}
    required_flags = {
        f.name: (f.choices[0] if f.choices else f"<{f.name}>") for f in cmd.flags if f.required
    }
    if required_flags:
        example["flags"] = required_flags
    if cmd.body:
        example["body"] = _body_example(cmd)
    elif cmd.takes_body:
        example["body"] = {"_comment": "free-form JSON; see body_freeform"}
    return example


def list_groups() -> list[dict[str, Any]]:
    """Return every command group with its commands. The first call an agent should make."""
    return [
        {
            "group": g.name,
            "summary": g.help,
            "commands": [
                {"name": c.name, "method": c.method, "summary": c.summary} for c in g.commands
            ],
        }
        for g in sorted(REGISTRY, key=lambda x: x.name)
    ]


def describe_command(group: str, command: str) -> dict[str, Any]:
    """Return the full schema for one command so the caller can build a valid sellerclaw_run."""
    matched, cmd = _resolve(group, command)
    return {
        "group": matched.name,
        "command": cmd.name,
        "method": cmd.method,
        "path": cmd.path,
        "summary": cmd.summary,
        "positionals": positionals_of(cmd.path),
        "flags": [_flag_schema(f) for f in cmd.flags],
        "takes_body": cmd.takes_body,
        "body_freeform": cmd.takes_body and not cmd.body,
        "body_fields": [_body_schema(b) for b in cmd.body],
        "call_example": _call_example(matched.name, cmd),
    }


def run_command(
    group: str,
    command: str,
    positionals: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    """Execute a command against the SellerClaw Agent API and return the parsed JSON response.

    ``positionals`` fills the path placeholders, ``flags`` becomes the query string, and ``body``
    is sent as the JSON payload. Names come from ``sellerclaw_describe``; flag names are accepted
    in snake_case, kebab-case, or with a leading ``--``. Unknown groups/commands/flags and missing
    positionals raise a clear error; API failures surface the server's structured message.
    """
    matched, cmd = _resolve(group, command)
    positionals = positionals or {}
    flags = flags or {}

    needed = positionals_of(cmd.path)
    missing = [p for p in needed if positionals.get(p) in (None, "")]
    if missing:
        raise UserInputError(
            f"missing positional argument(s) for {group} {command}: {', '.join(missing)} "
            f"(order: {', '.join(needed)}). Call sellerclaw_describe for the schema."
        )
    path = cmd.path
    for name in needed:
        path = path.replace("{" + name + "}", str(positionals[name]))

    params = _map_flags(group, command, cmd, flags)

    if body is not None and not cmd.takes_body:
        raise UserInputError(f"{group} {command} does not take a body; drop the `body` argument.")

    with Client.from_env() as client:
        return client.request(cmd.method, path, params=params or None, json=body)


def _map_flags(group: str, command: str, cmd: Cmd, flags: dict[str, Any]) -> dict[str, Any]:
    """Map a {name: value} flag map to API query params, dropping unset values.

    Accepts a flag's snake_case name, its ``--kebab`` spelling, or any documented alias. Unknown
    flags raise so the caller fixes the call instead of silently dropping a filter.
    """
    lookup: dict[str, Flag] = {}
    for f in cmd.flags:
        lookup[f.name] = f
        for spelling in f.option_names:
            lookup[spelling.lstrip("-").replace("-", "_")] = f

    params: dict[str, Any] = {}
    for raw_key, value in flags.items():
        normalized = raw_key.lstrip("-").replace("-", "_")
        flag = lookup.get(normalized)
        if flag is None:
            allowed = ", ".join(sorted(f.name for f in cmd.flags)) or "(none)"
            raise UserInputError(
                f"unknown flag {raw_key!r} for {group} {command}. Allowed: {allowed}. "
                f"Call sellerclaw_describe for the schema."
            )
        if value is None or value == [] or value is False:
            continue
        params[flag.query_key] = value
    return params


def build_server() -> Any:
    """Construct the FastMCP server with the three discovery/proxy tools.

    The optional ``mcp`` SDK is imported here (not at module load) so importing this module — and
    the core CLI — never requires it. Importing the CLI package populates the command ``REGISTRY``.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise UserInputError(
            "the MCP server needs the optional 'mcp' dependency. "
            "Install it with: pip install 'sellerclaw-cli[mcp]'."
        ) from exc

    import sellerclaw_cli.cli  # noqa: F401 — importing registers every group into REGISTRY

    server = FastMCP(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    server.add_tool(list_groups, name="sellerclaw_groups", description=_GROUPS_TOOL_DESC)
    server.add_tool(describe_command, name="sellerclaw_describe", description=_DESCRIBE_TOOL_DESC)
    server.add_tool(run_command, name="sellerclaw_run", description=_RUN_TOOL_DESC)
    return server


def serve() -> None:
    """Build the server and serve over stdio. Blocks until the client disconnects."""
    _warn_if_unauthenticated()
    build_server().run()  # transport defaults to "stdio"


def _warn_if_unauthenticated() -> None:
    """Nudge the human if no token is configured, so they don't have to guess why commands fail.

    Written to stderr (never stdout, which carries the MCP protocol) — clients surface it in their
    logs. We warn rather than block: discovery (``sellerclaw_groups`` / ``sellerclaw_describe``) needs
    no auth, only ``sellerclaw_run`` does, so the server still starts and the client can explore.
    """
    import sys

    from sellerclaw_cli import _config

    if _config.load().token is None:
        sys.stderr.write(
            "sellerclaw MCP: not signed in. Run `sellerclaw auth login` once in a terminal to "
            "enable commands that touch the account (discovery tools work without it).\n"
        )


def register(app: typer.Typer) -> None:
    """Mount a ``sellerclaw mcp`` subcommand on the main CLI app."""

    @app.command(
        "mcp",
        help=(
            "Run the MCP server (stdio) exposing this CLI to MCP clients like Claude. "
            "Requires `pip install 'sellerclaw-cli[mcp]'`."
        ),
    )
    def mcp_cmd() -> None:
        from sellerclaw_cli._runtime import emit_error

        try:
            serve()
        except UserInputError as err:
            emit_error(err)  # surfaces the structured stderr contract + non-zero exit


def main() -> None:
    """Console entry point for the dedicated ``sellerclaw-mcp`` script."""
    import sys

    try:
        serve()
    except UserInputError as err:
        sys.stderr.write(err.message + "\n")
        raise SystemExit(1) from None
