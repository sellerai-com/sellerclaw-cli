"""What one ChatGPT tool is, and how it becomes a tool on the server.

An :class:`Action` is one thing the owner can have done — publish these listings, ship this order —
with a plain name, a description for the model, a flat set of parameters and its own annotations.
Most actions run exactly one command of the CLI registry; the rest pick the command from the store's
platform or read a few things at once. Either way the call goes through
:func:`sellerclaw_cli.mcp_server.run_command`, so paths, timeouts, background jobs and approvals behave
exactly as they do behind the read/write runners.

The input schema is written here rather than derived by the SDK from a Python signature: the SDK's
version spells every optional field as ``anyOf [type, null]`` with a title and a default, which
triples its size, and ChatGPT reads every tool's schema on every turn. The signature still exists —
the SDK validates arguments against it — and :func:`register` keeps the two in step.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from sellerclaw_cli._errors import UserInputError

if TYPE_CHECKING:
    from sellerclaw_cli._command_group import Cmd

#: Where a parameter's value goes in the command it runs.
Target = Literal["path", "flag", "body"]

_JSON_TYPES: Mapping[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
}


@dataclass(frozen=True)
class Param:
    """One input of an action: its JSON type, what it means, and where it goes."""

    name: str
    type: str
    description: str
    required: bool = False
    #: For an array: the type of its items.
    items: str | None = None
    choices: tuple[str, ...] = ()
    #: ``null`` is a value the caller may send (it means "remove"), not only an absence.
    nullable: bool = False
    to: Target = "body"
    #: The command's own name for it, when it differs from :attr:`name`.
    key: str | None = None

    @property
    def command_key(self) -> str:
        return self.key or self.name

    def json_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {"type": [self.type, "null"] if self.nullable else self.type}
        if self.type == "array":
            item: dict[str, Any] = {"type": self.items or "string"}
            if self.choices:
                item["enum"] = list(self.choices)
            schema["items"] = item
        elif self.choices:
            schema["enum"] = list(self.choices)
        schema["description"] = self.description
        return schema

    def annotation(self) -> Any:
        """The Python type the SDK validates this parameter against."""
        if self.type == "array":
            item = Literal[self.choices] if self.choices else _JSON_TYPES.get(
                self.items or "string",
                Any,
            )  # type: ignore[valid-type]
            base: Any = list[item]  # type: ignore[valid-type]
        elif self.choices:
            base = Literal[self.choices]  # type: ignore[valid-type]
        else:
            base = _JSON_TYPES[self.type]
            if base is dict:
                base = dict[str, Any]
        return base | None if (self.nullable or not self.required) else base


@dataclass(frozen=True)
class Action:
    """One tool of the ChatGPT surface."""

    name: str
    title: str
    description: str
    params: tuple[Param, ...]
    run: Callable[[dict[str, Any]], Any]
    read_only: bool
    destructive: bool
    open_world: bool
    #: The single registry command this action runs, when it runs exactly one — so a test can hold
    #: its parameters to that command's own path, flags and body.
    target: tuple[str, str] | None = None

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {p.name: p.json_schema() for p in self.params},
            "required": [p.name for p in self.params if p.required],
            "additionalProperties": False,
        }


# ---------------------------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------------------------

#: Registry job readers -> the tool that reads them here, with the job reader's path arguments.
_JOB_READERS: Mapping[tuple[str, str], str] = {("listings", "bulk-job"): "get_listing_job"}


def _poll_call(group: str, reader: Cmd, args: dict[str, str]) -> str | None:
    tool = _JOB_READERS.get((group, reader.name))
    if tool is None:
        # The write behind it has already gone through: answer with the job as it is rather than
        # fail a call that worked, which would invite sending it again.
        return None
    rendered = ", ".join(f'{name}="{value}"' for name, value in args.items())
    return f"{tool}({rendered})"


def _approval_note(request: str) -> str:
    return (
        "Waiting on the owner. Show them the request as a card — "
        f'sellerclaw_approval(request="{request}") — and let them answer on it. Only if they reply '
        f'to you in words instead, close it with answer_action_request(request_id="{request}", '
        'quote="<their words, verbatim>").'
    )


def _notes() -> Any:
    from sellerclaw_cli.mcp_server import Notes

    return Notes(poll_call=_poll_call, approval=_approval_note)


def execute(
    group: str,
    command: str,
    positionals: Mapping[str, Any] | None = None,
    flags: Mapping[str, Any] | None = None,
    body: Mapping[str, Any] | None = None,
) -> Any:
    """Run one registry command for an action, and name it for the call's usage report."""
    from sellerclaw_cli import mcp_server, mcp_usage

    changes = not mcp_server._reads(_registry_command(group, command))
    mcp_usage.note_command(f"{group} {command}", changes=changes)
    return mcp_server.run_command(
        group,
        command,
        dict(positionals) if positionals else None,
        dict(flags) if flags else None,
        dict(body) if body is not None else None,
        notes=_notes(),
    )


def split(values: Mapping[str, Any], params: Sequence[Param]) -> tuple[dict, dict, dict]:
    """Sort an action's arguments into the command's path arguments, query flags and body."""
    parts: dict[str, dict[str, Any]] = {"path": {}, "flag": {}, "body": {}}
    by_name = {p.name: p for p in params}
    for name, value in values.items():
        param = by_name.get(name)
        if param is not None:
            parts[param.to][param.command_key] = value
    return parts["path"], parts["flag"], parts["body"]


def runs(group: str, command: str, *, body: Mapping[str, Any] | None = None) -> Callable[..., Any]:
    """The run function of an action that is one registry command, its parameters laid out as declared.

    ``body`` is merged into what the caller sent: the constant that picks one shape of a general
    endpoint (publish vs withdraw on the same bulk job), never something the caller decides.
    """

    def run(values: dict[str, Any], params: Sequence[Param]) -> Any:
        positionals, flags, sent = split(values, params)
        merged = {**sent, **(body or {})}
        return execute(group, command, positionals, flags, merged or None)

    run.target = (group, command)  # type: ignore[attr-defined]
    return run


#: The registry group prefix of each platform, as the Agent API spells the platform.
_GROUP_PREFIX: Mapping[str, str] = {"tiktok_shop": "tiktok-shop"}

#: How the platforms are named to the owner and the model.
PLATFORM_NAMES: Mapping[str, str] = {
    "shopify": "Shopify",
    "ebay": "eBay",
    "amazon": "Amazon",
    "walmart": "Walmart",
    "woocommerce": "WooCommerce",
    "wix": "Wix",
    "bigcommerce": "BigCommerce",
    "sellercart": "SellerCart",
    "etsy": "Etsy",
    "tiktok_shop": "TikTok Shop",
}


def platform_of(store_id: str) -> str:
    """The platform of one of the owner's stores, as the Agent API names it (``shopify``, ``ebay``…)."""
    from sellerclaw_cli import mcp_server

    with mcp_server._client_for_tool(mcp_server.DEFAULT_TIMEOUT_SECONDS) as client:
        store = client.request("GET", f"/agent/sales-channels/{store_id}", read_only=True)
    platform = store.get("platform") if isinstance(store, Mapping) else None
    if not isinstance(platform, str) or not platform:
        raise UserInputError(f"store {store_id} was not found; take the store id from list_connections.")
    return platform


def group_for(platform: str, kind: str) -> str:
    """The registry group for one platform and kind: ``("tiktok_shop", "orders")`` -> ``tiktok-shop-orders``."""
    return f"{_GROUP_PREFIX.get(platform, platform)}-{kind}"


#: Platforms SellerClaw lets an owner connect today. Etsy and TikTok Shop have commands, and a store
#: connected earlier still works through them, but a refusal never offers them as the way out.
ADVERTISED_PLATFORMS: frozenset[str] = frozenset(
    {"shopify", "ebay", "amazon", "walmart", "woocommerce", "wix", "bigcommerce", "sellercart"}
)


def unsupported(what: str, platform: str, supported: Sequence[str]) -> UserInputError:
    """A refusal for a store whose platform has no such action — said before anything is sent."""
    names = ", ".join(PLATFORM_NAMES.get(p, p) for p in supported if p in ADVERTISED_PLATFORMS)
    return UserInputError(
        f"{what} is not available for {PLATFORM_NAMES.get(platform, platform)} stores here; it works "
        f"for {names}."
    )


def _registry_command(group: str, command: str) -> Cmd:
    from sellerclaw_cli import mcp_server

    return mcp_server._resolve(group, command)[1]


def fit(
    group: str, command: str, flags: Mapping[str, Any], body: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Keep only the flags and body fields this platform's command takes.

    One action stands for the same operation on every platform, and its parameters are the union
    of theirs — a period only eBay reports by, a product only BigCommerce needs. Sending one to a
    command that has no such field would refuse the whole call over something that does not apply.
    """
    cmd = _registry_command(group, command)
    flag_names = {f.name for f in cmd.flags}
    kept_flags = {k: v for k, v in flags.items() if k in flag_names}
    if not cmd.takes_body:
        return kept_flags, None
    if cmd.body and cmd.body_strict:
        body_names = {b.name for b in cmd.body}
        body = {k: v for k, v in body.items() if k in body_names}
    return kept_flags, dict(body) or None


def by_platform(
    values: Mapping[str, Any],
    params: Sequence[Param],
    *,
    what: str,
    commands: Mapping[str, tuple[str, str]],
) -> Any:
    """Run the command this store's platform has for the action, or refuse naming the ones that do."""
    platform = platform_of(str(values["store_id"]))
    target = commands.get(platform)
    if target is None:
        raise unsupported(what, platform, list(commands))
    group, command = target
    positionals, flags, body = split(values, params)
    kept_flags, kept_body = fit(group, command, flags, body)
    return execute(group, command, positionals, kept_flags, kept_body)


def store_param(*, to: Target = "path", key: str | None = None, required: bool = True) -> Param:
    """The ``store_id`` every store-scoped action takes."""
    return Param(
        "store_id", "string", "The store's id, from list_connections.", required=required, to=to, key=key
    )


def per_platform(kind: str, command: str, platforms: Sequence[str]) -> dict[str, tuple[str, str]]:
    """``{platform: (<platform>-<kind>, command)}`` for platforms whose group has that command."""
    return {p: (group_for(p, kind), command) for p in platforms}


# ---------------------------------------------------------------------------------------------
# Registering
# ---------------------------------------------------------------------------------------------


def _tool_function(action: Action) -> Callable[..., Any]:
    """A function the SDK can call and validate: keyword parameters exactly as the schema has them."""
    required = {p.name for p in action.params if p.required}

    def call(**kwargs: Any) -> Any:
        values = {k: v for k, v in kwargs.items() if v is not None or k in required}
        return action.run(values)

    parameters = [
        inspect.Parameter(
            p.name,
            inspect.Parameter.KEYWORD_ONLY,
            annotation=p.annotation(),
            **({} if p.required else {"default": None}),
        )
        for p in action.params
    ]
    call.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    call.__name__ = action.name
    return call


def register(server: Any, actions: Sequence[Action], *, wrap: Callable[[Callable[..., Any]], Any]) -> None:
    """Register every action on an ``MCPServer``, each with its own schema and annotations.

    ``wrap`` turns a refusal into the error JSON the model reads (the server's own wrapper).
    """
    from mcp.types import ToolAnnotations

    for action in actions:
        server.add_tool(
            wrap(_tool_function(action)),
            name=action.name,
            title=action.title,
            description=action.description,
            annotations=ToolAnnotations(
                title=action.title,
                read_only_hint=action.read_only,
                destructive_hint=action.destructive,
                idempotent_hint=action.read_only,
                open_world_hint=action.open_world,
            ),
        )
        # The SDK derived a schema from the signature; publish the compact one it was built from.
        server._tool_manager.get_tool(action.name).parameters = action.input_schema()


def action(
    name: str,
    title: str,
    description: str,
    params: Sequence[Param],
    run: Callable[..., Any],
    *,
    read_only: bool,
    destructive: bool = False,
    open_world: bool = False,
) -> Action:
    """Declare an action. ``run`` takes the arguments, or the arguments and the parameters."""
    takes_params = len(inspect.signature(run).parameters) == 2
    bound = functools.partial(run, params=tuple(params)) if takes_params else run
    return Action(
        name=name,
        title=title,
        description=description,
        params=tuple(params),
        run=bound,
        read_only=read_only,
        destructive=destructive and not read_only,
        open_world=open_world,
        target=getattr(run, "target", None),
    )
