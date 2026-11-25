"""Keep the cards' buttons out of the model's reach in a client that would hand them to it.

A tool that only a card's button calls is declared ``visibility: ["app"]``: the client lists it for
the card and never for the model. That declaration is all that keeps a model from pressing the owner's
buttons for them — approving a payment, a mailing or an ad launch the owner was meant to decide, or
spending their credits on a generation — and it is a promise the client keeps, not a boundary of ours.

Cursor — the editor and its terminal agent alike — announces MCP Apps support and then offers those
tools to the model anyway (checked 25.11.2026). Asked to put a photo from the computer into the
owner's files, its model reached for the studio's Upload button, wrote the photo out as base64 text,
and Cursor itself failed on the call. So for a client known to do that, ``tools/list`` leaves the
buttons out. Only the list: a call by name still goes through, so a card the client does draw keeps
its buttons working.

The hosted server answers every request on a fresh connection, so the name a client gave in its
handshake is gone by the time it asks for the list. Cursor signs every HTTP request with
``User-Agent: Cursor/<version>`` — its terminal agent with that alone, its editor with the platform
after it (``Cursor/2.1.50 (linux x64)``) — and that is what the hosted server goes by; over stdio
the handshake's name is still there.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Final

from sellerclaw_cli.mcp_usage import client_name_of

#: Clients that list a card's buttons to the model, by the name they give themselves, in lowercase.
CLIENTS_SHOWING_BUTTONS_TO_THE_MODEL: Final[frozenset[str]] = frozenset({"cursor"})


def shows_buttons_to_the_model(ctx: Any) -> bool:
    """Whether this request comes from a client known to offer a card's buttons to its model."""
    return not _client_names(ctx).isdisjoint(CLIENTS_SHOWING_BUTTONS_TO_THE_MODEL)


def _client_names(ctx: Any) -> set[str]:
    """Every name the request goes by: the one the client gave itself, and its User-Agent products."""
    names: set[str] = set()
    announced = client_name_of(ctx)
    if announced is not None:
        names.add(announced.strip().lower())
    headers = getattr(getattr(ctx, "request", None), "headers", None)
    agent = headers.get("user-agent") if headers is not None else None
    if isinstance(agent, str):
        # Every product token: "Cursor/1.0.0", "Cursor/2.1.50 (linux x64)", or one among several.
        names.update(token.split("/", 1)[0].lower() for token in agent.split() if "/" in token)
    return names


def is_button(tool: Any) -> bool:
    """Whether a listed tool is one only a card calls — declared for the app and not for the model."""
    meta = tool.get("_meta") if isinstance(tool, Mapping) else getattr(tool, "meta", None)
    ui = meta.get("ui") if isinstance(meta, Mapping) else None
    visibility = ui.get("visibility") if isinstance(ui, Mapping) else None
    return isinstance(visibility, list) and "model" not in visibility


def without_buttons(result: Any) -> Any:
    """A ``tools/list`` result with the cards' buttons taken out; anything else as it came."""
    if isinstance(result, Mapping):
        tools = result.get("tools")
        if not isinstance(tools, list):
            return result
        return {**result, "tools": [tool for tool in tools if not is_button(tool)]}
    tools = getattr(result, "tools", None)
    if not isinstance(tools, list) or not hasattr(result, "model_copy"):
        return result
    return result.model_copy(update={"tools": [tool for tool in tools if not is_button(tool)]})


class ButtonsOutOfTheModelsReach:
    """Server middleware: the tool list without the cards' buttons, for a client that shows them to the model."""

    async def __call__(self, ctx: Any, call_next: Callable[[Any], Awaitable[Any]]) -> Any:
        result = await call_next(ctx)
        if ctx.method != "tools/list" or not shows_buttons_to_the_model(ctx):
            return result
        return without_buttons(result)
