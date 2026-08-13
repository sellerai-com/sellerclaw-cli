"""The plugin's capability map must describe exactly what the MCP face exposes.

Two different mistakes, one guard. Documenting a group the MCP server hides teaches an external
agent to reach for something it cannot call — and worse, for the orchestration groups it hides on
purpose (task tree, owner approvals) it advertises actions that are inverted for a person who *is*
the owner. Leaving a visible group out of the map hides real capability behind a discovery round
trip nobody makes.

The list drifted once already: five agent-internal groups were documented long after the allowlist
stopped serving them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sellerclaw_cli.mcp_server import MCP_VISIBLE_GROUPS

pytestmark = pytest.mark.unit

_CAPABILITIES = (
    Path(__file__).resolve().parents[2]
    / "plugin"
    / "shared"
    / "skills"
    / "sellerclaw"
    / "references"
    / "capabilities.md"
)
#: A row's first cell holds the group ids the row is about ("`ebay-store` / `ebay-listings`").
_TABLE_ROW = re.compile(r"^\|\s*(`[^|]+`)\s*\|", re.MULTILINE)
_BACKTICKED = re.compile(r"`([a-z0-9-]+)`")


def _documented_groups(text: str) -> set[str]:
    return {name for cell in _TABLE_ROW.findall(text) for name in _BACKTICKED.findall(cell)}


def test_the_map_documents_no_group_the_mcp_face_hides() -> None:
    documented = _documented_groups(_CAPABILITIES.read_text())

    invisible = sorted(documented - MCP_VISIBLE_GROUPS)

    assert not invisible, (
        "capabilities.md describes groups an MCP client cannot call: "
        f"{', '.join(invisible)}. Either drop the row or add the group to MCP_VISIBLE_GROUPS."
    )


def test_every_visible_group_is_named_in_the_map() -> None:
    """Prose counts: the raw passthrough groups are described in a sentence, not a table row."""
    text = _CAPABILITIES.read_text()

    missing = sorted(group for group in MCP_VISIBLE_GROUPS if f"`{group}`" not in text)

    assert not missing, (
        f"MCP exposes groups the capability map never mentions: {', '.join(missing)}."
    )
