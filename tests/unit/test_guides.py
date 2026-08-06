"""Task guides: the package data, the `sellerclaw_guide` tool, and the skills compiled from them.

The guides are the only workflow knowledge an MCP client ever gets — Claude Desktop's extension and
the hosted connector have no skills — so the things worth guarding are that every declared topic
actually resolves to text, that a wrong topic answers with the list instead of nothing, and that the
plugin's skills keep being generated from these same files rather than a second copy of them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import sellerclaw_cli.cli  # noqa: F401 — importing registers every command group into the REGISTRY
from scripts.build_plugin import TARGETS, assemble, default_guides_src
from sellerclaw_cli import guides
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.mcp_server import _resolve, show_guide

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = REPO_ROOT / "plugin"

RECIPE_TOPICS = ("listings", "orders", "catalog", "suppliers", "email", "ads", "research", "analytics")


def test_every_declared_topic_resolves_to_a_readable_guide() -> None:
    topics = guides.topics()

    assert guides.topic_names() == ("start", *RECIPE_TOPICS)
    for guide in topics:
        body = guides.read(guide.topic)
        assert body.startswith("# SellerClaw"), guide.topic
        assert len(body) > 500, f"{guide.topic}: too thin to be a useful guide"
        assert guide.description.strip()


@pytest.mark.parametrize("topic", RECIPE_TOPICS)
def test_task_guides_carry_runnable_examples(topic: str) -> None:
    # A guide's whole point is that the agent can copy a call instead of deriving it from schemas.
    body = guides.read(topic)

    assert 'sellerclaw_run(group="' in body


@pytest.mark.parametrize("topic", guides.topic_names())
def test_every_example_call_names_a_command_that_exists(topic: str) -> None:
    # A guide is only worth more than the schemas if its examples run. Renaming or dropping a command
    # without touching the guides fails here instead of failing in front of a user.
    examples = re.findall(r'group="([^"]+)",\s*command="([^"]+)"', guides.read(topic))
    assert examples or topic == "start", f"{topic}: no runnable example at all"
    for group, command in examples:
        _resolve(group, command)  # raises UserInputError if the pair is unknown or not MCP-visible


def test_start_guide_covers_the_rules_a_bare_mcp_client_has_nowhere_else_to_learn() -> None:
    body = guides.read("start")

    for expected in ("positionals", "channels", "approval", "sellerclaw_describe"):
        assert expected in body, expected


def test_unknown_topic_names_the_ones_that_exist() -> None:
    with pytest.raises(UserInputError, match="unknown guide topic 'pricing'"):
        guides.read("pricing")

    with pytest.raises(UserInputError, match="listings"):
        guides.find("pricing")


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        pytest.param("orders", "orders", id="exact"),
        pytest.param("  Orders  ", "orders", id="padded-and-capitalised"),
    ],
)
def test_guide_tool_returns_the_markdown_for_a_topic(topic: str, expected: str) -> None:
    # Markdown as-is, not wrapped in an object: a JSON envelope would escape every newline of a
    # document whose only job is to be read.
    result = show_guide(topic)

    assert result == guides.read(expected)


@pytest.mark.parametrize("topic", [None, "", "   "], ids=["omitted", "empty", "blank"])
def test_guide_tool_without_a_topic_lists_them(topic: str | None) -> None:
    result = show_guide(topic)

    for guide in guides.topics():
        assert f"`{guide.topic}`" in result
        assert guide.description in result
    assert "sellerclaw_guide" in result


def test_guide_tool_rejects_an_unknown_topic() -> None:
    with pytest.raises(UserInputError, match="Available: start, listings"):
        show_guide("everything")


def test_plugin_skills_are_compiled_from_the_guides(tmp_path: Path) -> None:
    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0")

    for topic in RECIPE_TOPICS:
        guide = guides.find(topic)
        assert guide.skill is not None
        skill = (out / "skills" / guide.skill / "SKILL.md").read_text()
        assert skill == f'---\nname: {guide.skill}\ndescription: "{guide.description}"\n---\n\n{guides.read(topic)}'


def test_editing_a_guide_changes_the_skill_that_ships(tmp_path: Path) -> None:
    # The point of compiling skills from the package: one edit, both audiences. Guarding it here
    # means a future refactor that goes back to two hand-maintained copies fails loudly.
    guides_src = tmp_path / "guides"
    guides_src.mkdir()
    (guides_src / "topics.json").write_text(
        json.dumps(
            [{"topic": "orders", "skill": "sellerclaw-orders", "description": "Edited.", "file": "orders.md"}]
        )
    )
    (guides_src / "orders.md").write_text("# SellerClaw — orders\n\nEdited body.\n")

    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0", guides_src=guides_src)

    skill = (out / "skills" / "sellerclaw-orders" / "SKILL.md").read_text()
    assert 'description: "Edited."' in skill
    assert "Edited body." in skill
    # Topics without a skill (the MCP-only `start` guide) must not leak in as one.
    assert not (out / "skills" / "sellerclaw-start").exists()


def test_desktop_bundle_carries_no_skills_but_the_package_ships_the_guides(tmp_path: Path) -> None:
    # The .mcpb has no skills concept — its client reaches the same text through sellerclaw_guide,
    # which is served by the package data, so that data must travel with the wheel.
    out = assemble(
        "claude-desktop", PLUGIN_SRC, tmp_path / "out", version="0.0.0", layers=TARGETS["claude-desktop"].layers
    )

    assert not (out / "skills").exists()
    packaged = default_guides_src(PLUGIN_SRC)
    assert (packaged / "topics.json").is_file()
    for guide in guides.topics():
        assert (packaged / guide.file).is_file(), guide.topic
