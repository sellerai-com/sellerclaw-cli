# Install the SellerClaw skill for Claude Code / Cursor. No CLI, Python, or uv required — it just
# downloads the skill's markdown into your skills directory.
#
#   irm https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install-skill.ps1 | iex
#
# Install somewhere else (e.g. Cursor) by setting $env:SKILLS_DIR first.
$ErrorActionPreference = 'Stop'

$Base = "https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/plugin/shared/skills/sellerclaw"
$SkillsDir = if ($env:SKILLS_DIR) { $env:SKILLS_DIR } else { Join-Path $env:USERPROFILE ".claude\skills" }
$Dest = Join-Path $SkillsDir "sellerclaw"
$Files = @("SKILL.md", "references/setup.md", "references/capabilities.md")

Write-Host "Installing the SellerClaw skill into $Dest …"
foreach ($f in $Files) {
  $target = Join-Path $Dest ($f -replace '/', '\')
  New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
  Invoke-WebRequest -UseBasicParsing -Uri "$Base/$f" -OutFile $target
}
Write-Host "Done. Restart Claude Code (or reload skills) to pick it up."
