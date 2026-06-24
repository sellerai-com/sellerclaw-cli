#!/usr/bin/env python3
"""Manual fallback launcher for the SellerClaw MCP server (the extension's declared entry point).

The bundle stays tiny and cross-platform by *not* shipping Python dependencies — those include
compiled, platform-specific wheels (pydantic-core, …). Instead it runs the published
``sellerclaw-cli[mcp]@latest`` through uv: the ``@latest`` keeps users on the newest release with no
action on their part (uv checks the index each launch and reuses the cached wheel when unchanged).

Claude Desktop normally launches ``uvx`` directly (see ``mcp_config`` in manifest.json); this file
is the equivalent you can run by hand — ``python server/main.py`` — and what ``entry_point`` points
at. Requires `uv` on PATH: https://docs.astral.sh/uv/getting-started/installation/
"""

from __future__ import annotations

import os
import shutil
import sys

_PACKAGE = "sellerclaw-cli[mcp]@latest"


def main() -> None:
    uvx = shutil.which("uvx")
    if uvx is not None:
        argv = [uvx, "--from", _PACKAGE, "sellerclaw", "mcp"]
    else:
        uv = shutil.which("uv")
        if uv is None:
            sys.stderr.write(
                "SellerClaw MCP: 'uv' was not found on PATH. Install it from "
                "https://docs.astral.sh/uv/ and restart Claude.\n"
            )
            raise SystemExit(1)
        argv = [uv, "tool", "run", "--from", _PACKAGE, "sellerclaw", "mcp"]
    # Replace this process so the child speaks MCP over our stdio directly.
    os.execv(argv[0], argv)


if __name__ == "__main__":
    main()
