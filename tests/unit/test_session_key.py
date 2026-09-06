from __future__ import annotations

import pytest

from sellerclaw_cli._session_key import ENV_SESSION_KEY, resolve_session_key

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(
            "agent:supervisor:sellerclaw-ui:direct:48729abf-b759-46bf-8802-6768891edc7e",
            "agent:supervisor:sellerclaw-ui:direct:48729abf-b759-46bf-8802-6768891edc7e",
            id="chat-session",
        ),
        pytest.param(
            "agent:ebay:subagent:cd0df525-f55c-45a9-b328-02baaa8ece25",
            "agent:ebay:subagent:cd0df525-f55c-45a9-b328-02baaa8ece25",
            id="executor-session",
        ),
        pytest.param("  agent:supervisor:main  ", "agent:supervisor:main", id="whitespace-trimmed"),
        pytest.param("", None, id="empty"),
        pytest.param("   ", None, id="blank"),
        pytest.param("hook:dev", None, id="not-an-agent-session"),
        pytest.param("agent:supervisor", None, id="no-session-part"),
        pytest.param("agent:super visor:main", None, id="space-in-agent-id"),
        pytest.param("agent:supervisor:" + "x" * 300, None, id="too-long"),
    ],
)
def test_resolve_session_key_reads_only_a_well_formed_key(
    value: str, expected: str | None
) -> None:
    assert resolve_session_key({ENV_SESSION_KEY: value}) == expected


def test_resolve_session_key_is_none_when_unset() -> None:
    assert resolve_session_key({}) is None


def test_resolve_session_key_defaults_to_the_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_SESSION_KEY, "agent:supervisor:main")
    assert resolve_session_key() == "agent:supervisor:main"
    monkeypatch.delenv(ENV_SESSION_KEY)
    assert resolve_session_key() is None
