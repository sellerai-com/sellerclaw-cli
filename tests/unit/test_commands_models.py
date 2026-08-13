"""The model-settings group: one vocabulary, and no command that applies anything by itself."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_overview_reads_the_level_in_use_by_default(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/models").mock(
        return_value=httpx.Response(200, json={"current_effort": "medium", "region": "worldwide"})
    )

    result = runner.invoke(app, ["models", "overview"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert route.calls.last.request.url.params.multi_items() == []


@respx.mock
def test_overview_can_ask_for_one_level_or_all_of_them(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/models").mock(
        return_value=httpx.Response(200, json={"current_effort": "medium"})
    )

    assert runner.invoke(app, ["models", "overview", "--effort", "high"]).exit_code == 0
    assert dict(route.calls.last.request.url.params) == {"effort": "high"}

    assert runner.invoke(app, ["models", "overview", "--all"]).exit_code == 0
    assert dict(route.calls.last.request.url.params) == {"all": "true"}


@pytest.mark.parametrize(
    ("command", "path", "body"),
    [
        pytest.param(
            "set-effort",
            "effort",
            {"effort": "high", "reason": "owner wants stronger answers"},
            id="effort",
        ),
        pytest.param(
            "set-region",
            "region",
            {"region": "us-only", "reason": "data must stay in the US"},
            id="region",
        ),
        pytest.param(
            "set-source",
            "source",
            {"source": "own-only", "reason": "owner runs their own provider"},
            id="source",
        ),
        pytest.param(
            "disable",
            "disable",
            {"target": "moonshot", "reason": "owner objects to this provider"},
            id="disable-provider",
        ),
        pytest.param(
            "enable",
            "enable",
            {"target": "kimi-k2", "effort": "high", "role": "complex", "reason": "back on"},
            id="enable-one-model-at-one-level",
        ),
    ],
)
@respx.mock
def test_every_change_goes_to_its_endpoint_untouched(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    path: str,
    body: dict[str, object],
) -> None:
    route = respx.post(f"{fake_api_url}/agent/models/{path}").mock(
        return_value=httpx.Response(
            200,
            json={"applied": False, "action_request_id": "1f0e0d0c-0b0a-4090-8070-605040302010"},
        )
    )

    result = runner.invoke(app, ["models", command, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@pytest.mark.parametrize(
    ("command", "body"),
    [
        pytest.param("set-effort", {"effort": "ludicrous", "reason": "why not"}, id="unknown-level"),
        pytest.param("set-region", {"region": "eu-only", "reason": "gdpr"}, id="unknown-region"),
        pytest.param("set-source", {"source": "mine", "reason": "privacy"}, id="unknown-source"),
        pytest.param("set-effort", {"effort": "high"}, id="no-reason"),
        pytest.param("disable", {"reason": "no target given"}, id="no-target"),
    ],
)
@respx.mock
def test_a_malformed_change_never_reaches_the_owner(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    body: dict[str, object],
) -> None:
    """Caught locally: a typo must not turn into an approval the owner has to read and reject."""
    route = respx.post(f"{fake_api_url}/agent/models/{command.removeprefix('set-')}").mock(
        return_value=httpx.Response(200, json={})
    )

    result = runner.invoke(app, ["models", command, "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert route.call_count == 0
