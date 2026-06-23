# Setup & troubleshooting

## Install (recommended: one line)

macOS / Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/sellerclaw/sellerclaw/main/packages/sellerclaw-cli/scripts/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/sellerclaw/sellerclaw/main/packages/sellerclaw-cli/scripts/install.ps1 | iex
```

The installer sets up `uv`, installs the CLI, signs the user in via the browser, and wires the MCP
server into Claude Desktop and Claude Code. After it finishes, **restart Claude Desktop**.

## Manual install

```sh
uv tool install 'sellerclaw-cli[mcp]'     # or: pipx install 'sellerclaw-cli[mcp]'
sellerclaw auth login                      # opens a browser — no API token to copy
```

Then connect a client:

- **Claude Code:** `claude mcp add sellerclaw -- sellerclaw mcp`
- **Claude Desktop:** add to `claude_desktop_config.json` (Settings → Developer → Edit Config), then
  restart:
  ```json
  { "mcpServers": { "sellerclaw": { "command": "sellerclaw", "args": ["mcp"] } } }
  ```
- **Desktop Extension (.mcpb):** double-click the bundle from the SellerClaw repo's
  `packages/sellerclaw-cli/extension` (needs `uv` installed).

## Authentication model

`sellerclaw auth login` (browser device flow) stores credentials in
`~/.config/sellerclaw/config.toml`. The MCP server reads the **same** file, so **no token belongs in
the Claude config**. Verify with `sellerclaw auth whoami` — it prints whether a token is present and
the exact config path in use. For headless use, set `SELLERCLAW_TOKEN` (and optionally
`SELLERCLAW_API_URL`) in the environment instead.

## Troubleshooting

- **"not signed in" / every `run` fails with auth** → run `sellerclaw auth login` once in a terminal.
  Discovery (`groups` / `describe`) works without auth; only `run` needs it.
- **Claude Desktop can't start the server / "command not found"** → the desktop app doesn't always
  inherit your shell PATH. Put the **absolute** path in the config: run `which sellerclaw`
  (`where sellerclaw` on Windows) and use that as `"command"`.
- **`.mcpb` extension won't launch** → it runs the published package via `uvx`, so `uv` must be
  installed and on PATH. Install from https://docs.astral.sh/uv/ and restart Claude.
- **Wrong account / API** → check `sellerclaw auth whoami`; re-run `sellerclaw auth login`, or set
  `SELLERCLAW_API_URL`.
