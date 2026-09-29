"""Shortcuts: the package data, the MCP prompts served from it, and the plugin skills compiled from it.

A shortcut is only worth its menu line if what it tells Claude to do exists: the card it opens, the
command it runs, the guide it points to. A rename anywhere in the surface must fail here rather than
in front of an owner who picked "Orders" and got an apology.
"""

from __future__ import annotations

import asyncio
import functools
import json
import re
from pathlib import Path

import pytest
from mcp.types import TextContent

import sellerclaw_cli.cli  # noqa: F401 — importing registers every command group into the REGISTRY
from scripts.build_plugin import TARGETS, assemble, default_shortcuts_src
from sellerclaw_cli import guides, mcp_apps, shortcuts
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.mcp_server import _resolve, build_server

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = REPO_ROOT / "plugin"

CARD_SHORTCUTS = (
    "today",
    "summary",
    "orders",
    "listings",
    "product",
    "ads",
    "connections",
    "billing",
    "media",
    "studio",
    "approvals",
)
JOB_SHORTCUTS = ("ship", "publish", "fix-listings", "report", "restock", "research", "inbox", "generate")

_KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_CARD_CALL = re.compile(r"`(sellerclaw_[a-z_]+)[(`]")
_RUN_CALL = re.compile(r'group="([^"]+)",\s*command="([^"]+)"')
_GUIDE_CALL = re.compile(r'topic="([^"]+)"')


@functools.cache
def _model_visible_cards() -> frozenset[str]:
    tools = asyncio.run(build_server().list_tools())
    return frozenset({tool.name for tool in tools if tool.name in mcp_apps.tool_names()}) - {
        # Only the card itself may call these; a shortcut naming one would send Claude to a tool it
        # does not have.
        "sellerclaw_approval_decide",
        "sellerclaw_media_set_default",
        "sellerclaw_media_upload_image",
        "sellerclaw_media_generate",
    }


def test_the_menu_is_the_cards_then_the_jobs() -> None:
    assert shortcuts.names() == (*CARD_SHORTCUTS, *JOB_SHORTCUTS)


@pytest.mark.parametrize("name", shortcuts.names())
def test_every_shortcut_is_a_short_readable_instruction(name: str) -> None:
    shortcut = shortcuts.find(name)
    body = shortcuts.read(name)

    assert _KEBAB.match(name), name
    assert shortcut.title.strip()
    assert shortcut.description.strip()
    # The plugin writes description and hint into YAML double quotes.
    assert '"' not in shortcut.description
    assert shortcut.words is None or '"' not in shortcut.words.hint
    assert 40 < len(body) < 1200, f"{name}: a shortcut points to a card or a guide, it does not restate one"


@pytest.mark.parametrize("name", shortcuts.names())
def test_the_owners_words_have_a_place_exactly_when_the_shortcut_takes_them(name: str) -> None:
    shortcut = shortcuts.find(name)
    body = shortcuts.read(name)

    if shortcut.words is None:
        assert shortcuts.WORDS_PLACEHOLDER not in body
    else:
        assert body.count(shortcuts.WORDS_PLACEHOLDER) == 1
        assert shortcut.words.name.isidentifier(), "an MCP client sends it as an argument name"
        assert shortcut.words.hint.startswith("[")
        assert shortcut.words.description.strip()


@pytest.mark.parametrize("name", shortcuts.names())
def test_every_card_a_shortcut_opens_is_one_claude_can_call(name: str) -> None:
    cards = set(_CARD_CALL.findall(shortcuts.read(name))) - {"sellerclaw_run", "sellerclaw_guide"}

    assert cards <= _model_visible_cards(), name


@pytest.mark.parametrize("name", CARD_SHORTCUTS)
def test_every_card_shortcut_names_its_card(name: str) -> None:
    cards = set(_CARD_CALL.findall(shortcuts.read(name))) & _model_visible_cards()

    assert cards, f"{name}: a card shortcut must say which card to open"


@pytest.mark.parametrize("name", shortcuts.names())
def test_every_command_a_shortcut_runs_exists_and_is_visible(name: str) -> None:
    for group, command in _RUN_CALL.findall(shortcuts.read(name)):
        _resolve(group, command)  # raises UserInputError if the pair is unknown or not MCP-visible


@pytest.mark.parametrize("name", shortcuts.names())
def test_every_guide_a_shortcut_points_to_exists(name: str) -> None:
    for topic in _GUIDE_CALL.findall(shortcuts.read(name)):
        guides.find(topic)  # raises UserInputError for a topic that does not exist


@pytest.mark.parametrize("name", JOB_SHORTCUTS)
def test_every_job_shortcut_points_to_a_guide_a_card_or_a_command(name: str) -> None:
    body = shortcuts.read(name)

    assert _GUIDE_CALL.search(body) or _RUN_CALL.search(body) or _CARD_CALL.search(body), name


@pytest.mark.parametrize(
    ("words", "expected_tail"),
    [
        pytest.param("#1001", "Owner's words: #1001\n", id="words"),
        pytest.param("  Jane Doe  ", "Owner's words: Jane Doe\n", id="padded-words"),
        pytest.param(None, "Owner's words: \n", id="no-words"),
        pytest.param("", "Owner's words: \n", id="empty-words"),
    ],
)
def test_render_puts_the_owners_words_where_claude_code_would(words: str | None, expected_tail: str) -> None:
    rendered = shortcuts.render("orders", words)

    assert rendered == shortcuts.read("orders").replace("Owner's words: $ARGUMENTS\n", expected_tail)
    assert shortcuts.WORDS_PLACEHOLDER not in rendered


def test_render_of_a_shortcut_without_words_is_its_body() -> None:
    assert shortcuts.render("billing", "ignored") == shortcuts.read("billing")


@pytest.mark.parametrize("name", ["pricing", ""], ids=["unknown", "empty"])
def test_unknown_shortcut_names_the_ones_that_exist(name: str) -> None:
    with pytest.raises(UserInputError, match=r"unknown shortcut .*Available: today, summary, orders"):
        shortcuts.find(name)


# --------------------------------------------------------------------------- the MCP prompts


def test_the_server_lists_every_shortcut_as_a_prompt_with_optional_words() -> None:
    prompts = asyncio.run(build_server().list_prompts())

    assert [prompt.name for prompt in prompts] == list(shortcuts.names())
    for prompt in prompts:
        shortcut = shortcuts.find(prompt.name)
        assert prompt.title == shortcut.title
        assert prompt.description == shortcut.description
        if shortcut.words is None:
            assert prompt.arguments == []
        else:
            [argument] = prompt.arguments or []
            assert argument.name == shortcut.words.name
            assert argument.description == shortcut.words.description
            # Required would hide the command from a client that cannot ask for words, and refuse
            # the whole board to an owner who typed none.
            assert argument.required is False


@pytest.mark.parametrize(
    ("name", "arguments", "words"),
    [
        pytest.param("orders", {"order": "#1001"}, "#1001", id="with-words"),
        pytest.param("orders", None, None, id="without-words"),
        pytest.param("studio", {"idea": "a red sneaker on a beach"}, "a red sneaker on a beach", id="idea"),
        pytest.param("billing", None, None, id="no-words-shortcut"),
    ],
)
def test_a_prompt_renders_the_shortcut_with_the_owners_words(
    name: str, arguments: dict[str, str] | None, words: str | None
) -> None:
    result = asyncio.run(build_server().get_prompt(name, arguments))

    [message] = result.messages
    assert message.role == "user"
    assert isinstance(message.content, TextContent)
    assert message.content.text == shortcuts.render(name, words)


def test_an_unknown_prompt_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown prompt: pricing"):
        asyncio.run(build_server().get_prompt("pricing", None))


# --------------------------------------------------------------------------- the plugin skills


def test_plugin_ships_every_shortcut_as_a_command_only_the_owner_starts(tmp_path: Path) -> None:
    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0")

    for shortcut in shortcuts.shortcuts():
        skill = (out / "skills" / shortcut.name / "SKILL.md").read_text()
        hint = f'argument-hint: "{shortcut.words.hint}"\n' if shortcut.words else ""
        assert skill == (
            f'---\nname: {shortcut.name}\ndescription: "{shortcut.description}"\n{hint}'
            f"disable-model-invocation: true\n---\n\n{shortcuts.read(shortcut.name)}"
        )


def test_editing_a_shortcut_changes_the_command_that_ships(tmp_path: Path) -> None:
    shortcuts_src = tmp_path / "shortcuts"
    shortcuts_src.mkdir()
    (shortcuts_src / "shortcuts.json").write_text(
        json.dumps([{"name": "orders", "title": "Orders", "description": "Edited.", "file": "orders.md"}])
    )
    (shortcuts_src / "orders.md").write_text("Edited body.\n")

    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0", shortcuts_src=shortcuts_src)

    skill = (out / "skills" / "orders" / "SKILL.md").read_text()
    assert skill == '---\nname: orders\ndescription: "Edited."\ndisable-model-invocation: true\n---\n\nEdited body.\n'


@pytest.mark.parametrize(
    ("entry", "error"),
    [
        pytest.param(
            {"name": "sellerclaw-orders", "title": "Orders", "description": "Clash.", "file": "body.md"},
            "shortcut 'sellerclaw-orders': a skill of that name already ships in the plugin",
            id="name-of-a-guide-skill",
        ),
        pytest.param(
            {"name": "orders", "title": "Orders", "description": 'Say "hi".', "file": "body.md"},
            "shortcut 'orders': description must not contain a double quote",
            id="quote-in-description",
        ),
        pytest.param(
            {
                "name": "orders",
                "title": "Orders",
                "description": "Fine.",
                "file": "body.md",
                "words": {"name": "order", "hint": '["#1001"]', "description": "An order."},
            },
            "shortcut 'orders': argument-hint must not contain a double quote",
            id="quote-in-hint",
        ),
    ],
)
def test_a_shortcut_that_would_break_the_plugin_fails_the_build(
    tmp_path: Path, entry: dict[str, object], error: str
) -> None:
    shortcuts_src = tmp_path / "shortcuts"
    shortcuts_src.mkdir()
    (shortcuts_src / "shortcuts.json").write_text(json.dumps([entry]))
    (shortcuts_src / "body.md").write_text("Body.\n")

    with pytest.raises(ValueError, match=re.escape(error)):
        assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0", shortcuts_src=shortcuts_src)


def test_desktop_bundle_carries_no_skills_but_the_package_ships_the_shortcuts(tmp_path: Path) -> None:
    # The .mcpb reaches the shortcuts as prompts from the hosted server, so the data must travel
    # with the wheel rather than with the bundle.
    out = assemble(
        "claude-desktop", PLUGIN_SRC, tmp_path / "out", version="0.0.0", layers=TARGETS["claude-desktop"].layers
    )

    assert not (out / "skills").exists()
    packaged = default_shortcuts_src(PLUGIN_SRC)
    assert (packaged / "shortcuts.json").is_file()
    for shortcut in shortcuts.shortcuts():
        assert (packaged / shortcut.file).is_file(), shortcut.name
