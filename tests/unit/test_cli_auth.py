from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture
def env_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    isolated_config_home: Path,  # noqa: ARG001 — ensures env cleanup runs BEFORE we set SELLERCLAW_API_URL
) -> str:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.delenv("SELLERCLAW_TOKEN", raising=False)
    return fake_api_url


class TestWhoami:
    def test_reports_unauthenticated_when_no_token(
        self, env_api: str, isolated_config_home: Path  # noqa: ARG002
    ) -> None:
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["authenticated"] is False
        assert payload["data"]["api_url"] == env_api

    def test_reports_authenticated_when_env_token_set(
        self,
        env_api: str,  # noqa: ARG002
        isolated_config_home: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
        fake_token: str,
    ) -> None:
        monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["authenticated"] is True


class TestLogout:
    def test_clears_token_from_config(
        self,
        env_api: str,  # noqa: ARG002
        isolated_config_home: Path,  # noqa: ARG002
        fake_token: str,
    ) -> None:
        from sellerclaw_cli import _config

        _config.save_token(fake_token)
        assert _config.load().token == fake_token

        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0
        assert _config.load().token is None


class TestLoginDeviceFlow:
    @respx.mock
    def test_writes_token_to_config_on_success(
        self,
        env_api: str,
        isolated_config_home: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Fake monotonic+sleep so polling is instant.
        t = {"now": 0.0}
        monkeypatch.setattr("sellerclaw_cli._auth.time.monotonic", lambda: t["now"])
        monkeypatch.setattr(
            "sellerclaw_cli._auth.time.sleep", lambda s: t.__setitem__("now", t["now"] + s)
        )

        respx.post(f"{env_api}/agent/auth/device/code").mock(
            return_value=httpx.Response(
                200,
                json={
                    "device_code": "dev_x",
                    "user_code": "ABCD-1234",
                    "verification_uri": "https://sellerclaw.com/activate",
                    "expires_in": 600,
                    "interval": 1,
                },
            )
        )
        respx.post(f"{env_api}/agent/auth/device/token").mock(
            side_effect=[
                httpx.Response(200, json={"error": "authorization_pending"}),
                httpx.Response(200, json={"agent_token": "sca_from_device", "user": {"id": "u1"}}),
            ]
        )

        result = runner.invoke(app, ["auth", "login"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["data"]["authenticated"] is True
        # Verification URI / code should have gone to stderr, not stdout.
        assert "ABCD-1234" in result.stderr
        assert "ABCD-1234" not in result.stdout

        from sellerclaw_cli import _config

        assert _config.load().token == "sca_from_device"

    @respx.mock
    def test_login_password_via_stdin(
        self,
        env_api: str,
        isolated_config_home: Path,  # noqa: ARG002
    ) -> None:
        respx.post(f"{env_api}/agent/auth/token").mock(
            return_value=httpx.Response(
                200, json={"agent_token": "sca_pw", "user": {"id": "u1"}}
            )
        )
        result = runner.invoke(
            app,
            ["auth", "login", "--password"],
            input="alice@example.com\nhunter2\n",
        )
        assert result.exit_code == 0, result.stderr
        from sellerclaw_cli import _config

        assert _config.load().token == "sca_pw"

    def test_password_missing_credentials_on_stdin_is_user_error(
        self,
        env_api: str,  # noqa: ARG002
        isolated_config_home: Path,  # noqa: ARG002
    ) -> None:
        result = runner.invoke(app, ["auth", "login", "--password"], input="")
        assert result.exit_code == 1
        err = json.loads(result.stderr)
        assert err["error"]["code"] == "user_error"
