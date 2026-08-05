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

Nothing rebuilds the committed tree on its own, so an edit to ``plugin/`` that was never followed by
``make plugin`` ships stale skills to everyone installing from the marketplace — silently, with a
green test suite. ``--check`` is the guard: it rebuilds into a temp dir and diffs against the
committed tree, writing nothing. CI and the release gate both run it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
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
    """Plugin version — decoupled from the CLI/PyPI version.

    Sourced from ``plugin/VERSION`` so plugin, skill or manifest changes can ship (and bump the
    version Claude Code caches the marketplace plugin by) without cutting a CLI release. Falls back
    to ``pyproject.toml`` if the file is missing. Callers can still pass an explicit ``--version``.
    """
    version_file = repo_root / "plugin" / "VERSION"
    if version_file.is_file():
        version = version_file.read_text().strip()
        if version:
            return version
    data = tomllib.loads((repo_root / "pyproject.toml").read_text())
    return str(data["project"]["version"])


def _merge_components(layer_dir: Path, out: Path) -> None:
    for comp in COMPONENT_DIRS:
        src = layer_dir / comp
        if src.is_dir():
            shutil.copytree(src, out / comp, dirs_exist_ok=True)


def default_guides_src(plugin_src: Path) -> Path:
    """Where the task guides live relative to ``plugin/`` — ``<repo>/sellerclaw_cli/guides``."""
    return plugin_src.parent / "sellerclaw_cli" / "guides"


def _write_guide_skills(out: Path, guides_src: Path) -> None:
    """Compile every task guide that has a skill counterpart into ``skills/<name>/SKILL.md``.

    The guide bodies live in the Python package because two audiences need the same text: any MCP
    client reads them through the ``sellerclaw_guide`` tool, and the Claude plugin needs them as
    skills. Generating the skills from that single source is what keeps the two from drifting — the
    committed plugin tree is diffed against a fresh build, so a guide edited without a rebuild fails
    ``--check`` instead of quietly shipping two different versions of the same recipe.
    """
    for topic in json.loads((guides_src / "topics.json").read_text()):
        skill = topic.get("skill")
        if not skill:
            continue  # MCP-only guide; the plugin's hand-written core skill covers that ground
        description = topic["description"]
        if '"' in description:
            raise ValueError(f"guide {topic['topic']!r}: description must not contain a double quote")
        body = (guides_src / topic["file"]).read_text()
        skill_file = out / "skills" / skill / "SKILL.md"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(f'---\nname: {skill}\ndescription: "{description}"\n---\n\n{body}')


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
    guides_src: Path | None = None,
) -> Path:
    """Build one target into ``out`` from ``plugin_src``. Pure in its paths (no repo-layout policy)."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for layer in layers:
        _merge_components(plugin_src / layer, out)
    if layers:
        # Only skill-carrying targets get the compiled guides; the Desktop .mcpb has no skills
        # concept and reaches the same text through the `sellerclaw_guide` tool instead.
        _write_guide_skills(out, guides_src or default_guides_src(plugin_src))
    shutil.copytree(plugin_src / "targets" / target, out, dirs_exist_ok=True)
    _stamp_version(out, version)
    return out


def build_target(name: str, repo_root: Path, version: str | None = None) -> Path:
    spec = TARGETS[name]
    version = version or read_version(repo_root)
    out = repo_root / spec.out
    return assemble(name, repo_root / "plugin", out, version, spec.layers)


def pack_zip(out: Path, zip_path: Path, top_dir: str = "sellerclaw") -> Path:
    """Pack an assembled plugin output into a single ``.zip`` whose files live under ``top_dir/``.

    Extracting the archive yields one tidy ``<top_dir>/`` folder ready to drop into claude.ai's
    *Customize -> Personal plugins -> Upload plugin* dialog (the web path for users who would rather
    upload by hand than add the marketplace).
    """
    zip_path = zip_path.with_suffix(".zip")
    staging = zip_path.parent / f".{zip_path.stem}.stage"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(out, staging / top_dir)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=staging, base_dir=top_dir)
    shutil.rmtree(staging)
    return zip_path


def available_targets(repo_root: Path) -> list[str]:
    return [n for n in TARGETS if (repo_root / "plugin" / "targets" / n).is_dir()]


def is_committed(name: str) -> bool:
    """Is this target's output committed to the repo (rather than a throwaway dist/ artifact)?

    Committed output is what the marketplace serves straight from ``main``, so it is the only output
    that can silently drift from ``plugin/`` — nothing rebuilds it on install, push or release.
    """
    return not TARGETS[name].out.startswith("dist/")


def committed_targets(repo_root: Path) -> list[str]:
    return [n for n in available_targets(repo_root) if is_committed(n)]


def _snapshot(root: Path) -> dict[str, tuple[bytes, bool]]:
    """Every file under ``root`` as content + executable bit, keyed by its relative path."""
    return {
        p.relative_to(root).as_posix(): (p.read_bytes(), bool(p.stat().st_mode & 0o111))
        for p in root.rglob("*")
        if p.is_file()
    }


def check_target(name: str, repo_root: Path, version: str | None = None) -> list[str]:
    """Compare a target's committed output against a fresh build. Returns drift; empty when in sync.

    Read-only: the fresh build lands in a temp dir, so this never writes to the working tree and can
    run inside the release gate — which demands a clean tree — without dirtying the very tree the
    release is about to tag.
    """
    spec = TARGETS[name]
    version = version or read_version(repo_root)
    with tempfile.TemporaryDirectory() as tmp:
        fresh = assemble(name, repo_root / "plugin", Path(tmp) / name, version, spec.layers)
        want = _snapshot(fresh)
    committed = repo_root / spec.out
    have = _snapshot(committed) if committed.is_dir() else {}

    drift: list[str] = []
    for rel in sorted(want.keys() | have.keys()):
        if rel not in have:
            drift.append(f"never committed: {spec.out}/{rel}")
        elif rel not in want:
            drift.append(f"stale leftover, plugin/ no longer produces it: {spec.out}/{rel}")
        elif have[rel] != want[rel]:
            drift.append(f"out of date: {spec.out}/{rel}")
    return drift


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
    parser.add_argument(
        "--zip",
        type=Path,
        help="After building, pack the target's output into this .zip (one folder, for manual upload "
        "to claude.ai's Upload plugin dialog). Requires --target.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Write nothing: verify the committed plugin output still matches what plugin/ produces, "
        "and exit 1 listing the offending files if it does not. Used by CI and the release gate.",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    version = args.version or read_version(repo_root)
    if args.zip and not args.target:
        print("--zip requires --target", file=sys.stderr)
        return 1
    if args.check:
        if args.zip:
            print("--zip cannot be combined with --check", file=sys.stderr)
            return 1
        if args.target and not is_committed(args.target):
            print(
                f"--check: {args.target} is a throwaway dist/ artifact — nothing is committed to check",
                file=sys.stderr,
            )
            return 1
        names = [args.target] if args.target else committed_targets(repo_root)
        drift = [line for name in names for line in check_target(name, repo_root, version)]
        if drift:
            print("the committed plugin no longer matches plugin/:", file=sys.stderr)
            for line in drift:
                print(f"  {line}", file=sys.stderr)
            print("\nrun 'make plugin' and commit the result.", file=sys.stderr)
            return 1
        print(f"committed plugin is up to date with plugin/ (v{version}): {', '.join(names)}")
        return 0
    names = [args.target] if args.target else available_targets(repo_root)
    if not names:
        print("no plugin targets found under plugin/targets/", file=sys.stderr)
        return 1
    for name in names:
        out = build_target(name, repo_root, version)
        print(f"built {name} -> {out.relative_to(repo_root)} (v{version})")
        if args.zip:
            zip_path = args.zip if args.zip.is_absolute() else repo_root / args.zip
            archive = pack_zip(out, zip_path)
            print(f"packed {name} -> {archive.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
