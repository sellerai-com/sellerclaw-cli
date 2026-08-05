#!/bin/sh
# SellerClaw MCP — one-line installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install.sh | sh
#
# It installs uv (if missing), installs the sellerclaw CLI with the MCP extra, signs you in via
# your browser (no API token to copy), and wires the MCP server into Claude Code. Safe to re-run —
# it upgrades and reconfigures in place.
#
# Claude Desktop is deliberately NOT configured here any more: its own extension needs no Python and
# no uv and signs in from inside Claude, so an entry in claude_desktop_config.json would only add a
# second, worse copy of the same tools.
#
# Opt-outs (set before running):
#   SELLERCLAW_SKIP_LOGIN=1  don't run `auth login`
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
# Nothing is written here. Desktop's own extension is the better path in every way — it installs with
# no prerequisites, signs in from inside Claude and updates itself — so this step only cleans up: a
# `sellerclaw` server left in the config by an older run of this installer would show up alongside
# the extension as a second, identical set of tools, and would still fail on a machine without uv.
case "$(uname -s)" in
  Darwin) CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json" ;;
  *)      CFG="${XDG_CONFIG_HOME:-$HOME/.config}/Claude/claude_desktop_config.json" ;;
esac
CLAUDE_DIR="$(dirname "$CFG")"
EXTENSION_URL='https://github.com/sellerai-com/sellerclaw-cli/releases/download/plugin-latest/sellerclaw.mcpb'

if [ -d "$CLAUDE_DIR" ]; then
  REMOVED=''
  if [ -f "$CFG" ]; then
    # Touch only our own key, and only when the file is JSON we can read back — someone else's
    # config is never ours to rewrite or reformat.
    REMOVED="$(run_py "$CFG" <<'PY'
import json, pathlib, sys
cfg = pathlib.Path(sys.argv[1])
try:
    data = json.loads(cfg.read_text() or "{}")
except Exception:
    raise SystemExit(0)
if not isinstance(data, dict):
    raise SystemExit(0)
servers = data.get("mcpServers")
if isinstance(servers, dict) and servers.pop("sellerclaw", None) is not None:
    cfg.write_text(json.dumps(data, indent=2) + "\n")
    print("removed")
PY
)"
  fi
  if [ "$REMOVED" = "removed" ]; then
    info "Claude Desktop: removed the old SellerClaw entry from $CFG (the extension replaces it)."
  fi
  info "Claude Desktop: install the extension — nothing else to set up:"
  info "  $EXTENSION_URL"
fi

info "All set. In Claude, try: \"list my SellerClaw stores\"."
