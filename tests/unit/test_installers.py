"""The one-line installers' Claude Desktop cleanup — the only part of them that edits a user's file.

Claude Desktop is set up by its own extension now, so the installers write no MCP entry there; what
they do instead is delete the entry an older run left behind, which would otherwise duplicate the
extension's tools. That deletion happens inside somebody's real config, next to other people's MCP
servers, so it is worth pinning down: it must remove our key and nothing else, do nothing on a second
run, and keep its hands off a file it cannot parse.

Both installers run the *same* Python snippet — the macOS/Linux script through a heredoc, the Windows
one through a PowerShell here-string — so testing it once covers both, and the first test here is
what keeps that claim true.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"

OTHER_SERVER = {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/me"]}
OUR_SERVER = {
    "command": "/home/me/.local/bin/uvx",
    "args": ["--from", "sellerclaw-cli[mcp]@latest", "sellerclaw", "mcp"],
}


def _sh_snippet() -> str:
    blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", INSTALL_SH.read_text(), re.S)
    ours = [b for b in blocks if "mcpServers" in b]
    assert len(ours) == 1, f"expected one config-editing snippet in install.sh, found {len(ours)}"
    return ours[0]


def _ps_snippet() -> str:
    blocks = re.findall(r"@'\n(.*?)\n'@", INSTALL_PS1.read_text(), re.S)
    ours = [b for b in blocks if "mcpServers" in b]
    assert len(ours) == 1, f"expected one config-editing snippet in install.ps1, found {len(ours)}"
    return ours[0]


def _run(config: Path) -> str:
    """Run the installer's snippet exactly as the installers do: piped to python, path as argv[1]."""
    result = subprocess.run(
        [sys.executable, "-", str(config)],
        input=_sh_snippet(),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_both_installers_run_the_same_cleanup() -> None:
    assert _sh_snippet() == _ps_snippet()


def test_our_entry_goes_and_everything_else_stays(tmp_path: Path) -> None:
    config = tmp_path / "claude_desktop_config.json"
    config.write_text(
        json.dumps(
            {
                "globalShortcut": "Alt+Space",
                "mcpServers": {"filesystem": OTHER_SERVER, "sellerclaw": OUR_SERVER},
            }
        )
    )

    assert _run(config) == "removed"

    data = json.loads(config.read_text())
    assert data["mcpServers"] == {"filesystem": OTHER_SERVER}
    assert data["globalShortcut"] == "Alt+Space"


def test_second_run_changes_nothing(tmp_path: Path) -> None:
    config = tmp_path / "claude_desktop_config.json"
    config.write_text(json.dumps({"mcpServers": {"sellerclaw": OUR_SERVER}}))
    _run(config)
    after_first = config.read_text()

    # Silence is what tells the installer not to print "removed the old entry" a second time.
    assert _run(config) == ""
    assert config.read_text() == after_first


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("this is not json at all", id="unparseable"),
        pytest.param('["a list", "not an object"]', id="json-but-not-an-object"),
        pytest.param('{"mcpServers": "somehow a string"}', id="mcpServers-not-an-object"),
        pytest.param('{"theme": "dark"}', id="no-mcp-servers-at-all"),
        pytest.param('{"mcpServers": {"filesystem": {"command": "npx"}}}', id="only-other-servers"),
        pytest.param("", id="empty-file"),
    ],
)
def test_a_config_without_our_entry_is_left_byte_for_byte_alone(tmp_path: Path, content: str) -> None:
    config = tmp_path / "claude_desktop_config.json"
    config.write_text(content)

    assert _run(config) == ""
    assert config.read_text() == content
