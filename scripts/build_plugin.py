#!/usr/bin/env python3
"""Build the SellerClaw Claude plugin variants from a single source tree.

Source of truth is ``plugin/``:

    plugin/shared/{skills,hooks}/   generic core (works for any MCP agent)
    plugin/claude/{skills,hooks}/   Claude-family overlay (all claude-* targets)
    plugin/targets/<target>/        per-target manifests + MCP/connector declaration

Each target is assembled by merging the layer component dirs (skills/, hooks/) and then overlaying
the target's own files (``.claude-plugin/plugin.json``, ``.mcp.json``/``connector.json``, ...). The
package version from ``pyproject.toml`` is stamped into the plugin/desktop manifest.

``claude-code`` lands in the committed ``plugins/`` tree (the marketplace references it by path); the
rest are throwaway artifacts under ``dist/``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Layer component dirs merged (in order) into a plugin output.
COMPONENT_DIRS = ("skills", "hooks")
# Merge order: generic core first, Claude-family overlay on top.
CLAUDE_LAYERS = ("shared", "claude")


class TargetSpec(NamedTuple):
    # Output location relative to the repo root. Committed targets sit in the repo so the marketplace
    # can point at them; the rest are build artifacts under the git-ignored dist/.
    out: str
    # Component layers merged in. Plugins get the skills/hooks core; the Desktop .mcpb bundle ships
    # only the MCP server (it has no skills concept), so its layers are empty.
    layers: tuple[str, ...] = CLAUDE_LAYERS


TARGETS: dict[str, TargetSpec] = {
    "claude-code": TargetSpec("plugins/claude-code"),
    "claude-desktop": TargetSpec("dist/plugins/claude-desktop", layers=()),
    "claude-web": TargetSpec("dist/plugins/claude-web"),
    "claude-cowork": TargetSpec("dist/plugins/claude-cowork"),
}

# Manifests whose "version" field is stamped from pyproject (whichever is present in the output).
MANIFESTS = (".claude-plugin/plugin.json", "manifest.json")


def read_version(repo_root: Path) -> str:
    data = tomllib.loads((repo_root / "pyproject.toml").read_text())
    return str(data["project"]["version"])


def _merge_components(layer_dir: Path, out: Path) -> None:
    for comp in COMPONENT_DIRS:
        src = layer_dir / comp
        if src.is_dir():
            shutil.copytree(src, out / comp, dirs_exist_ok=True)


def _stamp_version(out: Path, version: str) -> None:
    for rel in MANIFESTS:
        manifest = out / rel
        if manifest.is_file():
            data = json.loads(manifest.read_text())
            data["version"] = version
            manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def assemble(
    target: str,
    plugin_src: Path,
    out: Path,
    version: str,
    layers: tuple[str, ...] = CLAUDE_LAYERS,
) -> Path:
    """Build one target into ``out`` from ``plugin_src``. Pure in its paths (no repo-layout policy)."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for layer in layers:
        _merge_components(plugin_src / layer, out)
    shutil.copytree(plugin_src / "targets" / target, out, dirs_exist_ok=True)
    _stamp_version(out, version)
    return out


def build_target(name: str, repo_root: Path, version: str | None = None) -> Path:
    spec = TARGETS[name]
    version = version or read_version(repo_root)
    out = repo_root / spec.out
    return assemble(name, repo_root / "plugin", out, version, spec.layers)


def available_targets(repo_root: Path) -> list[str]:
    return [n for n in TARGETS if (repo_root / "plugin" / "targets" / n).is_dir()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build SellerClaw Claude plugin variants from plugin/.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Build one target (default: all available).")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repo root containing plugin/ and pyproject.toml (default: this script's repo).",
    )
    parser.add_argument(
        "--version",
        help="Override the stamped version (default: read from pyproject.toml). CI passes the release tag.",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    version = args.version or read_version(repo_root)
    names = [args.target] if args.target else available_targets(repo_root)
    if not names:
        print("no plugin targets found under plugin/targets/", file=sys.stderr)
        return 1
    for name in names:
        out = build_target(name, repo_root, version)
        print(f"built {name} -> {out.relative_to(repo_root)} (v{version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
