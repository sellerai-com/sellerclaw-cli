"""Shortcuts — the ready-made commands an owner starts from a menu instead of phrasing a request.

``/sellerclaw:orders #1001`` in Claude Code, "Orders" under SellerClaw in claude.ai's "+" menu: each
shortcut is a short instruction to Claude — open this card, or run this job from its guide — with
the owner's own words carried in. Two audiences read the same files, as with the guides:

* **Any MCP client** gets them as MCP prompts (``mcp_server._register_prompts``). That is the only
  way claude.ai, Claude Desktop, Cursor and the rest show a server's ready-made commands.
* **The Claude plugin** compiles each into a user-invoked skill (``scripts/build_plugin.py``), which
  is what Claude Code and Cowork list as ``/sellerclaw:<name>``.

A body that takes the owner's words ends with ``$ARGUMENTS``: Claude Code substitutes what was typed
after the command, and :func:`render` does the same for an MCP client, so both read one text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

from sellerclaw_cli._errors import UserInputError

SHORTCUTS_FILE = "shortcuts.json"

#: Where the owner's words go in a body — Claude Code's own placeholder for them.
WORDS_PLACEHOLDER = "$ARGUMENTS"


@dataclass(frozen=True)
class Words:
    """What the owner may type after the command, and how each client offers it."""

    name: str
    hint: str
    description: str


@dataclass(frozen=True)
class Shortcut:
    name: str
    title: str
    description: str
    file: str
    words: Words | None = None


@lru_cache(maxsize=1)
def shortcuts() -> tuple[Shortcut, ...]:
    """Every shortcut in menu order — the cards first, then the jobs."""
    raw = json.loads((files(__name__) / SHORTCUTS_FILE).read_text(encoding="utf-8"))
    return tuple(
        Shortcut(
            name=item["name"],
            title=item["title"],
            description=item["description"],
            file=item["file"],
            words=Words(**item["words"]) if item.get("words") else None,
        )
        for item in raw
    )


def names() -> tuple[str, ...]:
    return tuple(shortcut.name for shortcut in shortcuts())


def find(name: str) -> Shortcut:
    """Look a shortcut up by name, or raise with the names that do exist."""
    wanted = name.strip().lower()
    match = next((shortcut for shortcut in shortcuts() if shortcut.name == wanted), None)
    if match is None:
        raise UserInputError(f"unknown shortcut {name!r}. Available: {', '.join(names())}.")
    return match


def read(name: str) -> str:
    """The shortcut's body as written, placeholder included."""
    return (files(__name__) / find(name).file).read_text(encoding="utf-8")


def render(name: str, words: str | None = None) -> str:
    """The body with the owner's words in place — nothing there when they typed none."""
    return read(name).replace(WORDS_PLACEHOLDER, (words or "").strip())
