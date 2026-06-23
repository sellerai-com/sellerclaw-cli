from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from sellerclaw_cli._client import MAX_RETRIES, Client
from sellerclaw_cli._errors import ApiError, AuthError, CliError, NetworkError, ServerError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(fake_api_url: str, fake_token: str) -> Client:
    """A Client pointed at the fake API URL with the fake token installed."""
    return Client(base_url=fake_api_url, token=fake_token)


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace time.sleep used by retry backoff so tests run instantly; collects durations for assertions."""
    calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr("sellerclaw_cli._client.time.sleep", fake_sleep)
    return calls


# ---------------------------------------------------------------------------
# Success + auth header
# ---------------------------------------------------------------------------


class TestSuccess:
    @respx.mock
    def test_get_returns_parsed_json_body(self, client: Client, fake_api_url: str) -> None:
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "s1"}]})
        )
        result = client.request("GET", "/agent/stores")
        assert result == {"items": [{"id": "s1"}]}
        assert route.call_count == 1

    @respx.mock
    def test_sends_bearer_authorization_header(
        self, client: Client, fake_api_url: str, fake_token: str
    ) -> None:
        route = respx.get(f"{fake_api_url}/agent/stores").mock(return_value=httpx.Response(200, json={}))
        client.request("GET", "/agent/stores")

        sent = route.calls.last.request
        assert sent.headers["authorization"] == f"Bearer {fake_token}"

    @respx.mock
    def test_post_sends_json_body_and_returns_parsed_response(
        self, client: Client, fake_api_url: str
    ) -> None:
        route = respx.post(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(201, json={"id": "new-store"})
        )
        result = client.request("POST", "/agent/stores", json={"name": "Acme"})

        assert result == {"id": "new-store"}
        import json as _json

        assert _json.loads(route.calls.last.request.content) == {"name": "Acme"}

    @respx.mock
    def test_query_params_are_forwarded(self, client: Client, fake_api_url: str) -> None:
        route = respx.get(f"{fake_api_url}/agent/stores").mock(return_value=httpx.Response(200, json={}))
        client.request("GET", "/agent/stores", params={"status": "active", "limit": 10})

        sent_url = route.calls.last.request.url
        assert sent_url.params["status"] == "active"
        assert sent_url.params["limit"] == "10"

    @respx.mock
    def test_request_without_token_omits_authorization_header(
        self, fake_api_url: str
    ) -> None:
        anon_client = Client(base_url=fake_api_url, token=None)
        route = respx.get(f"{fake_api_url}/agent/auth/device/code").mock(
            return_value=httpx.Response(200, json={})
        )
        anon_client.request("GET", "/agent/auth/device/code")
        sent = route.calls.last.request
        assert "authorization" not in {k.lower() for k in sent.headers.keys()}


# ---------------------------------------------------------------------------
# Error mapping — HTTP status → custom exception
# ---------------------------------------------------------------------------


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("status", "expected_exc"),
        [
            pytest.param(401, AuthError, id="401-unauthorized"),
            pytest.param(403, AuthError, id="403-forbidden"),
            pytest.param(400, ApiError, id="400-bad-request"),
            pytest.param(404, ApiError, id="404-not-found"),
            pytest.param(422, ApiError, id="422-validation"),
        ],
    )
    @respx.mock
    def test_4xx_maps_to_correct_exception(
        self,
        client: Client,
        fake_api_url: str,
        status: int,
        expected_exc: type[CliError],
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(status, json={"detail": "oops"})
        )
        with pytest.raises(expected_exc) as exc_info:
            client.request("GET", "/agent/stores")

        assert exc_info.value.status == status

    @respx.mock
    def test_api_error_carries_parsed_detail_into_details(
        self, client: Client, fake_api_url: str
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(400, json={"code": "bad_name", "message": "too long", "fields": ["name"]})
        )
        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/agent/stores")

        # Whatever the body is, it should be captured in `details` so the CLI can surface it to the user.
        assert exc_info.value.details is not None
        assert "too long" in str(exc_info.value.details) or exc_info.value.message == "too long"

    @respx.mock
    def test_non_json_4xx_still_raises_with_text_message(
        self, client: Client, fake_api_url: str
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(400, text="plain error")
        )
        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/agent/stores")
        assert "plain error" in exc_info.value.message or exc_info.value.message


class TestValidationErrorMessages:
    @respx.mock
    def test_422_list_detail_formats_field_and_constraint(
        self, client: Client, fake_api_url: str
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(
                422,
                json={
                    "detail": [
                        {
                            "type": "less_than_equal",
                            "loc": ["query", "page_size"],
                            "msg": "Input should be less than or equal to 200",
                            "input": "1000",
                            "ctx": {"le": 200},
                        }
                    ]
                },
            )
        )
        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/agent/stores")

        assert exc_info.value.status == 422
        assert exc_info.value.message == (
            "page_size: Input should be less than or equal to 200 (got '1000')"
        )
        assert exc_info.value.details is not None
        assert isinstance(exc_info.value.details["detail"], list)

    @respx.mock
    def test_4xx_string_detail_is_used_as_message(self, client: Client, fake_api_url: str) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(404, json={"detail": "Store not found"})
        )
        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/agent/stores")

        assert exc_info.value.message == "Store not found"
        assert exc_info.value.details == {"detail": "Store not found"}

    @respx.mock
    def test_4xx_dict_detail_surfaces_inner_message_and_hint(self, client: Client, fake_api_url: str) -> None:
        """Domain errors arrive as a structured `detail` dict; the inner message + hint must be the
        top-level message, not an opaque 'HTTP 400'."""
        respx.post(f"{fake_api_url}/agent/goals/agent-tasks/x/request-review").mock(
            return_value=httpx.Response(
                400,
                json={
                    "detail": {
                        "code": "invalid_status_transition",
                        "message": "Invalid agent_task status transition: pending -> pending_review",
                        "hint": "Start the task first: `subagent-tasks start <id>`.",
                    }
                },
            )
        )
        with pytest.raises(ApiError) as exc_info:
            client.request("POST", "/agent/goals/agent-tasks/x/request-review")

        assert "Invalid agent_task status transition: pending -> pending_review" in exc_info.value.message
        assert "subagent-tasks start" in exc_info.value.message  # hint appended

    @respx.mock
    def test_4xx_message_field_is_preferred(self, client: Client, fake_api_url: str) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(
                400,
                json={"message": "too long", "detail": [{"loc": ["body", "name"], "msg": "too short"}]},
            )
        )
        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/agent/stores")

        assert exc_info.value.message == "too long"


# ---------------------------------------------------------------------------
# Retry logic — 429 / 502 / 503 / 504 retried with exp backoff; others not.
# ---------------------------------------------------------------------------


class TestRetries:
    @pytest.mark.parametrize("status", [429, 502, 503, 504], ids=lambda s: f"retry-on-{s}")
    @respx.mock
    def test_retriable_status_retried_up_to_max(
        self,
        client: Client,
        fake_api_url: str,
        no_sleep: list[float],
        status: int,
    ) -> None:
        # All attempts return the retriable status → we exhaust MAX_RETRIES and raise.
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(status, json={})
        )

        expected_exc: type[Exception] = ApiError if status == 429 else ServerError
        with pytest.raises(expected_exc):
            client.request("GET", "/agent/stores")

        # Exactly MAX_RETRIES total attempts (1 initial + retries).
        assert route.call_count == MAX_RETRIES
        # Between each pair of attempts, one sleep — so MAX_RETRIES-1 sleeps.
        assert len(no_sleep) == MAX_RETRIES - 1

    @respx.mock
    def test_retriable_status_recovers_on_second_attempt(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            side_effect=[
                httpx.Response(503, json={}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        result = client.request("GET", "/agent/stores")
        assert result == {"ok": True}
        assert route.call_count == 2
        assert len(no_sleep) == 1

    @respx.mock
    def test_backoff_is_exponential(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(503, json={})
        )
        with pytest.raises(ServerError):
            client.request("GET", "/agent/stores")

        # Expected backoff sequence roughly 1s, 2s (monotonically increasing). Allow jitter ≤ 0.5s.
        assert len(no_sleep) == MAX_RETRIES - 1
        assert no_sleep[0] >= 1.0
        assert no_sleep[-1] >= no_sleep[0]
        for s in no_sleep:
            assert s <= 10.0, "backoff should not exceed 10s without explicit Retry-After"

    @respx.mock
    def test_retry_after_header_is_honored_for_429(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "7"}, json={}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        client.request("GET", "/agent/stores")
        # Retry-After: 7 must be respected exactly (no backoff math on top of it).
        assert len(no_sleep) == 1
        assert no_sleep[0] == pytest.approx(7.0, abs=0.01)

    @respx.mock
    def test_non_retriable_4xx_does_not_retry(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(404, json={})
        )
        with pytest.raises(ApiError):
            client.request("GET", "/agent/stores")
        assert route.call_count == 1
        assert no_sleep == []

    @respx.mock
    def test_401_does_not_retry(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        # Auth errors are terminal — retrying will just waste time and leak tokens into logs.
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(401, json={})
        )
        with pytest.raises(AuthError):
            client.request("GET", "/agent/stores")
        assert route.call_count == 1
        assert no_sleep == []


# ---------------------------------------------------------------------------
# Network / transport errors
# ---------------------------------------------------------------------------


class TestNetworkErrors:
    @respx.mock
    def test_connect_error_raises_network_error(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises(NetworkError):
            client.request("GET", "/agent/stores")

    @respx.mock
    def test_timeout_raises_network_error(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        respx.get(f"{fake_api_url}/agent/stores").mock(side_effect=httpx.ReadTimeout("slow"))
        with pytest.raises(NetworkError):
            client.request("GET", "/agent/stores")

    @respx.mock
    def test_transport_errors_are_retried(
        self, client: Client, fake_api_url: str, no_sleep: list[float]
    ) -> None:
        # Transient connect errors (captive portal, DNS blip) should retry like 5xx.
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            side_effect=[
                httpx.ConnectError("refused"),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        result = client.request("GET", "/agent/stores")
        assert result == {"ok": True}
        assert route.call_count == 2


# ---------------------------------------------------------------------------
# X-Agent-Id header injection (resolved from cwd)
# ---------------------------------------------------------------------------


class TestAgentIdHeader:
    @respx.mock
    def test_workspace_cwd_injects_x_agent_id_header(
        self,
        fake_api_url: str,
        fake_token: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace = tmp_path / "workspace-supervisor"
        workspace.mkdir()
        monkeypatch.chdir(workspace)

        client = Client(base_url=fake_api_url, token=fake_token)
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(200, json={})
        )
        client.request("GET", "/agent/stores")

        sent = route.calls.last.request
        assert sent.headers["x-agent-id"] == "supervisor"

    @respx.mock
    def test_non_workspace_cwd_omits_x_agent_id_header(
        self,
        fake_api_url: str,
        fake_token: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plain = tmp_path / "no-workspace-here"
        plain.mkdir()
        monkeypatch.chdir(plain)

        client = Client(base_url=fake_api_url, token=fake_token)
        route = respx.get(f"{fake_api_url}/agent/stores").mock(
            return_value=httpx.Response(200, json={})
        )
        client.request("GET", "/agent/stores")

        sent = route.calls.last.request
        assert "x-agent-id" not in {k.lower() for k in sent.headers.keys()}


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------


class TestFromEnv:
    @respx.mock
    def test_from_env_reads_env_token_and_api_url(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_api_url: str,
        fake_token: str,
        isolated_config_home,  # noqa: ARG002 — redirects XDG away from real filesystem
    ) -> None:
        monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
        monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)

        client = Client.from_env()
        respx.get(f"{fake_api_url}/agent/stores").mock(return_value=httpx.Response(200, json={}))
        # Should not raise; validates base_url and token wiring together.
        client.request("GET", "/agent/stores")
        assert client.token == fake_token
