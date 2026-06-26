from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from scripts.build_plugin import TARGETS, assemble, available_targets, pack_zip, read_version

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = REPO_ROOT / "plugin"

CORE_SKILL = "sellerclaw"
TASK_RECIPES = (
    "sellerclaw-listings",
    "sellerclaw-orders",
    "sellerclaw-ads",
    "sellerclaw-research",
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
    out = assemble(target, PLUGIN_SRC, tmp_path / target, version="0.0.0", layers=spec.layers)
    # Every target carries at least one stampable manifest.
    has_manifest = (out / ".claude-plugin" / "plugin.json").is_file() or (out / "manifest.json").is_file()
    assert has_manifest, target
    # Plugin targets (non-empty layers) ship the shared skills core; the Desktop .mcpb bundle does not.
    if spec.layers:
        assert (out / "skills" / CORE_SKILL / "SKILL.md").is_file(), target
    else:
        assert not (out / "skills").exists(), target


def test_pack_zip_wraps_output_in_a_single_folder(tmp_path: Path) -> None:
    # The web upload bundle must extract to one tidy folder so users can drop it straight into
    # claude.ai's Upload plugin dialog.
    out = assemble("claude-web", PLUGIN_SRC, tmp_path / "out", version="0.0.0", layers=TARGETS["claude-web"].layers)
    archive = pack_zip(out, tmp_path / "sellerclaw-claude-web.zip")

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
