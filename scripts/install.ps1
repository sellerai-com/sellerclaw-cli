# SellerClaw MCP — one-line installer for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install.ps1 | iex
#
# Installs uv (if missing), installs the sellerclaw CLI with the MCP extra, signs you in via your
# browser (no API token to copy), and wires the MCP server into Claude Code. Safe to re-run.
#
# Claude Desktop is deliberately NOT configured here any more: its own extension needs no Python and
# no uv and signs in from inside Claude, so an entry in claude_desktop_config.json would only add a
# second, worse copy of the same tools. Opt-outs via env vars before running:
#   $env:SELLERCLAW_SKIP_LOGIN=1  don't run `auth login`
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$Pkg = 'sellerclaw-cli[mcp]'

function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "warning: $m" -ForegroundColor Yellow }

function Add-LocalBinToPath {
  foreach ($d in @("$env:USERPROFILE\.local\bin", "$env:USERPROFILE\.cargo\bin")) {
    if ((Test-Path $d) -and ($env:Path -notlike "*$d*")) { $env:Path = "$d;$env:Path" }
  }
}

# Run a Python snippet (piped to stdin), preferring a system interpreter and falling back to uv's.
# The installer edits the user's Claude config through this rather than through PowerShell's own JSON
# support: install.sh runs the identical snippet, so both platforms share one behaviour that is
# covered by tests — and ConvertTo-Json would silently reshape parts of the file we never touched.
function Invoke-Py {
  param([string]$Code, [string[]]$Arguments = @())
  $exe = Get-Command python -ErrorAction SilentlyContinue
  if (-not $exe) { $exe = Get-Command python3 -ErrorAction SilentlyContinue }
  if ($exe) { return ($Code | & $exe.Source - @Arguments) }
  return ($Code | & uv run python - @Arguments)
}

Add-LocalBinToPath

# 1. uv -----------------------------------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Info "Installing uv (Python tool manager)…"
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  Add-LocalBinToPath
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv is not on PATH after install — see https://docs.astral.sh/uv/"
}

# 2. CLI ----------------------------------------------------------------------
Info "Installing $Pkg…"
uv tool install --upgrade $Pkg
Add-LocalBinToPath
$Bin = (Get-Command sellerclaw -ErrorAction SilentlyContinue).Source
if (-not $Bin) {
  throw "'sellerclaw' was not found after install — add %USERPROFILE%\.local\bin to PATH and re-run."
}

# MCP launches via `uvx … sellerclaw-cli[mcp]@latest` (not the installed binary) so each Claude start
# auto-updates to the newest release. Resolve an absolute uvx path (uvx ships with uv).
$Uvx = (Get-Command uvx -ErrorAction SilentlyContinue).Source
if (-not $Uvx) { $Uvx = Join-Path (Split-Path (Get-Command uv).Source) 'uvx.exe' }
if (-not (Test-Path $Uvx)) {
  throw "'uvx' was not found (it ships with uv) — see https://docs.astral.sh/uv/"
}

# 3. Sign in ------------------------------------------------------------------
if ($env:SELLERCLAW_SKIP_LOGIN -ne '1') {
  $who = & sellerclaw auth whoami 2>$null
  if ($who -match '"authenticated":true') {
    Info "Already signed in."
  } else {
    Info "Signing in — open the link shown and confirm in your browser."
    try { & sellerclaw auth login } catch { Warn "Sign-in didn't complete. Run 'sellerclaw auth login' any time." }
  }
}

# 4. Claude Code --------------------------------------------------------------
if (Get-Command claude -ErrorAction SilentlyContinue) {
  # Re-add every run so re-running the installer migrates any older (non-auto-updating) config.
  & claude mcp remove sellerclaw *> $null
  Info "Claude Code: adding the MCP server…"
  & claude mcp add sellerclaw -- $Uvx --from 'sellerclaw-cli[mcp]@latest' sellerclaw mcp
}

# 5. Claude Desktop -----------------------------------------------------------
# Nothing is written here. Desktop's own extension is the better path in every way — it installs with
# no prerequisites, signs in from inside Claude and updates itself — so this step only cleans up: a
# `sellerclaw` server left in the config by an older run of this installer would show up alongside
# the extension as a second, identical set of tools, and would still fail on a machine without uv.
$Cfg = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
$Dir = Split-Path $Cfg
$ExtensionUrl = 'https://github.com/sellerai-com/sellerclaw-cli/releases/download/plugin-latest/sellerclaw.mcpb'
# Kept character-for-character identical to the snippet in install.sh — a unit test compares the two,
# so the cleanup cannot behave one way on macOS and another on Windows.
$CleanupPy = @'
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
'@

if (Test-Path $Dir) {
  if (Test-Path $Cfg) {
    if ((Invoke-Py $CleanupPy @($Cfg)) -match 'removed') {
      Info "Claude Desktop: removed the old SellerClaw entry from $Cfg (the extension replaces it)."
    }
  }
  Info "Claude Desktop: install the extension — nothing else to set up:"
  Info "  $ExtensionUrl"
}

Info "All set. In Claude, try: 'list my SellerClaw stores'."
