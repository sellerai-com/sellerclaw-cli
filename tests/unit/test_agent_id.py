from __future__ import annotations

from pathlib import Path

import pytest

from sellerclaw_cli._agent_id import resolve_agent_id

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("cwd", "expected"),
    [
        pytest.param(
            "/home/node/.openclaw/workspace-supervisor",
            "supervisor",
            id="exact-workspace-segment",
        ),
        pytest.param(
            "/home/node/.openclaw/workspace-product_scout/sub/dir",
            "product_scout",
            id="subdirectory-of-workspace",
        ),
        pytest.param(
            "/home/node/.openclaw/workspace-a/inner/workspace-b",
            "b",
            id="multiple-workspace-segments-takes-last",
        ),
        pytest.param("/home/node", None, id="no-workspace-segment"),
        pytest.param("/", None, id="root-path"),
        pytest.param(
            "/home/node/.openclaw/workspace-bad id",
            None,
            id="invalid-id-contains-space",
        ),
        pytest.param(
            "/home/node/.openclaw/workspace-" + ("a" * 65),
            None,
            id="invalid-id-exceeds-max-length",
        ),
        pytest.param(
            "/home/node/.openclaw/workspace-" + ("a" * 64),
            "a" * 64,
            id="id-at-max-length-boundary",
        ),
        pytest.param(
            "/home/node/.openclaw/workspace-foo$bar",
            None,
            id="invalid-id-disallowed-character",
        ),
        pytest.param(
            "/home/node/.openclaw/workspace-/foo",
            None,
            id="empty-id-after-prefix",
        ),
    ],
)
def test_resolve_agent_id_with_explicit_cwd(cwd: str, expected: str | None) -> None:
    assert resolve_agent_id(cwd) == expected


def test_resolve_agent_id_defaults_to_os_getcwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace-supervisor"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    assert resolve_agent_id() == "supervisor"
