"""A client that offers a card's buttons to its model is not handed them (see ``mcp_buttons``).

Cursor lists ``visibility: ["app"]`` tools to the model, so its model pressed the studio's Upload
button itself (25.11.2026). These tests drive the stdio server in-process, through its middleware, as
each client names itself; the hosted server's HTTP path is covered in ``test_mcp_http``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp.types import Implementation

from sellerclaw_cli import mcp_buttons

# Importing the CLI app registers every command group the proxy tools read.
from sellerclaw_cli.cli import app  # noqa: F401
from sellerclaw_cli.mcp_server import build_server

pytestmark = pytest.mark.unit

CARD_BUTTONS = frozenset(
    {
        "sellerclaw_approval_decide",
        "sellerclaw_media_set_default",
        "sellerclaw_media_upload_image",
        "sellerclaw_media_generate",
    }
)


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
    isolated_config_home: Any,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


def _drive(action: Callable[[Client], Awaitable[Any]], *, client_name: str) -> Any:
    async def _run() -> Any:
        async with Client(
            build_server(), client_info=Implementation(name=client_name, version="1.0.0"), mode="legacy"
        ) as client:
            return await action(client)

    return asyncio.run(_run())


def _listed(client_name: str) -> set[str]:
    async def _names(client: Client) -> set[str]:
        return {tool.name for tool in (await client.list_tools()).tools}

    return _drive(_names, client_name=client_name)


@pytest.mark.parametrize(
    ("client_name", "buttons_listed"),
    [
        pytest.param("Cursor", False, id="cursor-as-it-names-itself"),
        pytest.param("cursor", False, id="cursor-in-lowercase"),
        pytest.param("claude-code", True, id="a-client-that-keeps-them-for-the-card"),
        pytest.param("cursorlike", True, id="a-name-that-only-starts-the-same"),
    ],
)
def test_the_cards_buttons_are_listed_only_to_clients_that_keep_them_from_the_model(
    client_name: str, buttons_listed: bool
) -> None:
    listed = _listed(client_name)

    assert (listed & CARD_BUTTONS == CARD_BUTTONS) is buttons_listed
    if not buttons_listed:
        assert listed.isdisjoint(CARD_BUTTONS)
    # Everything a model may call stays, whoever asks.
    assert {"sellerclaw_guide", "sellerclaw_read", "sellerclaw_write", "sellerclaw_media_studio"} <= listed


@pytest.mark.usefixtures("env_pointing_at_fake_api")
@respx.mock
def test_a_card_cursor_draws_can_still_press_its_button(fake_api_url: str) -> None:
    """Only the list leaves them out: a call by name is a card's press and still goes through."""
    models = {"tasks": [{"task": "video", "models": [{"id": "veo-3.1-lite", "is_default": True}]}]}
    pressed = respx.put(f"{fake_api_url}/agent/media/models/video/default").mock(
        return_value=httpx.Response(200, json=models)
    )
    respx.post(f"{fake_api_url}/agent/mcp/calls").mock(return_value=httpx.Response(204))

    result = _drive(
        lambda c: c.call_tool("sellerclaw_media_set_default", {"task": "video", "model": "veo-3.1-lite"}),
        client_name="Cursor",
    )

    assert result.is_error is False
    assert pressed.calls[0].request.content == b'{"model":"veo-3.1-lite"}'
    assert result.structured_content == {"models": models, "draft": {"task": "video", "model": "veo-3.1-lite"}}


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        pytest.param(
            {
                "tools": [
                    {"name": "shown", "_meta": {"ui": {"visibility": ["model", "app"]}}},
                    {"name": "button", "_meta": {"ui": {"visibility": ["app"]}}},
                    {"name": "plain"},
                ],
                "ttlMs": 5,
            },
            {
                "tools": [
                    {"name": "shown", "_meta": {"ui": {"visibility": ["model", "app"]}}},
                    {"name": "plain"},
                ],
                "ttlMs": 5,
            },
            id="a-result-handed-back-as-a-dict",
        ),
        pytest.param({"tools": None}, {"tools": None}, id="no-list-to-filter"),
        pytest.param(None, None, id="nothing-at-all"),
    ],
)
def test_only_the_buttons_are_taken_out_of_a_list(result: Any, expected: Any) -> None:
    assert mcp_buttons.without_buttons(result) == expected
