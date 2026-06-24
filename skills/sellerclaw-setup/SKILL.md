---
name: sellerclaw-setup
description: "Use when the user wants to install, connect, or set up SellerClaw — the SellerClaw CLI or its MCP server — so this assistant can run their e-commerce stores (Shopify, eBay, Amazon, ads, suppliers, research), or asks how to get started with SellerClaw, or hits a connection or sign-in problem with it."
---

# Set up SellerClaw

Help the user connect their SellerClaw account to this assistant. SellerClaw runs their e-commerce
business (stores, orders, listings, ads, suppliers, email, research); the assistant drives it through
the **SellerClaw MCP server**, which is shipped inside the `sellerclaw` CLI. Goal of this skill: get the
CLI installed, the user signed in, and the MCP server wired into their assistant. Then `sellerclaw_*`
tools become available and the operational skills take over.

Pick the path that matches the user. Recommend the one-line installer first — it does everything.

## Fastest: one-line installer

Installs `uv`, installs the CLI, opens the browser to sign in, and wires the MCP server into Claude
Code and Claude Desktop automatically.

macOS / Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/sellerai-com/sellerclaw-cli/main/scripts/install.ps1 | iex
```

After it finishes, **restart the assistant app** (Claude Desktop) so it picks up the new server.

## Manual install

```sh
uv tool install 'sellerclaw-cli[mcp]'   # or: pipx install 'sellerclaw-cli[mcp]'
sellerclaw auth login                    # opens a browser — no API token to copy
```

Then connect the client. All of these launch via `uvx … @latest`, so the server always runs the latest
published version:

- **Claude Code:**
  ```sh
  claude mcp add sellerclaw -- uvx --from 'sellerclaw-cli[mcp]@latest' sellerclaw mcp
  ```
- **Claude Desktop:** Settings → Developer → Edit Config, add the server, then restart:
  ```json
  { "mcpServers": { "sellerclaw": { "command": "uvx", "args": ["--from", "sellerclaw-cli[mcp]@latest", "sellerclaw", "mcp"] } } }
  ```
- **Other MCP clients (Cursor, Agent SDK, etc.):** same command — `uvx --from 'sellerclaw-cli[mcp]@latest' sellerclaw mcp`, transport **stdio**.
- **Desktop Extension (.mcpb):** download and double-click (needs `uv` installed):
  https://github.com/sellerai-com/sellerclaw-cli/releases/latest/download/sellerclaw.mcpb

## Verify it worked

- `sellerclaw auth whoami` — prints whether a token is present and the config path in use.
- In the assistant, the `sellerclaw_groups` / `sellerclaw_describe` / `sellerclaw_run` tools should now
  be available. If only the CLI is installed (no MCP), `sellerclaw guide` confirms the CLI works.

## How sign-in works

`sellerclaw auth login` uses a browser device flow and stores credentials in
`~/.config/sellerclaw/config.toml`. The MCP server reads the **same file**, so **no token goes in the
client config**. For headless use, set `SELLERCLAW_TOKEN` (and optionally `SELLERCLAW_API_URL`) in the
environment instead.

## Troubleshooting

- **Every action fails with "not signed in"** → run `sellerclaw auth login` once in a terminal.
  Discovery (`groups` / `describe`) works without auth; only running commands needs it.
- **Claude Desktop says "command not found" / won't start the server** → the desktop app doesn't always
  inherit the shell PATH. Put the **absolute** path to `uvx` in the config: run `which uvx`
  (`where uvx` on Windows) and use that as `"command"`.
- **`.mcpb` extension won't launch** → it runs the published package via `uvx`, so `uv` must be on
  PATH. Install `uv` from https://docs.astral.sh/uv/ and restart the app.
- **Wrong account or environment** → check `sellerclaw auth whoami`; re-run `sellerclaw auth login`, or
  set `SELLERCLAW_API_URL`.

## After setup

Once connected, the assistant can operate the user's stores directly. For the full set of task skills
(listings, orders, ads, research) packaged together, install the Claude plugin:
`/plugin marketplace add sellerai-com/sellerclaw-cli` → `/plugin install sellerclaw@sellerclaw`.
