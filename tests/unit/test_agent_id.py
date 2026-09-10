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
    assert resolve_agent_id(cwd, environ={}) == expected


def test_resolve_agent_id_defaults_to_os_getcwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace-supervisor"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    assert resolve_agent_id() == "supervisor"


# ---------------------------------------------------------------------------
# The session key answers when the path has walked out of the workspace
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cwd", "session_key", "expected"),
    [
        pytest.param(
            "/tmp",
            "agent:supplier:subagent:590fc53a",
            "supplier",
            id="session-names-the-agent-outside-any-workspace",
        ),
        pytest.param(
            "/home/node/.openclaw/workspace-supervisor",
            "agent:supplier:subagent:590fc53a",
            "supervisor",
            id="workspace-in-the-path-wins-over-the-session",
        ),
        pytest.param("/tmp", "", None, id="blank-session"),
        pytest.param("/tmp", "hook:dev", None, id="not-an-agent-session"),
        pytest.param("/tmp", "agent:supplier", None, id="session-without-a-tail"),
        pytest.param(
            "/tmp",
            "agent:" + ("a" * 65) + ":subagent:r1",
            None,
            id="session-names-an-over-long-id",
        ),
        pytest.param(
            "/tmp",
            "agent:supplier:" + "x" * 300,
            None,
            id="session-key-too-long-to-be-sent",
        ),
    ],
)
def test_resolve_agent_id_falls_back_to_the_session_key(
    cwd: str, session_key: str, expected: str | None
) -> None:
    assert resolve_agent_id(cwd, environ={"SELLERCLAW_SESSION_KEY": session_key}) == expected


def test_resolve_agent_id_defaults_to_os_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "no-workspace-here"
    plain.mkdir()
    monkeypatch.chdir(plain)
    monkeypatch.setenv("SELLERCLAW_SESSION_KEY", "agent:supplier:subagent:590fc53a")

    assert resolve_agent_id() == "supplier"


def test_resolve_agent_id_is_none_when_neither_names_an_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "no-workspace-here"
    plain.mkdir()
    monkeypatch.chdir(plain)
    monkeypatch.delenv("SELLERCLAW_SESSION_KEY", raising=False)

    assert resolve_agent_id() is None
