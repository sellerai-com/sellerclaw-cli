# SellerClaw MCP — one-line installer for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/sellerclaw/sellerclaw/main/packages/sellerclaw-cli/scripts/install.ps1 | iex
#
# Installs uv (if missing), installs the sellerclaw CLI with the MCP extra, signs you in via your
# browser (no API token to copy), and wires the MCP server into Claude Code and Claude Desktop
# (whichever it finds). Safe to re-run. Opt-outs via env vars before running:
#   $env:SELLERCLAW_SKIP_LOGIN=1     don't run `auth login`
#   $env:SELLERCLAW_FORCE_DESKTOP=1  write the Claude Desktop config even if the app isn't detected
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
  & claude mcp get sellerclaw *> $null
  if ($LASTEXITCODE -eq 0) {
    Info "Claude Code: 'sellerclaw' already configured."
  } else {
    Info "Claude Code: adding the MCP server…"
    & claude mcp add sellerclaw -- $Bin mcp
  }
}

# 5. Claude Desktop -----------------------------------------------------------
$Cfg = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
$Dir = Split-Path $Cfg
if ((Test-Path $Dir) -or ($env:SELLERCLAW_FORCE_DESKTOP -eq '1')) {
  Info "Claude Desktop: writing config at $Cfg"
  New-Item -ItemType Directory -Force -Path $Dir | Out-Null
  if (Test-Path $Cfg) {
    try { $data = Get-Content -Raw $Cfg | ConvertFrom-Json -ErrorAction Stop } catch { $data = [pscustomobject]@{} }
  } else {
    $data = [pscustomobject]@{}
  }
  if (-not ($data.PSObject.Properties.Name -contains 'mcpServers')) {
    $data | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
  }
  $server = [pscustomobject]@{ command = $Bin; args = @('mcp') }
  if ($data.mcpServers.PSObject.Properties.Name -contains 'sellerclaw') {
    $data.mcpServers.sellerclaw = $server
  } else {
    $data.mcpServers | Add-Member -NotePropertyName sellerclaw -NotePropertyValue $server
  }
  ($data | ConvertTo-Json -Depth 10) | Set-Content -Path $Cfg -Encoding UTF8
  Info "Done — restart Claude Desktop to load SellerClaw."
} else {
  Warn "Claude Desktop not detected ($Dir missing). Skipped. Set `$env:SELLERCLAW_FORCE_DESKTOP=1 to configure anyway."
}

Info "All set. In Claude, try: 'list my SellerClaw stores'."
