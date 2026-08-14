"""MCP (Model Context Protocol) server exposing the SellerClaw CLI to any MCP client.

Why a *proxy*, not one tool per command
---------------------------------------
The CLI carries ~250 commands across ~45 groups. Emitting one MCP tool per command would
swamp any client (huge tool list, poor selection, wasted context). Instead this mirrors the
CLI's own agent-first discovery model with **four thin tools**:

* ``sellerclaw_groups``   — list command groups and the commands inside each;
* ``sellerclaw_describe`` — full schema for one command (positionals, flags, body fields);
* ``sellerclaw_run``      — invoke a command;
* ``sellerclaw_guide``    — a task guide with ready-to-run examples for a whole area of work.

A client (e.g. Claude) discovers commands at runtime exactly as the OpenClaw agent does via
``sellerclaw groups`` -> ``describe`` -> invoke. New CLI commands appear automatically with no
change here, and the MCP surface can never drift from the CLI because both read the same live
``REGISTRY`` and execute through the same :class:`~sellerclaw_cli._client.Client` (auth, retries,
structured errors).

``sellerclaw_guide`` exists because schemas alone do not teach a workflow. Claude Code and claude.ai
get that knowledge as plugin skills; an MCP client (Claude Desktop's extension, Cursor, the hosted
connector) has no skills at all and would otherwise re-derive every multi-step job from field lists.
It serves :mod:`sellerclaw_cli.guides` — the same files the plugin's skills are compiled from.

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

from sellerclaw_cli import guides
from sellerclaw_cli._client import Client
from sellerclaw_cli._command_group import REGISTRY, Cmd, Flag, GroupSpec, positionals_of
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.commands._discover import _body_example

if TYPE_CHECKING:
    import typer

SERVER_NAME = "sellerclaw"

# Where someone can read what this server is, and the logo to show beside it. Both are standard
# server metadata (``websiteUrl`` / ``icons`` in the initialize response): a client that renders
# them shows SellerClaw's own branding instead of a generic tile, and a client that does not —
# claude.ai's custom connectors today — ignores them at no cost.
SERVER_WEBSITE_URL = "https://sellerclaw.ai"
_ICON_MIME_TYPE = "image/png"
_ICON_SIZES = ["512x512"]

SERVER_INSTRUCTIONS = (
    "SellerClaw e-commerce control over the seller's stores, orders, listings, ads, suppliers, "
    "email and research. The surface is large, so start with the guide for the job:\n"
    "0. `sellerclaw_guide(topic)` — a short guide with ready-to-run calls for publishing and "
    "maintaining listings, fulfilling orders, running ads and campaigns, market research, or how "
    "the business is doing. Call it with no topic for the list, and read `start` once for the "
    "conventions every job shares. Prefer running a guide's example over re-deriving the call.\n"
    "For anything the guides do not cover, discover it:\n"
    "1. `sellerclaw_groups` — list command groups and their commands.\n"
    "2. `sellerclaw_describe(group)` — every command in that group with its positionals, flags, "
    "JSON body fields and a ready `call_example`. Pass `command` too for just one of them.\n"
    "3. `sellerclaw_run(group, command, positionals, flags, body)` — invoke it.\n"
    "Describe a command before running it the first time unless a guide already shows the call. "
    "Some actions (e.g. sending email or marketing campaigns) are gated server-side and need the "
    "owner's approval.\n"
    "Finding things: read one row by its SellerClaw id with the channel-agnostic groups — "
    "`listings get`, `orders get`, `catalog get` (the per-channel groups like `shopify-listings` "
    "do not read by id). `listings search` finds listings by product_id (one row per variant), "
    "store, SKU, marketplace id, channel or status; `catalog list` finds a product by exact SKU or "
    "by supplier item; `orders list` takes a product_id (who bought this).\n"
    "How the business is doing — sales, profit, best sellers, trends, what to reorder, where buyers "
    "are, cash tied up in stock, what needs attention today — is the `analytics` group. Every "
    "command there takes the same period (a `period` keyword, or `week`/`month` for a COMPLETED "
    "week/month, or `from`+`to` dates) and the same store selection (a store id, `all` for every "
    "store, or a repeated `store` flag). Ask for several stores in one call rather than adding up "
    "per-store answers — totals add, averages and shares do not. Answers carry a `coverage` block: "
    'a `history_status` of "syncing" means that store is still importing its sales history, so the '
    "figures are real but partial and must be reported as such."
)

_GROUPS_TOOL_DESC = (
    "List every SellerClaw command group (stores, orders, listings, ads, suppliers, email, "
    "research, …) with the commands inside each. Start here, then call sellerclaw_describe."
)
_DESCRIBE_TOOL_DESC = (
    "Full schema — HTTP method, positional arguments (in order), query flags (with "
    "types/choices/ranges), JSON body fields, and a ready-to-use call_example for sellerclaw_run. "
    "Pass only `group` to get every command in it in one call; add `command` for a single one. "
    "Call this before sellerclaw_run the first time you use a command."
)
_RUN_TOOL_DESC = (
    "Invoke a SellerClaw command. `positionals` is a {name: value} map for the path arguments, "
    "`flags` a {name: value} map of filters, and `body` the JSON payload for write commands. "
    "Use sellerclaw_describe to learn the exact names. Returns the API response JSON."
)
_GUIDE_TOOL_DESC = (
    "Read the task guide for an area of work: `listings` (publish and maintain marketplace "
    "listings), `orders` (find, fulfill, ship, cancel), `ads` (Google, Meta, eBay Promoted, Klaviyo "
    "campaigns), `research` (keywords, trends, competitors, social), `analytics` (how the business "
    "is doing), or `start` (how a call is shaped and the rules every job shares). Each guide is "
    "short and carries ready-to-run sellerclaw_run examples — read the relevant one before a "
    "multi-step job instead of deriving the calls from schemas. Omit `topic` to list them."
)


# --------------------------------------------------------------------------------------------- #
# Audience filter — which command groups the MCP server exposes.
#
# The CLI ships the *full* REGISTRY because the self-hosted OpenClaw agent (the sellerclaw-agent
# repo) drives the same binary and needs its own operating system: the supervisor/subagent task
# tree, goal lifecycle, owner action-requests, owner-chat reads, in-chat media and the agent file
# library. An MCP client, by contrast, is a *human* running their own store through Claude (or
# another MCP agent) — that person already IS the owner, so those orchestration / escalate-to-owner
# groups are redundant or inverted for them.
#
# So the MCP face is an allowlist: only the store-management surface below is discoverable and
# callable. Everything else stays in the CLI but is invisible to `sellerclaw_groups` /
# `sellerclaw_describe` / `sellerclaw_run`. An allowlist (not a denylist) means a new
# agent-internal group added later never leaks to users by default.
MCP_VISIBLE_GROUPS: frozenset[str] = frozenset(
    {
        # Stores, integrations, account
        "channels",
        "integrations",
        "account",
        # Shopify
        "shopify-store",
        "shopify-listings",
        "shopify-orders",
        "shopify-finances",
        "shopify",
        # eBay
        "ebay-store",
        "ebay-listings",
        "ebay-orders",
        "ebay-finances",
        "ebay-promoted",
        "ebay",
        # Amazon
        "amazon-store",
        "amazon-listings",
        "amazon-orders",
        "amazon",
        # Internal catalog, orders, analytics
        "catalog",
        "orders",
        "listings",
        "analytics",
        # Marketing & ads
        "ad-accounts",
        "google-ads",
        "facebook-ads",
        "klaviyo",
        "email",
        # Suppliers
        "suppliers",
        # Research & knowledge
        "research-seo",
        "research-social",
        "research-trends",
        "research-catalog",
        "store-audit",
        "kb",
    }
)


def _visible_groups() -> list[GroupSpec]:
    """Registry groups the MCP server exposes to clients (see :data:`MCP_VISIBLE_GROUPS`)."""
    return [g for g in REGISTRY if g.name in MCP_VISIBLE_GROUPS]


def _resolve_group(group: str) -> GroupSpec:
    """Find an MCP-visible group, or raise an actionable error."""
    visible = _visible_groups()
    matched = next((g for g in visible if g.name == group), None)
    if matched is None:
        names = ", ".join(sorted(g.name for g in visible))
        raise UserInputError(f"unknown group {group!r}. Call sellerclaw_groups. Available: {names}.")
    return matched


def _sibling_group_hint(group: str, wanted: str) -> str:
    """Point a channel group at the channel-agnostic group that owns the verb, if one does.

    ``shopify-listings`` and friends carry only channel-specific verbs; reading one row by its
    SellerClaw id lives in the cross-channel ``listings`` / ``orders`` group, because the id is not
    scoped to a channel. Derived from the registry, so a channel added later is covered for free.
    """
    if "-" not in group:
        return ""
    entity = group.rsplit("-", 1)[-1]
    sibling = next((g for g in _visible_groups() if g.name == entity), None)
    if sibling is None or not any(c.name == wanted for c in sibling.commands):
        return ""
    return f" `{wanted}` lives in the channel-agnostic group instead: group='{entity}'."


def _resolve(group: str, command: str) -> tuple[GroupSpec, Cmd]:
    """Find the (group, command) pair among the MCP-visible groups, or raise an actionable error.

    Groups outside :data:`MCP_VISIBLE_GROUPS` are invisible here even though they exist in the CLI,
    so they read as unknown — an MCP client can neither describe nor run them.
    """
    matched = _resolve_group(group)
    cmd = next((c for c in matched.commands if c.name == command), None)
    if cmd is None:
        names = ", ".join(sorted(c.name for c in matched.commands))
        raise UserInputError(
            f"unknown command {command!r} in group {group!r}."
            f"{_sibling_group_hint(group, command)} Commands: {names}."
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
    if f.aliases:
        # Free-text search answers to --q / --query / --search / --text whichever one the command
        # declares; surfacing the aliases means a caller's first guess is accepted.
        item["also_accepted_as"] = [a.lstrip("-").replace("-", "_") for a in f.aliases]
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
    if b.nullable:
        # Said only where it is true: here ``null`` is a value meaning "unset this", so a caller
        # that reads the schema knows it has a way to clear the setting.
        item["nullable"] = True
    if b.clearable:
        # The same question, answered by the empty string instead: ``""`` clears the stored value
        # and returns the setting to the API's own default.
        item["clearable"] = True
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
    """Return every MCP-visible command group with its commands. The first call an agent makes."""
    return [
        {
            "group": g.name,
            "summary": g.help,
            "commands": [
                {"name": c.name, "method": c.method, "summary": c.summary} for c in g.commands
            ],
        }
        for g in sorted(_visible_groups(), key=lambda x: x.name)
    ]


def show_guide(topic: str | None = None) -> str:
    """Return one task guide as markdown, or the list of topics when none is given.

    The guides are the workflow knowledge a bare MCP client has no other way to get: schemas say
    what a command accepts, not which three calls fulfil an order. Unknown topics raise with the
    list, so a wrong guess costs one turn instead of a silent empty answer.

    Markdown, not a JSON object: the whole payload is prose meant to be read, and wrapping it would
    only escape every newline in the guide for no reader's benefit.
    """
    if topic is None or not str(topic).strip():
        lines = [f"- `{g.topic}` — {g.description}" for g in guides.topics()]
        return (
            "SellerClaw task guides:\n"
            + "\n".join(lines)
            + "\n\nCall sellerclaw_guide again with one of these topics to read it."
        )
    return guides.read(topic)


def _command_schema(group: str, cmd: Cmd) -> dict[str, Any]:
    """Everything needed to build a valid `sellerclaw_run` for one command."""
    return {
        "group": group,
        "command": cmd.name,
        "method": cmd.method,
        "path": cmd.path,
        "summary": cmd.summary,
        "positionals": positionals_of(cmd.path),
        "flags": [_flag_schema(f) for f in cmd.flags],
        "takes_body": cmd.takes_body,
        "body_freeform": cmd.takes_body and not cmd.body,
        "body_fields": [_body_schema(b) for b in cmd.body],
        "call_example": _call_example(group, cmd),
    }


def describe_command(group: str, command: str | None = None) -> dict[str, Any]:
    """Return the full schema for one command — or for every command in the group at once.

    Omitting ``command`` describes the whole group in a single call, so the caller learns every
    verb, flag and body field of an area without a lookup per command.
    """
    if command is None:
        matched = _resolve_group(group)
        return {
            "group": matched.name,
            "summary": matched.help,
            "commands": [_command_schema(matched.name, cmd) for cmd in matched.commands],
        }
    matched, cmd = _resolve(group, command)
    return _command_schema(matched.name, cmd)


def _request_token() -> str | None:
    """The OAuth bearer verified for the current HTTP request, or None over stdio (no request)."""
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token
    except ImportError:
        return None
    access_token = get_access_token()
    return access_token.token if access_token is not None else None


def _client_for_tool(timeout: float) -> Client:
    """Build the Client a tool call should use.

    In the hosted HTTP server every request carries its own OAuth bearer (one user per request),
    so the token comes from the verified request context. Over stdio there is no request context,
    so fall back to the locally configured token (``sellerclaw auth login`` / ``SELLERCLAW_TOKEN``).

    ``timeout`` is the command's own budget, so a call gets the same wait over MCP as it would from
    the CLI — a publish that legitimately takes minutes must not be cut short by the door it came in.
    """
    token = _request_token()
    if token is not None:
        from sellerclaw_cli import _config

        return Client(base_url=_config.load().api_url, token=token, timeout=timeout)
    return Client.from_env(timeout=timeout)


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

    with _client_for_tool(cmd.effective_timeout) as client:
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


def _import_fastmcp() -> Any:
    """Import FastMCP lazily so the core CLI never depends on the optional ``mcp`` SDK."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise UserInputError(
            "the MCP server needs the optional 'mcp' dependency. "
            "Install it with: pip install 'sellerclaw-cli[mcp]'."
        ) from exc
    return FastMCP


def _server_branding() -> dict[str, Any]:
    """The website and logo a client can show for this server, as FastMCP keyword arguments.

    The icon travels as a data URI rather than a link: a permission dialog that renders it should
    not depend on our web host being reachable, and 11 KB rides along once per session. Read here
    rather than at import time so the core CLI never touches it.
    """
    import base64
    from importlib.resources import files

    from mcp.types import Icon

    try:
        # Addressed through the package, not as ``sellerclaw_cli.assets``: the folder holds data,
        # not code, and has no ``__init__.py`` to be imported as a package of its own.
        png = (files("sellerclaw_cli") / "assets" / "icon.png").read_bytes()
    except OSError:
        # A build that shipped without the asset loses a logo, nothing more. Refusing to start the
        # hosted server over a decoration would turn a cosmetic regression into an outage.
        return {"website_url": SERVER_WEBSITE_URL}
    data_uri = f"data:{_ICON_MIME_TYPE};base64,{base64.b64encode(png).decode('ascii')}"
    return {
        "website_url": SERVER_WEBSITE_URL,
        "icons": [Icon(src=data_uri, mimeType=_ICON_MIME_TYPE, sizes=_ICON_SIZES)],
    }


def _apply_server_version(server: Any) -> None:
    """Report SellerClaw's version in the handshake instead of the SDK's.

    FastMCP takes no version argument and lets the low-level server default to the ``mcp`` package
    version, so a client that shows "SellerClaw 1.29.0" would be quoting the SDK back at us — and
    at anyone asking a user which version they are on.

    Reached through a private attribute for want of a public one, so it gives way rather than
    crashes if a future SDK moves it: the hosted image installs the SDK unpinned within 1.x (see the
    ``mcp`` extra), and the worst honest outcome of a rename is the old, wrong version number.
    """
    from sellerclaw_cli import __version__

    low_level = getattr(server, "_mcp_server", None)
    if low_level is not None:
        low_level.version = __version__


def _register_tools(server: Any) -> None:
    """Register the four discovery/proxy tools on a FastMCP server.

    Each carries a title as well as a name: the name is what a caller types, the title is what a
    person reads in a permission dialog, where "Sellerclaw run" says a good deal less than "Run a
    SellerClaw command".

    Each also carries annotations, because a client told nothing has to assume the worst: ChatGPT
    labels every unannotated tool "destructive" and "public write", so reading a guide came out
    looking exactly as dangerous as withdrawing a listing — and a warning that fires on everything
    stops being read. Three of the four only read this process's own command registry and the
    bundled guides; ``sellerclaw_run`` is the one that reaches the account and can change or
    remove things in it.
    """
    from mcp.types import ToolAnnotations

    def _reads_only(title: str) -> ToolAnnotations:
        return ToolAnnotations(
            title=title,
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )

    server.add_tool(
        show_guide,
        name="sellerclaw_guide",
        title="Read a SellerClaw guide",
        description=_GUIDE_TOOL_DESC,
        annotations=_reads_only("Read a SellerClaw guide"),
    )
    server.add_tool(
        list_groups,
        name="sellerclaw_groups",
        title="List SellerClaw commands",
        description=_GROUPS_TOOL_DESC,
        annotations=_reads_only("List SellerClaw commands"),
    )
    server.add_tool(
        describe_command,
        name="sellerclaw_describe",
        title="Describe a SellerClaw command",
        description=_DESCRIBE_TOOL_DESC,
        annotations=_reads_only("Describe a SellerClaw command"),
    )
    server.add_tool(
        run_command,
        name="sellerclaw_run",
        title="Run a SellerClaw command",
        description=_RUN_TOOL_DESC,
        # The honest reading of the one tool that fronts every command: it writes, it can destroy
        # (withdraw a listing, cancel an order), running it twice is not the same as running it
        # once, and it reaches the outside world.
        annotations=ToolAnnotations(
            title="Run a SellerClaw command",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )


def build_server() -> Any:
    """Construct the stdio FastMCP server with the three discovery/proxy tools.

    The optional ``mcp`` SDK is imported here (not at module load) so importing this module — and
    the core CLI — never requires it. Importing the CLI package populates the command ``REGISTRY``.
    """
    fast_mcp = _import_fastmcp()
    import sellerclaw_cli.cli  # noqa: F401 — importing registers every group into REGISTRY

    server = fast_mcp(SERVER_NAME, instructions=SERVER_INSTRUCTIONS, **_server_branding())
    _apply_server_version(server)
    _register_tools(server)
    return server


class SellerclawTokenVerifier:
    """Resource-server token verifier for the hosted HTTP MCP server.

    We don't decode the ``sca_`` access token ourselves — a token is valid iff the SellerClaw
    Agent API accepts it (``GET /agent/me`` returns 200). Anything else is rejected, which makes
    FastMCP answer the MCP request with ``401`` + ``WWW-Authenticate`` and the client starts OAuth.
    """

    def __init__(self, *, api_url: str) -> None:
        self._api_url = api_url

    async def verify_token(self, token: str) -> Any:
        """Return an ``AccessToken`` if the Agent API accepts the bearer, else ``None``."""
        import httpx
        from mcp.server.auth.provider import AccessToken

        try:
            async with httpx.AsyncClient(base_url=self._api_url, timeout=10.0) as client:
                response = await client.get(
                    "/agent/me", headers={"Authorization": f"Bearer {token}"}
                )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        subject: str | None = None
        try:
            body = response.json()
            subject = str(body.get("id") or body.get("user_id") or "") or None
        except (ValueError, AttributeError):
            subject = None
        return AccessToken(
            token=token, client_id="sellerclaw-mcp", scopes=[], expires_at=None, subject=subject
        )


def build_http_server(
    *,
    issuer_url: str,
    resource_url: str | None,
    api_url: str,
    host: str = "0.0.0.0",  # noqa: S104 — containerized service must bind all interfaces
    port: int = 8080,
) -> Any:
    """Build a stateless streamable-HTTP FastMCP server that authenticates each request via OAuth.

    ``issuer_url`` is the authorization server (the SellerClaw backend); ``resource_url`` is this
    MCP server's own public URL. FastMCP serves the protected-resource metadata and answers
    unauthenticated MCP requests with ``401`` + ``WWW-Authenticate`` — the trigger for OAuth.
    """
    fast_mcp = _import_fastmcp()
    from mcp.server.auth.settings import AuthSettings

    import sellerclaw_cli.cli  # noqa: F401 — importing registers every group into REGISTRY

    auth = AuthSettings(
        issuer_url=issuer_url,  # type: ignore[arg-type]
        resource_server_url=resource_url,  # type: ignore[arg-type]
        required_scopes=[],
    )
    server = fast_mcp(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        token_verifier=SellerclawTokenVerifier(api_url=api_url),
        auth=auth,
        stateless_http=True,
        host=host,
        port=port,
        **_server_branding(),
    )
    _apply_server_version(server)
    _register_tools(server)
    return server


def _http_server_from_env() -> Any:
    """Build the hosted HTTP server from environment configuration."""
    import os

    from sellerclaw_cli import _config

    issuer_url = os.environ.get("SELLERCLAW_MCP_ISSUER_URL", "").strip()
    if not issuer_url:
        raise UserInputError("SELLERCLAW_MCP_ISSUER_URL is required to run the HTTP MCP server.")
    resource_url = os.environ.get("SELLERCLAW_MCP_RESOURCE_URL", "").strip() or None
    host = os.environ.get("HOST", "0.0.0.0")  # noqa: S104 — containerized service binds all
    port = int(os.environ.get("PORT", "8080"))
    return build_http_server(
        issuer_url=issuer_url,
        resource_url=resource_url,
        api_url=_config.load().api_url,
        host=host,
        port=port,
    )


def create_http_app() -> Any:
    """ASGI app factory for the hosted MCP server (e.g. ``uvicorn ... --factory``)."""
    return _http_server_from_env().streamable_http_app()


def serve_http() -> None:
    """Run the hosted streamable-HTTP MCP server (blocks until shutdown)."""
    _http_server_from_env().run(transport="streamable-http")


def main_http() -> None:
    """Console entry point for the hosted HTTP MCP server (``sellerclaw-mcp-http``)."""
    import sys

    try:
        serve_http()
    except UserInputError as err:
        sys.stderr.write(err.message + "\n")
        raise SystemExit(1) from None


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
