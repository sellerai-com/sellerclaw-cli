from __future__ import annotations

import difflib

import click
import typer

# typer >= 0.26 ships its own vendored copy of click as ``typer._click``. The running
# Typer app raises usage errors (NoSuchOption / NoSuchCommand / ...) as instances of
# THAT module's exception classes, which are *not* the public ``click`` package's. So
# our interception in ``main()`` must match both — match only public ``click`` and the
# vendored exceptions fall through to the generic handler and exit 2 instead of 1.
try:
    from typer import _click as _typer_click  # type: ignore[attr-defined]
except ImportError:  # older typer uses the public click package directly
    _typer_click = click

from sellerclaw_cli import __version__
from sellerclaw_cli._command_group import REGISTRY, positionals_of
from sellerclaw_cli._errors import ServerError, UserInputError
from sellerclaw_cli._output import OutputFormat, print_error
from sellerclaw_cli.commands import (
    _auth_cli,
    _discover,
    account,
    action_requests,
    ad_accounts,
    agent_files,
    amazon,
    amazon_listings,
    amazon_orders,
    amazon_store,
    analytics,
    catalog,
    channels,
    chats,
    ebay,
    ebay_finances,
    ebay_listings,
    ebay_orders,
    ebay_promoted,
    ebay_store,
    email,
    facebook_ads,
    goals,
    google_ads,
    integrations,
    kb,
    klaviyo,
    listings,
    media,
    orders,
    research_catalog,
    research_seo,
    research_social,
    research_trends,
    shopify,
    shopify_collections,
    shopify_finances,
    shopify_listings,
    shopify_menus,
    shopify_orders,
    shopify_pages,
    shopify_store,
    shopify_themes,
    social,
    spreadsheet,
    store_audit,
    subagent_tasks,
    suppliers,
    team_tasks,
    web,
    woocommerce,
    woocommerce_listings,
    woocommerce_orders,
    woocommerce_store,
)

# Match usage/abort errors raised by either the public click package or typer's vendored
# copy (see the ``_typer_click`` shim above) so ``main()`` never lets a vendored exception
# fall through to the generic handler.
_USAGE_ERRORS = (click.exceptions.UsageError, _typer_click.exceptions.UsageError)
_NO_SUCH_OPTION = (click.exceptions.NoSuchOption, _typer_click.exceptions.NoSuchOption)
_ABORTS = (click.exceptions.Abort, _typer_click.exceptions.Abort)
_CLICK_EXCEPTIONS = (click.ClickException, _typer_click.ClickException)

app = typer.Typer(
    name="sellerclaw",
    help=(
        "Command-line client for the SellerClaw Agent API (hand-curated for AI agents).\n\n"
        "Quick start: run `sellerclaw guide` for conventions, the group list, and how to call "
        "commands.\n\n"
        "Discovery: `sellerclaw groups` -> `sellerclaw commands --group <group>` -> "
        "`sellerclaw describe <group> <command>` (or `sellerclaw <group> --help`).\n"
        "Invoke: `sellerclaw <group> <command> [POSITIONAL ...] [--flags] [-b BODY]`.\n\n"
        "All output is JSON on stdout; structured errors go to stderr with non-zero exit codes "
        "(1=user/api, 2=server/network, 3=auth)."
    ),
    add_completion=True,
)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    fmt: OutputFormat = typer.Option(
        OutputFormat.JSON,
        "--format",
        "-f",
        help="Output format. Default 'json' (single-line, LLM-friendly).",
        case_sensitive=False,
    ),
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(0)
    ctx.ensure_object(dict)
    ctx.obj["format"] = fmt
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


# Discovery + auth + file uploads (hand-written, non-declarative).
_discover.register(app)
_auth_cli.register(app)
agent_files.register(app)

# MCP server subcommand (`sellerclaw mcp`). The module imports the optional `mcp` SDK lazily, so
# this registration adds no import cost or hard dependency to the base CLI.
from sellerclaw_cli import mcp_server  # noqa: E402 — registered alongside the other subcommands

mcp_server.register(app)

# Hand-curated command groups (declarative; see _command_group.py and commands/<group>.py).
_GROUPS = (
    account,
    ad_accounts,
    analytics,
    catalog,
    orders,
    listings,
    channels,
    chats,
    integrations,
    kb,
    klaviyo,
    suppliers,
    subagent_tasks,
    team_tasks,
    action_requests,
    email,
    social,
    goals,
    google_ads,
    facebook_ads,
    media,
    shopify_listings,
    shopify_orders,
    shopify_store,
    shopify,
    shopify_collections,
    shopify_finances,
    shopify_pages,
    shopify_menus,
    shopify_themes,
    ebay_listings,
    ebay_orders,
    ebay_store,
    ebay_finances,
    ebay_promoted,
    ebay,
    amazon_listings,
    amazon_orders,
    amazon_store,
    amazon,
    spreadsheet,
    research_seo,
    research_social,
    research_trends,
    research_catalog,
    web,
)

for _group in _GROUPS:
    _group.register(app)


def _spec_for(group: str | None, command: str | None):
    """The declarative ``Cmd`` for a group+command, or None (root/hand-written commands)."""
    if group is None or command is None:
        return None
    for g in REGISTRY:
        if g.name == group:
            return next((c for c in g.commands if c.name == command), None)
    return None


def _group_and_command(ctx: click.Context | None) -> tuple[str | None, str | None]:
    """Best-effort (group, command) for the context where a usage error fired.

    Errors at a command ctx → (group, command); at a group ctx → (group, None); at root → (None, None).
    """
    if ctx is None or ctx.parent is None:
        return None, None
    if ctx.parent.parent is None:
        return ctx.info_name, None  # ctx is a group (or a root-level command)
    return ctx.parent.info_name, ctx.info_name


def _quoted_token(message: str) -> str | None:
    """Pull the offending name out of a Click message like ``No such command 'progress'.``"""
    start = message.find("'")
    end = message.find("'", start + 1)
    return message[start + 1 : end] if 0 <= start < end else None


def _emit_usage_error(exc: click.exceptions.UsageError) -> int:
    """Re-emit a Click usage error in our structured stderr contract with a fix to try.

    Click's default "No such option/command" is terse and exits 2; an agent then guesses. We add the
    closest match, flag the two confusions that bite most (a `--flag` on a body command, a `--flag`
    that is really a positional), and point at `describe` — so the next attempt is informed.
    """
    ctx = getattr(exc, "ctx", None)
    group, command = _group_and_command(ctx)
    spec = _spec_for(group, command)
    parts: list[str] = [exc.format_message()]  # already includes Click's own "Did you mean …?" for options

    if isinstance(exc, _NO_SUCH_OPTION):
        bad = (exc.option_name or "").lstrip("-")
        if spec is not None and bad in positionals_of(spec.path):
            parts.append(f"`{bad}` is a positional argument — pass it without `--`, in path order.")
        if spec is not None and spec.body:
            fields = ", ".join(f.name for f in spec.body)
            parts.append(f"This command takes a JSON body via -b, not --options (fields: {fields}).")
        elif spec is not None and (spec.body_freeform or spec.has_body):
            parts.append("This command takes a free-form JSON body via -b, not --options.")
    elif command is None and "No such command" in exc.format_message():
        bad = _quoted_token(exc.format_message())
        names = [c.name for c in next((g.commands for g in REGISTRY if g.name == group), ())]
        near = difflib.get_close_matches(bad, names, n=2, cutoff=0.5) if bad else []
        if near:
            parts.append("Did you mean: " + ", ".join(near) + "?")

    if group and command:
        parts.append(f"Run `sellerclaw describe {group} {command}` for positionals, options, and body fields.")
    elif group:
        parts.append(f"Run `sellerclaw commands --group {group}` to list its commands.")
    else:
        parts.append("Run `sellerclaw groups` to list command groups.")

    print_error(UserInputError(" ".join(parts)))
    return UserInputError.exit_code


def main() -> None:
    """Console entry point. Runs the Typer app with ``standalone_mode=False`` so Click usage errors
    surface as our structured, self-correcting JSON instead of Click's terse default box.

    With ``standalone_mode=False`` Click *returns* the exit code from ``typer.Exit`` / ``ctx.exit`` (help,
    version, our already-printed errors) instead of calling ``sys.exit`` — so we propagate that return
    value; only genuinely uncaught exceptions reach the ``except`` arms.
    """
    try:
        code = app(standalone_mode=False)
    except _USAGE_ERRORS as exc:
        raise SystemExit(_emit_usage_error(exc)) from None
    except _ABORTS:
        print_error(UserInputError("aborted"))
        raise SystemExit(1) from None
    except _CLICK_EXCEPTIONS as exc:
        print_error(UserInputError(exc.format_message()))
        raise SystemExit(exc.exit_code) from None
    except SystemExit:
        raise
    except Exception as exc:  # never leak a raw traceback to an agent
        print_error(ServerError(f"unexpected CLI error: {type(exc).__name__}: {exc}"))
        raise SystemExit(2) from None
    raise SystemExit(code or 0)
