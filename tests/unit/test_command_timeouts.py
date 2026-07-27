"""Per-command HTTP budgets.

A publish or a draft does real work inside the request — a model call per product to place the
category and fill the item specifics, then the marketplace's own latency. Under the shared 30s
default those calls were cut off while still working, and the caller could not tell that from a
failure: it re-sent, and ended up with two of whatever it had just made. So the slow commands carry
their own budget, ``describe`` reports it (a caller wrapping us in its own deadline has no other way
to learn it), and ``--timeout`` overrides both.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli import _runtime
from sellerclaw_cli._client import DEFAULT_TIMEOUT_SECONDS, Client
from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS, REGISTRY
from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "46438868-3117-408f-a7d6-7e8a4b55e4c9"
PRODUCT_ID = "a847c4af-86ec-4f26-8861-357637e57c14"

#: Every command that drafts onto a marketplace or pushes to it. Each is a request the server spends
#: minutes inside, so each must declare the long budget rather than inherit the default.
_SLOW_COMMANDS = (
    pytest.param("ebay-listings", "create-drafts", id="ebay-create-drafts"),
    pytest.param("ebay-listings", "preview-drafts", id="ebay-preview-drafts"),
    pytest.param("ebay-listings", "publish-product", id="ebay-publish-product"),
    pytest.param("ebay-listings", "publish", id="ebay-publish"),
    pytest.param("shopify-listings", "create-drafts", id="shopify-create-drafts"),
    pytest.param("shopify-listings", "publish-product", id="shopify-publish-product"),
    pytest.param("shopify-listings", "publish", id="shopify-publish"),
    pytest.param("amazon-listings", "draft", id="amazon-draft"),
    pytest.param("amazon-listings", "publish", id="amazon-publish"),
    pytest.param("walmart-listings", "draft", id="walmart-draft"),
    pytest.param("walmart-listings", "publish", id="walmart-publish"),
    pytest.param("etsy-listings", "draft", id="etsy-draft"),
    pytest.param("etsy-listings", "publish", id="etsy-publish"),
    pytest.param("woocommerce-listings", "draft", id="woo-draft"),
    pytest.param("woocommerce-listings", "publish", id="woo-publish"),
    pytest.param("bigcommerce-listings", "draft", id="bigcommerce-draft"),
    pytest.param("bigcommerce-listings", "publish", id="bigcommerce-publish"),
    pytest.param("wix-listings", "draft", id="wix-draft"),
    pytest.param("wix-listings", "publish", id="wix-publish"),
    pytest.param("tiktok-shop-listings", "draft", id="tiktok-draft"),
    pytest.param("tiktok-shop-listings", "publish", id="tiktok-publish"),
    pytest.param("files", "upload", id="files-upload"),
    pytest.param("files", "from-url", id="files-from-url"),
)

#: Reads: a row lookup that hangs past 30s is broken, and failing fast is the useful answer.
_FAST_COMMANDS = (
    pytest.param("ebay-listings", "list", id="ebay-list"),
    pytest.param("listings", "bulk-publish", id="bulk-publish-returns-a-job"),
    pytest.param("listings", "bulk-job", id="bulk-job-poll"),
    pytest.param("catalog", "list", id="catalog-list"),
)


def _spec(group: str, command: str) -> Any:
    matched = next((g for g in REGISTRY if g.name == group), None)
    assert matched is not None, f"unknown group {group!r}"
    cmd = next((c for c in matched.commands if c.name == command), None)
    assert cmd is not None, f"unknown command {group} {command}"
    return cmd


@pytest.fixture
def env(
    isolated_config_home: Path,  # noqa: ARG001 — keeps config reads off the real ~/.config
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> str:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    return fake_api_url


@pytest.fixture
def recorded_timeouts(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the budget every client is built with, still returning a real Client."""
    seen: list[float] = []
    original = Client.from_env.__func__  # type: ignore[attr-defined] — unwrap the classmethod

    def _spy(cls: type[Client], *, timeout: float | None = None) -> Client:
        client = original(cls, timeout=timeout)
        seen.append(client.timeout)
        return client

    monkeypatch.setattr(Client, "from_env", classmethod(_spy))
    return seen


class TestDeclaredBudgets:
    @pytest.mark.parametrize(("group", "command"), _SLOW_COMMANDS)
    def test_marketplace_work_declares_the_long_budget(self, group: str, command: str) -> None:
        assert _spec(group, command).effective_timeout == LONG_TIMEOUT_SECONDS

    @pytest.mark.parametrize(("group", "command"), _FAST_COMMANDS)
    def test_reads_keep_the_default(self, group: str, command: str) -> None:
        assert _spec(group, command).effective_timeout == DEFAULT_TIMEOUT_SECONDS

    def test_long_budget_is_well_clear_of_the_default(self) -> None:
        # A publish observed in production ran past three minutes; the point of the tier is that it
        # is not a nudge but a different order of wait.
        assert LONG_TIMEOUT_SECONDS >= DEFAULT_TIMEOUT_SECONDS * 4


class TestBudgetReachesTheClient:
    @respx.mock
    def test_publish_product_waits_the_long_budget(
        self, env: str, recorded_timeouts: list[float]
    ) -> None:
        respx.post(
            f"{env}/agent/stores/{STORE_ID}/ebay-draft-listings/publish-product"
        ).mock(return_value=httpx.Response(200, json={"results": [], "errors": []}))

        result = runner.invoke(
            app,
            [
                "ebay-listings",
                "publish-product",
                STORE_ID,
                "-b",
                json.dumps({"product_ids": [PRODUCT_ID]}),
            ],
        )

        assert result.exit_code == 0, result.output
        assert recorded_timeouts == [LONG_TIMEOUT_SECONDS]

    @respx.mock
    def test_a_read_still_fails_fast(self, env: str, recorded_timeouts: list[float]) -> None:
        respx.get(f"{env}/agent/stores/{STORE_ID}/listings").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        result = runner.invoke(app, ["ebay-listings", "list", STORE_ID])

        assert result.exit_code == 0, result.output
        assert recorded_timeouts == [DEFAULT_TIMEOUT_SECONDS]

    @respx.mock
    def test_global_timeout_overrides_the_command(
        self, env: str, recorded_timeouts: list[float]
    ) -> None:
        # An unusually large batch is the caller's to know about, so the flag wins over our estimate.
        respx.post(
            f"{env}/agent/stores/{STORE_ID}/ebay-draft-listings/publish-product"
        ).mock(return_value=httpx.Response(200, json={"results": [], "errors": []}))

        result = runner.invoke(
            app,
            [
                "--timeout",
                "600",
                "ebay-listings",
                "publish-product",
                STORE_ID,
                "-b",
                json.dumps({"product_ids": [PRODUCT_ID]}),
            ],
        )

        assert result.exit_code == 0, result.output
        assert recorded_timeouts == [600.0]

    @respx.mock
    def test_global_timeout_also_raises_a_read(
        self, env: str, recorded_timeouts: list[float]
    ) -> None:
        respx.get(f"{env}/agent/stores/{STORE_ID}/listings").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        result = runner.invoke(app, ["--timeout", "90", "ebay-listings", "list", STORE_ID])

        assert result.exit_code == 0, result.output
        assert recorded_timeouts == [90.0]


class TestTimeoutMessage:
    def test_message_names_the_budget_that_ran_out(self) -> None:
        # "timed out" alone reads as "the server is down" — the one thing it does not mean here.
        client = Client(base_url="https://api.test", token=None, timeout=LONG_TIMEOUT_SECONDS)
        try:
            with respx.mock:
                respx.post("https://api.test/agent/thing").mock(
                    side_effect=httpx.ReadTimeout("timed out")
                )
                with pytest.raises(Exception) as excinfo:  # noqa: PT011 — NetworkError, checked below
                    client.request("POST", "/agent/thing", json={})
        finally:
            client.close()

        message = str(excinfo.value)
        assert "after 180s" in message
        assert "check current state before resending" in message


class TestDescribeReportsTheBudget:
    def test_describe_tells_the_caller_how_long_to_allow(self, env: str) -> None:  # noqa: ARG002
        result = runner.invoke(app, ["describe", "ebay-listings", "publish-product"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)["data"]
        assert payload["timeout_seconds"] == LONG_TIMEOUT_SECONDS

    def test_every_command_reports_a_budget(self, env: str) -> None:  # noqa: ARG002
        result = runner.invoke(app, ["describe", "listings"])

        assert result.exit_code == 0, result.output
        commands = json.loads(result.stdout)["data"]["commands"]
        assert commands, "describe returned no commands"
        assert all(item["timeout_seconds"] > 0 for item in commands)


def test_run_operation_defaults_to_the_client_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hand-written command that passes no budget still gets the shared default, not None."""
    seen: list[float | None] = []

    class _Ctx:
        obj: dict[str, Any] = {}

    def _capture(*, timeout: float | None = None) -> Client:
        seen.append(timeout)
        return Client(base_url="https://api.test", token=None)

    monkeypatch.setattr(_runtime.Client, "from_env", _capture)
    monkeypatch.setattr(
        Client, "request", lambda self, *a, **kw: {"ok": True}  # noqa: ARG005
    )

    _runtime.run_operation(_Ctx(), "GET", "/agent/thing")  # type: ignore[arg-type]

    assert seen == [None]
