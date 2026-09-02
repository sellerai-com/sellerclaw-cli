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
from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS, REGISTRY, Cmd, _as_provider_read
from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "46438868-3117-408f-a7d6-7e8a4b55e4c9"
PRODUCT_ID = "a847c4af-86ec-4f26-8861-357637e57c14"
JOB_ID = "3f6a5b3c-1b4a-4a2f-9d1e-2c8c2a5f9a11"

#: Every command that drafts onto a marketplace or pushes to it. Each is a request the server spends
#: minutes inside, so each must declare the long budget rather than inherit the default.
_SLOW_COMMANDS = (
    pytest.param("ebay-listings", "create-drafts", id="ebay-create-drafts"),
    pytest.param("ebay-listings", "preview-drafts", id="ebay-preview-drafts"),
    pytest.param("ebay-listings", "publish", id="ebay-publish"),
    pytest.param("shopify-listings", "create-drafts", id="shopify-create-drafts"),
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

#: Research and site-audit lookups. These wait on someone else's queue rather than on us: the
#: research providers are allowed 120s for a single call, and the marketplace-product endpoints poll
#: a task for a further 90s on top. Under the shared default the caller was told "timed out" while
#: the answer was still on its way — a product-niche scan lost its whole Amazon side that way and
#: reported the hole as the provider being down.
_PROVIDER_READ_COMMANDS = (
    pytest.param("research-seo", "amazon-products", id="amazon-products"),
    pytest.param("research-seo", "amazon-reviews", id="amazon-reviews"),
    pytest.param("research-seo", "product-search", id="google-shopping-products"),
    pytest.param("research-seo", "keyword-volume", id="keyword-volume"),
    pytest.param("research-social", "reddit-search", id="reddit-search"),
    pytest.param("research-social", "tiktok-shop-reviews", id="tiktok-shop-reviews"),
    pytest.param("store-audit", "pagespeed", id="store-audit-pagespeed"),
    pytest.param("store-audit", "ai-answers", id="store-audit-ai-answers"),
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

    @pytest.mark.parametrize(("group", "command"), _PROVIDER_READ_COMMANDS)
    def test_provider_lookups_declare_the_long_budget(self, group: str, command: str) -> None:
        assert _spec(group, command).effective_timeout == LONG_TIMEOUT_SECONDS

    @pytest.mark.parametrize(("group", "command"), _PROVIDER_READ_COMMANDS)
    def test_provider_lookups_are_marked_as_writing_nothing(
        self, group: str, command: str
    ) -> None:
        assert _spec(group, command).read_only is True

    @pytest.mark.parametrize(("group", "command"), _SLOW_COMMANDS)
    def test_marketplace_work_is_never_marked_read_only(self, group: str, command: str) -> None:
        """The flag decides what a timed-out caller is told, so a publish must not carry it."""
        assert _spec(group, command).read_only is False

    def test_whole_group_is_covered_not_just_the_commands_listed_here(self) -> None:
        """The budget is declared per group, so a command added later inherits it."""
        for group in ("research-seo", "research-social", "store-audit"):
            spec = next(g for g in REGISTRY if g.name == group)
            assert spec.commands, f"{group} has no commands"
            assert all(c.effective_timeout == LONG_TIMEOUT_SECONDS for c in spec.commands)
            assert all(c.read_only for c in spec.commands)

    def test_a_command_that_states_its_own_budget_keeps_it(self) -> None:
        stated = Cmd("thing", "POST", "/agent/thing", timeout=42.0)

        promoted = _as_provider_read(stated)

        assert promoted.effective_timeout == 42.0
        assert promoted.read_only is True

    def test_long_budget_is_well_clear_of_the_default(self) -> None:
        # A publish observed in production ran past three minutes; the point of the tier is that it
        # is not a nudge but a different order of wait.
        assert LONG_TIMEOUT_SECONDS >= DEFAULT_TIMEOUT_SECONDS * 4


class TestBudgetReachesTheClient:
    @respx.mock
    def test_a_synchronous_publish_waits_the_long_budget_on_the_wire(
        self, env: str, recorded_timeouts: list[float]
    ) -> None:
        """This one does the work inside the request, so the budget has to be the HTTP timeout."""
        respx.post(f"{env}/agent/stores/{STORE_ID}/ebay-listings/publish").mock(
            return_value=httpx.Response(200, json={"results": [], "errors": []})
        )

        result = runner.invoke(
            app,
            [
                "ebay-listings",
                "publish",
                STORE_ID,
                "-b",
                json.dumps({"listing_ids": [PRODUCT_ID]}),
            ],
        )

        assert result.exit_code == 0, result.output
        assert recorded_timeouts == [LONG_TIMEOUT_SECONDS]

    @respx.mock
    def test_a_job_starter_keeps_the_short_wire_timeout(
        self, env: str, recorded_timeouts: list[float]
    ) -> None:
        """It only queues the job, so the call itself is instant — the budget is spent waiting."""
        respx.post(f"{env}/agent/stores/{STORE_ID}/ebay-draft-listings").mock(
            return_value=httpx.Response(
                202, json={"id": JOB_ID, "status": "succeeded", "kind": "draft"}
            )
        )

        result = runner.invoke(
            app,
            [
                "ebay-listings",
                "create-drafts",
                STORE_ID,
                "-b",
                json.dumps({"product_ids": [PRODUCT_ID]}),
            ],
        )

        assert result.exit_code == 0, result.output
        assert recorded_timeouts == [DEFAULT_TIMEOUT_SECONDS]

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
        respx.post(f"{env}/agent/stores/{STORE_ID}/ebay-listings/publish").mock(
            return_value=httpx.Response(200, json={"results": [], "errors": []})
        )

        result = runner.invoke(
            app,
            [
                "--timeout",
                "600",
                "ebay-listings",
                "publish",
                STORE_ID,
                "-b",
                json.dumps({"listing_ids": [PRODUCT_ID]}),
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

    def test_a_lookup_that_ran_out_says_nothing_was_written(self) -> None:
        """"Check current state" is sound for a publish and useless for a keyword lookup.

        There is no state it could have changed, and a caller that goes looking for one wastes a
        turn finding nothing instead of simply asking again.
        """
        client = Client(base_url="https://api.test", token=None, timeout=LONG_TIMEOUT_SECONDS)
        try:
            with respx.mock:
                respx.post("https://api.test/agent/research/seo/amazon-products").mock(
                    side_effect=httpx.ReadTimeout("timed out")
                )
                with pytest.raises(Exception) as excinfo:  # noqa: PT011 — NetworkError, checked below
                    client.request(
                        "POST", "/agent/research/seo/amazon-products", json={}, read_only=True
                    )
        finally:
            client.close()

        message = str(excinfo.value)
        assert "after 180s" in message
        assert "safe to repeat" in message
        assert "may have been applied" not in message

    @respx.mock
    def test_the_research_command_itself_carries_that_wording_through(
        self, env: str, recorded_timeouts: list[float]
    ) -> None:
        """End to end: the group's marking has to reach the client, not just sit on the spec."""
        respx.post(f"{env}/agent/research/seo/amazon-products").mock(
            side_effect=httpx.ReadTimeout("timed out")
        )

        result = runner.invoke(
            app,
            [
                "research-seo",
                "amazon-products",
                "-b",
                json.dumps({"keyword": "posture corrector"}),
            ],
        )

        assert result.exit_code != 0
        assert recorded_timeouts == [LONG_TIMEOUT_SECONDS]
        assert "safe to repeat" in result.output
        assert "check current state" not in result.output


class TestDescribeReportsTheBudget:
    def test_describe_tells_the_caller_how_long_to_allow(self, env: str) -> None:  # noqa: ARG002
        result = runner.invoke(app, ["describe", "ebay-listings", "create-drafts"])

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
    """A hand-written command that passes no budget still gets the shared default, never None."""
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

    assert seen == [DEFAULT_TIMEOUT_SECONDS]
