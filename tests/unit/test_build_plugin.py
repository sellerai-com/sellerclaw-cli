from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.build_plugin import (
    TARGETS,
    assemble,
    available_targets,
    build_target,
    check_target,
    committed_targets,
    default_guides_src,
    default_shortcuts_src,
    pack_zip,
    read_version,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = REPO_ROOT / "plugin"

CORE_SKILL = "sellerclaw"
CHATGPT_SKILLS = frozenset(
    {
        "sellerclaw",
        "sellerclaw-listings",
        "sellerclaw-orders",
        "sellerclaw-catalog",
        "sellerclaw-ads",
        "sellerclaw-research",
        "sellerclaw-media",
    }
)
TASK_RECIPES = (
    "sellerclaw-listings",
    "sellerclaw-orders",
    "sellerclaw-ads",
    "sellerclaw-research",
    "sellerclaw-analytics",
)


def test_assemble_claude_code_layout_and_version(tmp_path: Path) -> None:
    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="9.9.9")

    manifest = out / ".claude-plugin" / "plugin.json"
    assert manifest.is_file()
    assert (out / ".mcp.json").is_file()

    data = json.loads(manifest.read_text())
    # Version is stamped from the caller, overriding whatever placeholder the source template carried.
    assert data["version"] == "9.9.9"
    assert data["name"] == "sellerclaw"
    # The standard hooks/hooks.json is auto-loaded by Claude Code; the manifest must NOT also
    # declare it, or the plugin fails to load with "Duplicate hooks file detected".
    assert "hooks" not in data


def test_assemble_merges_core_and_all_task_recipes(tmp_path: Path) -> None:
    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0")

    assert (out / "skills" / CORE_SKILL / "SKILL.md").is_file()
    assert (out / "skills" / CORE_SKILL / "references" / "capabilities.md").is_file()
    for recipe in TASK_RECIPES:
        assert (out / "skills" / recipe / "SKILL.md").is_file(), recipe


def test_assemble_ships_runnable_hooks(tmp_path: Path) -> None:
    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0")

    hooks = json.loads((out / "hooks" / "hooks.json").read_text())
    # The hooks file must be wrapped under a top-level "hooks" key (Claude Code rejects the bare map).
    assert set(hooks) == {"hooks"}
    assert "SessionStart" in hooks["hooks"]

    script = out / "hooks" / "session_start.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK), "session_start.sh lost its executable bit"


def test_assemble_does_not_leak_overlay_docs(tmp_path: Path) -> None:
    # The claude/ overlay carries a README documenting the seam; it must never reach the plugin root.
    out = assemble("claude-code", PLUGIN_SRC, tmp_path / "out", version="0.0.0")
    assert not (out / "README.md").exists()


def test_assemble_is_idempotent(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"

    def tree() -> list[str]:
        root = assemble("claude-code", PLUGIN_SRC, out_dir, "1.0.0")
        return sorted(p.relative_to(out_dir).as_posix() for p in root.rglob("*"))

    assert tree() == tree()


def test_read_version_reads_plugin_version_file() -> None:
    # The plugin version is decoupled from the CLI/PyPI version: it comes from plugin/VERSION.
    version = read_version(REPO_ROOT)
    assert version == (REPO_ROOT / "plugin" / "VERSION").read_text().strip()
    assert version[0].isdigit()


@pytest.mark.parametrize("target", available_targets(REPO_ROOT))
def test_every_available_target_assembles(target: str, tmp_path: Path) -> None:
    spec = TARGETS[target]
    out = assemble(target, PLUGIN_SRC, tmp_path / target, version="0.0.0")
    # Every target carries at least one stampable manifest.
    manifests = (".claude-plugin/plugin.json", "manifest.json", "plugin.json")
    assert any((out / rel).is_file() for rel in manifests), target
    # Plugin targets ship a core skill — compiled, or (ChatGPT) its own; the Desktop .mcpb bundle has
    # no skills concept.
    if spec.skills or target == "chatgpt":
        assert (out / "skills" / CORE_SKILL / "SKILL.md").is_file(), target
    else:
        assert not (out / "skills").exists(), target


def test_pack_zip_wraps_output_in_a_single_folder(tmp_path: Path) -> None:
    # The web upload bundle must extract to one tidy folder so users can drop it straight into
    # claude.ai's Upload plugin dialog.
    out = assemble("claude-web", PLUGIN_SRC, tmp_path / "out", version="0.0.0")
    archive = pack_zip(out, tmp_path / "sellerclaw-claude-web.zip", TARGETS["claude-web"].zip_folder)

    assert archive.is_file()
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    # Everything lives under the single top-level folder, including the plugin manifest and core skill.
    assert all(n.startswith("sellerclaw/") for n in names), names
    assert "sellerclaw/.claude-plugin/plugin.json" in names
    assert "sellerclaw/.mcp.json" in names
    assert f"sellerclaw/skills/{CORE_SKILL}/SKILL.md" in names


def test_target_out_policy() -> None:
    # claude-code is committed into the repo so the marketplace can reference it by path; everything
    # else is a throwaway artifact under the git-ignored dist/.
    assert TARGETS["claude-code"].out == "plugins/claude-code"
    assert all(spec.out.startswith("dist/") for name, spec in TARGETS.items() if name != "claude-code")
    # The Desktop .mcpb bundle ships the MCP server only — no skills/hooks layers.
    assert TARGETS["claude-desktop"].layers == ()
    assert TARGETS["claude-desktop"].skills is False
    # Only the committed target is checkable for drift — dist/ is git-ignored and rebuilt every time.
    assert committed_targets(REPO_ROOT) == ["claude-code"]


COMMITTED_OUT = TARGETS["claude-code"].out


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway repo: the plugin/ source plus a freshly built, in-sync committed plugins/ tree.

    The task guides and the shortcuts come along because the recipe skills and the owner's commands
    are compiled from them — a repo without them is not a repo the plugin can be built from.
    """
    root = tmp_path / "repo"
    shutil.copytree(PLUGIN_SRC, root / "plugin")
    shutil.copytree(default_guides_src(PLUGIN_SRC), root / "sellerclaw_cli" / "guides")
    shutil.copytree(default_shortcuts_src(PLUGIN_SRC), root / "sellerclaw_cli" / "shortcuts")
    build_target("claude-code", root)
    return root


def test_check_target_is_clean_when_the_committed_tree_matches_the_source(repo: Path) -> None:
    assert check_target("claude-code", repo) == []


def test_check_target_passes_on_this_repo() -> None:
    # The marketplace serves plugins/claude-code straight from main, so the tree committed here must
    # always be exactly what plugin/ produces. This is the regression guard for that: edit plugin/,
    # forget `make plugin`, and this fails long before the stale skills reach anyone.
    drift = check_target("claude-code", REPO_ROOT)
    assert not drift, "the committed plugin is stale — run `make plugin` and commit:\n  " + "\n  ".join(drift)


def _edit_a_skill(repo: Path) -> None:
    skill = repo / COMMITTED_OUT / "skills" / CORE_SKILL / "SKILL.md"
    skill.write_text(skill.read_text() + "\nhand-edited, never regenerated\n")


def _bump_the_version_without_rebuilding(repo: Path) -> None:
    (repo / "plugin" / "VERSION").write_text("99.0.0\n")


def _drop_the_executable_bit(repo: Path) -> None:
    (repo / COMMITTED_OUT / "hooks" / "session_start.sh").chmod(0o644)


def _delete_a_generated_file(repo: Path) -> None:
    (repo / COMMITTED_OUT / "skills" / CORE_SKILL / "SKILL.md").unlink()


def _leave_a_stale_file_behind(repo: Path) -> None:
    (repo / COMMITTED_OUT / "skills" / "sellerclaw-retired" / "SKILL.md").parent.mkdir(parents=True)
    (repo / COMMITTED_OUT / "skills" / "sellerclaw-retired" / "SKILL.md").write_text("dropped from plugin/\n")


@pytest.mark.parametrize(
    ("desync", "expected"),
    [
        pytest.param(
            _edit_a_skill,
            [f"out of date: {COMMITTED_OUT}/skills/{CORE_SKILL}/SKILL.md"],
            id="skill edited in the committed tree instead of the source",
        ),
        pytest.param(
            _bump_the_version_without_rebuilding,
            [f"out of date: {COMMITTED_OUT}/.claude-plugin/plugin.json"],
            id="plugin/VERSION bumped but never rebuilt",
        ),
        pytest.param(
            _drop_the_executable_bit,
            [f"out of date: {COMMITTED_OUT}/hooks/session_start.sh"],
            id="hook lost its executable bit",
        ),
        pytest.param(
            _delete_a_generated_file,
            [f"never committed: {COMMITTED_OUT}/skills/{CORE_SKILL}/SKILL.md"],
            id="generated file missing from the commit",
        ),
        pytest.param(
            _leave_a_stale_file_behind,
            [f"stale leftover, plugin/ no longer produces it: {COMMITTED_OUT}/skills/sellerclaw-retired/SKILL.md"],
            id="skill removed from the source but left in the commit",
        ),
    ],
)
def test_check_target_reports_each_way_the_committed_tree_can_drift(
    repo: Path,
    desync: Callable[[Path], None],
    expected: list[str],
) -> None:
    desync(repo)
    assert check_target("claude-code", repo) == expected


def test_check_target_writes_nothing(repo: Path) -> None:
    # The release gate runs this on a tree it is about to tag, and refuses to tag a dirty tree — so
    # the check must not touch a single byte, not even the mtimes it would take to rebuild in place.
    def snapshot() -> dict[str, tuple[bytes, float]]:
        root = repo / COMMITTED_OUT
        return {
            p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime)
            for p in root.rglob("*")
            if p.is_file()
        }

    before = snapshot()
    assert check_target("claude-code", repo) == []
    assert snapshot() == before


def test_the_desktop_extension_and_the_server_ship_the_same_logo() -> None:
    """One brand, two shipping routes — and nothing else keeps them in step.

    The extension takes its icon from the plugin tree; the MCP server serves its own copy from the
    package (a wheel cannot reach outside it). A rebrand that updates one and forgets the other
    would leave Claude Desktop and the hosted connector wearing different logos.
    """
    extension_icon = PLUGIN_SRC / "targets" / "claude-desktop" / "icon.png"
    served_icon = REPO_ROOT / "sellerclaw_cli" / "assets" / "icon.png"

    assert extension_icon.read_bytes() == served_icon.read_bytes(), (
        "icon.png differs between plugin/targets/claude-desktop and sellerclaw_cli/assets"
    )


# --- ChatGPT ---------------------------------------------------------------------------------------

CHATGPT_MANIFEST = PLUGIN_SRC / "targets" / "chatgpt" / "plugin.json"


@pytest.fixture
def chatgpt(tmp_path: Path) -> Path:
    return assemble("chatgpt", PLUGIN_SRC, tmp_path / "chatgpt", version="9.9.9")


def _openai(manifest: dict[str, object]) -> dict[str, object]:
    extensions = manifest["extensions"]
    assert isinstance(extensions, dict)
    return extensions["com.openai"]


def test_chatgpt_ships_the_manifest_and_server_at_its_root(chatgpt: Path) -> None:
    manifest = json.loads((chatgpt / "plugin.json").read_text())
    servers = json.loads((chatgpt / "mcp.json").read_text())["mcpServers"]

    assert manifest["name"] == "sellerclaw"
    assert manifest["version"] == "9.9.9"
    # One server: the dashboard connects exactly one per plugin.
    # ChatGPT has its own surface on the same host: one tool per action, as its directory requires.
    assert servers == {
        "sellerclaw": {"type": "streamable-http", "url": "https://mcp.sellerclaw.ai/chatgpt/mcp"}
    }
    assert not (chatgpt / ".claude-plugin").exists()
    assert not (chatgpt / ".mcp.json").exists()


def test_chatgpt_leaves_out_what_the_directory_refuses_or_cannot_use(chatgpt: Path) -> None:
    # Lifecycle hooks make a plugin ineligible for the public directory; the owner's shortcuts lean on
    # Claude Code's own frontmatter and $ARGUMENTS.
    assert not (chatgpt / "hooks").exists()
    listed = json.loads((default_shortcuts_src(PLUGIN_SRC) / "shortcuts.json").read_text())
    shortcuts = {item["name"] for item in listed}
    shipped = {p.name for p in (chatgpt / "skills").iterdir()}
    assert shipped.isdisjoint(shortcuts)
    assert shipped == CHATGPT_SKILLS


def _chatgpt_tool_names() -> set[str]:
    from sellerclaw_cli.mcp_server import build_chatgpt_http_server

    server = build_chatgpt_http_server(issuer_url="https://api.test", resource_url=None, api_url="https://api.test")
    return {
        tool.name
        for tool in asyncio.run(server.list_tools())
        if "model" in ((tool.meta or {}).get("ui") or {}).get("visibility", ["model"])
    }


@pytest.mark.parametrize("skill", sorted(CHATGPT_SKILLS))
def test_chatgpt_skills_teach_only_the_tools_chatgpt_has(chatgpt: Path, skill: str) -> None:
    """A skill naming a runner, a CLI command or a tool that is not there sends the model into a wall."""
    from sellerclaw_cli.chatgpt import ACTIONS

    text = (chatgpt / "skills" / skill / "SKILL.md").read_text()
    front, body = text.split("\n---\n", 1)
    known = _chatgpt_tool_names() | {p.name for a in ACTIONS for p in a.params} | {
        "approved_queued", "pending_approval", "out_of_stock", "not_selling", "performance_max",
        "price_list", "listing_id", "product_id",
    }
    named = {word for word in re.findall(r"`([a-z]+(?:_[a-z]+)+)`", body)}

    assert f"name: {skill}" in front
    assert named <= known, sorted(named - known)
    assert not re.search(r"sellerclaw_(read|write|describe|groups|guide)|sellerclaw [a-z-]+ [a-z-]+", text)


def test_chatgpt_package_never_names_claude(chatgpt: Path) -> None:
    # Everything in it is read inside ChatGPT — by the owner in the Skills tab, by the reviewer — so a
    # guide edited for Claude must say "a coding agent" or "the chat", not name another product.
    named = sorted(
        p.relative_to(chatgpt).as_posix()
        for p in chatgpt.rglob("*")
        if p.is_file() and p.suffix in {".md", ".json"} and "claude" in p.read_text().lower()
    )

    assert not named, named

def test_chatgpt_every_path_the_manifest_names_ships(chatgpt: Path) -> None:
    openai = _openai(json.loads((chatgpt / "plugin.json").read_text()))
    interface = openai["interface"]
    assert isinstance(interface, dict)

    paths = [interface["logo"], interface["composerIcon"], openai["onboardingSkill"]]

    assert all(isinstance(p, str) and p.startswith("./") and (chatgpt / p).is_file() for p in paths), paths


def test_chatgpt_listing_fits_the_dashboard_limits() -> None:
    interface = _openai(json.loads(CHATGPT_MANIFEST.read_text()))["interface"]
    assert isinstance(interface, dict)

    assert len(interface["displayName"]) <= 30
    assert len(interface["shortDescription"]) <= 30
    assert len(interface["longDescription"]) <= 4000
    assert len(interface["developerName"]) <= 80
    assert 0 < len(interface["capabilities"]) <= 20
    assert all(len(c) <= 120 for c in interface["capabilities"])
    assert 0 < len(interface["defaultPrompt"]) <= 3
    assert all(len(p) <= 128 and "@" not in p for p in interface["defaultPrompt"])
    urls = ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL")
    assert all(interface[key].startswith("https://") for key in urls)


def test_chatgpt_review_cases_name_tools_the_model_can_call() -> None:
    review = _openai(json.loads(CHATGPT_MANIFEST.read_text()))["review"]
    assert isinstance(review, dict)
    cases = review["test_cases"]
    # A card's own buttons call some tools the model never sees; a review case cannot expect those.
    callable_tools = _chatgpt_tool_names()

    # The dashboard demands exactly five of each kind it scores against, and three it must refuse.
    assert len(cases["positive"]) == 5
    assert len(cases["negative"]) == 3
    assert all(case["prompt"] and case["expected_behavior"] for case in cases["positive"])
    named = {name.strip() for case in cases["positive"] for name in case["tools_triggered"].split(",")}
    assert named <= callable_tools, sorted(named - callable_tools)
    # Credentials go through the dashboard's own form, never into the package.
    assert "test_credentials" not in review
    assert "reviewer_instructions" not in review


def test_pack_zip_puts_the_chatgpt_manifest_at_the_archive_root(chatgpt: Path, tmp_path: Path) -> None:
    archive = pack_zip(chatgpt, tmp_path / "sellerclaw-chatgpt.zip", TARGETS["chatgpt"].zip_folder)

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())

    assert {"plugin.json", "mcp.json", "assets/logo.png", f"skills/{CORE_SKILL}/SKILL.md"} <= names
    assert not any(name.startswith("sellerclaw/") for name in names)
