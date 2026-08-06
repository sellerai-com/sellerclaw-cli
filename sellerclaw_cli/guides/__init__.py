"""Task guides — the operating knowledge an agent needs before a multi-step SellerClaw job.

Two audiences read the same files, which is why they live in the package rather than next to the
plugin:

* **Any MCP client** (Claude Desktop's extension, Cursor, the hosted connector) reaches them through
  the ``sellerclaw_guide`` tool. Those clients have no notion of skills — without this they would
  only ever see three tool descriptions and would have to re-derive every workflow by hand.
* **The Claude plugin** compiles each guide into a skill (``scripts/build_plugin.py`` adds the
  frontmatter from ``topics.json``), so Claude Code and claude.ai load the same text automatically.

One source, so a recipe fixed for one audience is fixed for both — the plugin drift check
(``make plugin-check``) fails if the committed skills stop matching these files.

The ``start`` guide has no skill counterpart: the plugin's hand-written core skill already covers
that ground with links a skill can follow, which a bare MCP client cannot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

from sellerclaw_cli._errors import UserInputError

TOPICS_FILE = "topics.json"


@dataclass(frozen=True)
class Guide:
    """One guide: the topic an agent asks for, and the skill it becomes in the Claude plugin."""

    topic: str
    description: str
    file: str
    skill: str | None = None


@lru_cache(maxsize=1)
def topics() -> tuple[Guide, ...]:
    """Every guide in reading order — ``start`` first, then the task recipes."""
    raw = json.loads((files(__name__) / TOPICS_FILE).read_text(encoding="utf-8"))
    return tuple(
        Guide(topic=item["topic"], description=item["description"], file=item["file"], skill=item.get("skill"))
        for item in raw
    )


def topic_names() -> tuple[str, ...]:
    return tuple(guide.topic for guide in topics())


def find(topic: str) -> Guide:
    """Look a guide up by topic, or raise with the list of topics that do exist."""
    wanted = topic.strip().lower()
    match = next((guide for guide in topics() if guide.topic == wanted), None)
    if match is None:
        raise UserInputError(f"unknown guide topic {topic!r}. Available: {', '.join(topic_names())}.")
    return match


def read(topic: str) -> str:
    """The guide's markdown body."""
    return (files(__name__) / find(topic).file).read_text(encoding="utf-8")
