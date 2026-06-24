#!/bin/sh
# SellerClaw MCP — one-line installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install.sh | sh
#
# It installs uv (if missing), installs the sellerclaw CLI with the MCP extra, signs you in via
# your browser (no API token to copy), and wires the MCP server into Claude Code and Claude
# Desktop (whichever it finds). Safe to re-run — it upgrades and reconfigures in place.
#
# Opt-outs (set before running):
#   SELLERCLAW_SKIP_LOGIN=1     don't run `auth login`
#   SELLERCLAW_FORCE_DESKTOP=1  write the Claude Desktop config even if the app isn't detected
set -eu

PKG='sellerclaw-cli[mcp]'

info()  { printf '\033[1;34m==>\033[0m %s\n' "$1" >&2; }
warn()  { printf '\033[1;33mwarning:\033[0m %s\n' "$1" >&2; }
fail()  { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

# Put the common user bin dirs on PATH for this process so freshly-installed tools resolve.
ensure_path() {
  for d in "$HOME/.local/bin" "${XDG_BIN_HOME:-}" "${CARGO_HOME:-$HOME/.cargo}/bin"; do
    [ -n "$d" ] || continue
    case ":$PATH:" in
      *":$d:"*) ;;
      *) [ -d "$d" ] && PATH="$d:$PATH" ;;
    esac
  done
  export PATH
}

# Run a Python snippet (from stdin), preferring a system interpreter, falling back to uv's.
run_py() {
  _py="$(command -v python3 || command -v python || true)"
  if [ -n "$_py" ]; then
    "$_py" - "$@"
  else
    uv run python - "$@"
  fi
}

ensure_path

# 1. uv -----------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv (Python tool manager)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ensure_path
fi
command -v uv >/dev/null 2>&1 || fail "uv is not on PATH after install — see https://docs.astral.sh/uv/"

# 2. CLI ----------------------------------------------------------------------
info "Installing $PKG…"
uv tool install --upgrade "$PKG"
ensure_path

BIN="$(command -v sellerclaw || true)"
[ -n "$BIN" ] || fail "the 'sellerclaw' command was not found after install — add ~/.local/bin to your PATH and re-run."

# The MCP server is launched via `uvx … sellerclaw-cli[mcp]@latest`, NOT the installed binary, so
# every Claude start auto-updates to the newest published release with no action from the user.
# Resolve an absolute uvx path (uvx ships with uv) — the desktop app doesn't always inherit shell PATH.
UVX="$(command -v uvx || true)"
[ -n "$UVX" ] || UVX="$(dirname "$(command -v uv)")/uvx"
[ -x "$UVX" ] || fail "the 'uvx' command was not found (it ships with uv) — see https://docs.astral.sh/uv/"

# 3. Sign in ------------------------------------------------------------------
if [ "${SELLERCLAW_SKIP_LOGIN:-0}" != "1" ]; then
  if sellerclaw auth whoami 2>/dev/null | grep -q '"authenticated":true'; then
    info "Already signed in."
  else
    info "Signing in — a link and a code will appear; open the link and confirm in your browser."
    sellerclaw auth login || warn "Sign-in didn't complete. Run 'sellerclaw auth login' any time."
  fi
fi

# 4. Claude Code --------------------------------------------------------------
if command -v claude >/dev/null 2>&1; then
  # Re-add every run so re-running the installer migrates any older (non-auto-updating) config.
  claude mcp remove sellerclaw >/dev/null 2>&1 || true
  info "Claude Code: adding the MCP server…"
  claude mcp add sellerclaw -- "$UVX" --from 'sellerclaw-cli[mcp]@latest' sellerclaw mcp \
    || warn "Couldn't add to Claude Code automatically; run: claude mcp add sellerclaw -- \"$UVX\" --from 'sellerclaw-cli[mcp]@latest' sellerclaw mcp"
fi

# 5. Claude Desktop -----------------------------------------------------------
case "$(uname -s)" in
  Darwin) CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json" ;;
  *)      CFG="${XDG_CONFIG_HOME:-$HOME/.config}/Claude/claude_desktop_config.json" ;;
esac
CLAUDE_DIR="$(dirname "$CFG")"

if [ -d "$CLAUDE_DIR" ] || [ "${SELLERCLAW_FORCE_DESKTOP:-0}" = "1" ]; then
  info "Claude Desktop: writing config at $CFG"
  mkdir -p "$CLAUDE_DIR"
  # Merge our server into mcpServers, preserving any existing config. Launch via uvx …@latest so each
  # start auto-updates; absolute uvx path so the desktop app finds it without inheriting shell PATH.
  run_py "$CFG" "$UVX" <<'PY'
import json, pathlib, sys
cfg = pathlib.Path(sys.argv[1])
command = sys.argv[2]
data = {}
if cfg.exists():
    try:
        data = json.loads(cfg.read_text() or "{}")
    except Exception:
        data = {}
if not isinstance(data, dict):
    data = {}
servers = data.setdefault("mcpServers", {})
servers["sellerclaw"] = {"command": command, "args": ["--from", "sellerclaw-cli[mcp]@latest", "sellerclaw", "mcp"]}
cfg.write_text(json.dumps(data, indent=2) + "\n")
PY
  info "Done — restart Claude Desktop to load SellerClaw."
else
  warn "Claude Desktop not detected ($CLAUDE_DIR missing). Skipped. Re-run with SELLERCLAW_FORCE_DESKTOP=1 to set it up anyway."
fi

info "All set. In Claude, try: \"list my SellerClaw stores\"."
