from __future__ import annotations

import httpx
import pytest
import respx

from sellerclaw_cli._auth import (
    DeviceCode,
    password_login,
    poll_device_token,
    request_device_code,
)
from sellerclaw_cli._errors import AuthError

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    """Replace time.monotonic and time.sleep inside _auth so polling tests run instantly but still timeout correctly."""
    state = {"now": 0.0, "sleeps": 0.0}

    def monotonic() -> float:
        return state["now"]

    def sleep(seconds: float) -> None:
        state["now"] += seconds
        state["sleeps"] += seconds

    monkeypatch.setattr("sellerclaw_cli._auth.time.monotonic", monotonic)
    monkeypatch.setattr("sellerclaw_cli._auth.time.sleep", sleep)
    return state


# ---------------------------------------------------------------------------
# request_device_code
# ---------------------------------------------------------------------------


class TestRequestDeviceCode:
    @respx.mock
    def test_returns_parsed_device_code(self, fake_api_url: str) -> None:
        respx.post(f"{fake_api_url}/agent/auth/device/code").mock(
            return_value=httpx.Response(
                200,
                json={
                    "device_code": "dev_abc",
                    "user_code": "ABCD-1234",
                    "verification_uri": "https://sellerclaw.ai/activate",
                    "expires_in": 600,
                    "interval": 5,
                },
            )
        )
        result = request_device_code(fake_api_url)

        assert result == DeviceCode(
            device_code="dev_abc",
            user_code="ABCD-1234",
            verification_uri="https://sellerclaw.ai/activate",
            expires_in=600,
            interval=5,
        )

    @respx.mock
    def test_sends_no_authorization_header(self, fake_api_url: str) -> None:
        route = respx.post(f"{fake_api_url}/agent/auth/device/code").mock(
            return_value=httpx.Response(
                200,
                json={
                    "device_code": "d",
                    "user_code": "U",
                    "verification_uri": "u",
                    "expires_in": 1,
                    "interval": 1,
                },
            )
        )
        request_device_code(fake_api_url)
        sent = route.calls.last.request
        assert "authorization" not in {k.lower() for k in sent.headers.keys()}


# ---------------------------------------------------------------------------
# poll_device_token
# ---------------------------------------------------------------------------


class TestPollDeviceToken:
    @respx.mock
    def test_returns_token_after_pending_responses(
        self, fake_api_url: str, fake_clock: dict[str, float]
    ) -> None:
        # Two pendings, then grant.
        respx.post(f"{fake_api_url}/agent/auth/device/token").mock(
            side_effect=[
                httpx.Response(200, json={"error": "authorization_pending"}),
                httpx.Response(200, json={"error": "authorization_pending"}),
                httpx.Response(200, json={"agent_token": "sca_granted", "user": {"id": "u1"}}),
            ]
        )
        token = poll_device_token(fake_api_url, "dev_code", interval=5, expires_in=600)

        assert token == "sca_granted"
        # Two sleeps between three polls.
        assert fake_clock["sleeps"] == pytest.approx(10.0)

    @respx.mock
    def test_slow_down_increases_interval_by_5(
        self, fake_api_url: str, fake_clock: dict[str, float]
    ) -> None:
        respx.post(f"{fake_api_url}/agent/auth/device/token").mock(
            side_effect=[
                httpx.Response(200, json={"error": "slow_down"}),
                httpx.Response(200, json={"agent_token": "sca_ok", "user": {"id": "u1"}}),
            ]
        )
        poll_device_token(fake_api_url, "dev", interval=5, expires_in=600)

        # After slow_down, next sleep uses interval+5 = 10s.
        assert fake_clock["sleeps"] == pytest.approx(10.0)

    @pytest.mark.parametrize(
        ("err_code", "expected"),
        [
            pytest.param("expired_token", "expired_token", id="expired"),
            pytest.param("access_denied", "access_denied", id="denied"),
            # A code we have no words for is quoted as it came — all we can honestly say about it.
            pytest.param("something_new", "something_new", id="unknown-code"),
            # This one has words: it almost always means the code ran out while nobody approved it.
            pytest.param("invalid_device_code", "no longer valid", id="invalid-device-code"),
        ],
    )
    @respx.mock
    def test_terminal_error_raises_auth_error(
        self, fake_api_url: str, fake_clock: dict[str, float], err_code: str, expected: str
    ) -> None:
        respx.post(f"{fake_api_url}/agent/auth/device/token").mock(
            return_value=httpx.Response(200, json={"error": err_code})
        )
        with pytest.raises(AuthError) as exc_info:
            poll_device_token(fake_api_url, "dev", interval=5, expires_in=600)

        assert expected in exc_info.value.message

    @respx.mock
    def test_an_invalid_device_code_is_explained_and_says_to_log_in_again(
        self, fake_api_url: str, fake_clock: dict[str, float]
    ) -> None:
        """"Device authorization failed: invalid_device_code" reads like a bug in the CLI and
        leaves the person with nothing to do. The usual cause is a code nobody approved in time."""
        respx.post(f"{fake_api_url}/agent/auth/device/token").mock(
            return_value=httpx.Response(200, json={"error": "invalid_device_code"})
        )
        with pytest.raises(AuthError) as exc_info:
            poll_device_token(fake_api_url, "dev", interval=5, expires_in=600)

        message = exc_info.value.message
        assert "no longer valid" in message
        assert "may have expired" in message
        assert "Run the login again" in message
        assert "invalid_device_code" not in message

    @respx.mock
    def test_a_dropped_connection_is_waited_out_and_the_login_still_completes(
        self, fake_api_url: str, fake_clock: dict[str, float]
    ) -> None:
        """The person already has the code on screen and is approving it in a browser. One SSL EOF
        in those minutes used to kill the whole login with "unexpected CLI error: NetworkError" —
        it has to count as a poll that did not answer yet, not as a refusal."""
        respx.post(f"{fake_api_url}/agent/auth/device/token").mock(
            side_effect=[
                httpx.ReadError("EOF occurred in violation of protocol"),
                httpx.Response(200, json={"error": "authorization_pending"}),
                httpx.Response(200, json={"agent_token": "sca_granted", "user": {"id": "u1"}}),
            ]
        )
        token = poll_device_token(fake_api_url, "dev", interval=5, expires_in=600)

        assert token == "sca_granted"
        # The failed poll waited the normal interval, like the pending one after it.
        assert fake_clock["sleeps"] == pytest.approx(10.0)

    @respx.mock
    def test_an_outage_outlasting_the_code_ends_as_an_expiry_not_as_a_socket_error(
        self, fake_api_url: str, fake_clock: dict[str, float]
    ) -> None:
        """Retrying must still be bounded by the code's own lifetime, and what comes out is the
        login error the person can act on — with the connection named as the likely reason."""
        route = respx.post(f"{fake_api_url}/agent/auth/device/token").mock(
            side_effect=httpx.ReadError("EOF occurred in violation of protocol")
        )
        with pytest.raises(AuthError) as exc_info:
            poll_device_token(fake_api_url, "dev", interval=5, expires_in=10)

        message = exc_info.value.message
        assert "expired" in message.lower()
        assert "could not reach the API" in message
        # It kept asking rather than giving up on the first drop, and still respected expires_in.
        assert route.call_count >= 2
        assert fake_clock["now"] <= 30

    @respx.mock
    def test_timeout_raises_auth_error_when_expires_in_elapses(
        self, fake_api_url: str, fake_clock: dict[str, float]
    ) -> None:
        # Always pending — we rely on sleep advancing monotonic past expires_in.
        respx.post(f"{fake_api_url}/agent/auth/device/token").mock(
            return_value=httpx.Response(200, json={"error": "authorization_pending"})
        )
        with pytest.raises(AuthError) as exc_info:
            poll_device_token(fake_api_url, "dev", interval=5, expires_in=10)

        assert "expired" in exc_info.value.message.lower()
        # Loop should have respected expires_in — not blown past it indefinitely.
        assert fake_clock["now"] <= 30  # generous upper bound


# ---------------------------------------------------------------------------
# password_login
# ---------------------------------------------------------------------------


class TestPasswordLogin:
    @respx.mock
    def test_returns_agent_token(self, fake_api_url: str) -> None:
        route = respx.post(f"{fake_api_url}/agent/auth/token").mock(
            return_value=httpx.Response(200, json={"agent_token": "sca_pw", "user": {"id": "u1"}})
        )
        token = password_login(fake_api_url, "alice@example.com", "hunter2")

        assert token == "sca_pw"
        import json as _json

        body = _json.loads(route.calls.last.request.content)
        assert body == {"email": "alice@example.com", "password": "hunter2"}

    @respx.mock
    def test_401_raises_auth_error(self, fake_api_url: str) -> None:
        respx.post(f"{fake_api_url}/agent/auth/token").mock(
            return_value=httpx.Response(
                401, json={"detail": {"code": "invalid_credentials", "message": "wrong"}}
            )
        )
        with pytest.raises(AuthError):
            password_login(fake_api_url, "alice@example.com", "nope")
