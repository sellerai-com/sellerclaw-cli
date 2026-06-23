from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Tests never make real outbound HTTP calls (transports are mocked/faked), but httpx clients are
# created with trust_env=True and read *_proxy from the environment at construction time. A developer
# with a SOCKS proxy exported (e.g. all_proxy=socks://...) would otherwise crash every httpx client
# build with "Unknown scheme for proxy URL" unless socksio is installed. Strip proxy vars up front.
_PROXY_ENV_VARS = (
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
)


def pytest_configure(config: pytest.Config) -> None:
    for var in _PROXY_ENV_VARS:
        os.environ.pop(var, None)


@pytest.fixture
def fake_api_url() -> str:
    return "https://api.test.sellerclaw.com"


@pytest.fixture
def fake_token() -> str:
    return "sca_" + "0" * 64


@pytest.fixture
def isolated_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect XDG_CONFIG_HOME to a tmp dir so config tests never touch the real ~/.config."""
    xdg = tmp_path / "xdg"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    # Also blank out auth-related env so tests start from a clean slate.
    for key in ("SELLERCLAW_TOKEN", "SELLERCLAW_API_URL"):
        monkeypatch.delenv(key, raising=False)
    yield xdg


@pytest.fixture(autouse=True)
def _ensure_no_real_home_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    """Safety-net: ensure tests never accidentally read the real $HOME for config."""
    # Individual tests that need the real HOME can unset this via their own monkeypatch.
    if "XDG_CONFIG_HOME" not in os.environ:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/nonexistent-sellerclaw-cli-test-sentinel")
