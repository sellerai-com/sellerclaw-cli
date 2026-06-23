#!/bin/sh
# Install the SellerClaw skill for Claude Code / Cursor. No CLI, Python, or uv required — it just
# downloads the skill's markdown into your skills directory.
#
#   curl -fsSL https://raw.githubusercontent.com/sellerclaw/sellerclaw/main/packages/sellerclaw-cli/scripts/install-skill.sh | sh
#
# Install somewhere else (e.g. Cursor) by setting SKILLS_DIR first:
#   SKILLS_DIR="$HOME/.cursor/skills"  curl -fsSL …/install-skill.sh | sh
set -eu

BASE="https://raw.githubusercontent.com/sellerclaw/sellerclaw/main/packages/sellerclaw-cli/skill/sellerclaw"
SKILLS_DIR="${SKILLS_DIR:-$HOME/.claude/skills}"
DEST="$SKILLS_DIR/sellerclaw"
FILES="SKILL.md references/setup.md references/capabilities.md"

command -v curl >/dev/null 2>&1 || { printf 'error: curl is required\n' >&2; exit 1; }

printf 'Installing the SellerClaw skill into %s …\n' "$DEST" >&2
for f in $FILES; do
  mkdir -p "$DEST/$(dirname "$f")"
  curl -fsSL "$BASE/$f" -o "$DEST/$f"
done
printf 'Done. Restart Claude Code (or reload skills) to pick it up.\n' >&2
