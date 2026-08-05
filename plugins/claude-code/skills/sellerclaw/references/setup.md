# Setup & troubleshooting

## Install (recommended: one line)

macOS / Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install.ps1 | iex
```

The installer sets up `uv`, installs the CLI, signs the user in via the browser, and wires the MCP
server into Claude Code. It does **not** configure Claude Desktop — there the extension below is the
whole setup, and the installer removes a Desktop config entry an older run left behind so the same
tools don't show up twice.

## Manual install

```sh
uv tool install 'sellerclaw-cli[mcp]'     # or: pipx install 'sellerclaw-cli[mcp]'
sellerclaw auth login                      # opens a browser — no API token to copy
```

Then connect a client. These launch via `uvx … sellerclaw-cli[mcp]@latest`, so the server always runs
the latest published version automatically:

- **Claude Code:** `claude mcp add sellerclaw -- uvx --from 'sellerclaw-cli[mcp]@latest' sellerclaw mcp`
- **Claude Desktop:** add to `claude_desktop_config.json` (Settings → Developer → Edit Config), then
  restart:
  ```json
  { "mcpServers": { "sellerclaw": { "command": "uvx", "args": ["--from", "sellerclaw-cli[mcp]@latest", "sellerclaw", "mcp"] } } }
  ```
- **Desktop Extension (.mcpb):** download from
  https://github.com/sellerai-com/sellerclaw-cli/releases/download/plugin-latest/sellerclaw.mcpb and
  double-click it. **Nothing to install first** — it runs on the Node runtime inside Claude Desktop
  and talks to the hosted MCP server. Sign in by asking Claude to run its `sellerclaw_login` tool
  (opens the browser); no terminal, no CLI.

## Authentication model

`sellerclaw auth login` (browser device flow) stores credentials in
`~/.config/sellerclaw/config.toml`. The MCP server reads the **same** file, so **no token belongs in
the Claude config**. Verify with `sellerclaw auth whoami` — it prints whether a token is present and
the exact config path in use. For headless use, set `SELLERCLAW_TOKEN` (and optionally
`SELLERCLAW_API_URL`) in the environment instead.

The Desktop extension runs the very same device flow from inside Claude via its `sellerclaw_login`
tool and writes the same file — so signing in on either side signs in both.

## Troubleshooting

- **"not signed in" / every `run` fails with auth** → run `sellerclaw auth login` once in a terminal.
  Discovery (`groups` / `describe`) works without auth; only `run` needs it.
- **Claude Desktop can't start the server / "command not found"** → the desktop app doesn't always
  inherit your shell PATH. Put the **absolute** path in the config: run `which uvx`
  (`where uvx` on Windows) and use that as `"command"`.
- **`.mcpb` extension shows only `sellerclaw_login`** → that connection is not signed in yet. Run
  that tool: it opens the browser, and the rest of the tools appear as soon as access is approved
  (call it again if it reports it is still waiting).
- **`.mcpb` extension can't reach the server** → it talks to https://mcp.sellerclaw.ai over HTTPS;
  check the network/proxy. Nothing needs to be installed locally for it to work.
- **Wrong account / API** → check `sellerclaw auth whoami`; re-run `sellerclaw auth login`, or set
  `SELLERCLAW_API_URL`.
