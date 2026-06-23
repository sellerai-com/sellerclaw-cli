from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from sellerclaw_cli import _config
from sellerclaw_cli._config import (
    DEFAULT_API_URL,
    ENV_API_URL,
    ENV_TOKEN,
    Config,
    clear_token,
    config_path,
    load,
    save_token,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestConfigPath:
    def test_path_under_xdg_config_home(self, isolated_config_home: Path) -> None:
        path = config_path()
        assert path == isolated_config_home / "sellerclaw" / "config.toml"

    def test_path_falls_back_to_home_when_xdg_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", str(fake_home))

        path = config_path()
        assert path == fake_home / ".config" / "sellerclaw" / "config.toml"


# ---------------------------------------------------------------------------
# load() precedence: env > config file > defaults
# ---------------------------------------------------------------------------


class TestLoad:
    def test_returns_defaults_when_no_env_no_file(
        self, isolated_config_home: Path  # noqa: ARG002
    ) -> None:
        cfg = load()
        assert cfg == Config(api_url=DEFAULT_API_URL, token=None)

    def test_env_token_beats_defaults(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
        fake_token: str,
    ) -> None:
        monkeypatch.setenv(ENV_TOKEN, fake_token)
        cfg = load()
        assert cfg.token == fake_token
        assert cfg.api_url == DEFAULT_API_URL

    def test_env_api_url_beats_defaults(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
        fake_api_url: str,
    ) -> None:
        monkeypatch.setenv(ENV_API_URL, fake_api_url)
        cfg = load()
        assert cfg.api_url == fake_api_url

    def test_config_file_values_used_when_env_absent(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        fake_token: str,
        fake_api_url: str,
    ) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'api_url = "{fake_api_url}"\ntoken = "{fake_token}"\n')

        cfg = load()
        assert cfg.api_url == fake_api_url
        assert cfg.token == fake_token

    def test_env_token_overrides_config_file_token(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('api_url = "https://from-file.test"\ntoken = "sca_from_file"\n')

        monkeypatch.setenv(ENV_TOKEN, "sca_from_env")
        cfg = load()
        assert cfg.token == "sca_from_env"
        # api_url still comes from file since env didn't override it
        assert cfg.api_url == "https://from-file.test"

    def test_env_api_url_overrides_config_file_api_url(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('api_url = "https://from-file.test"\ntoken = "sca_from_file"\n')

        monkeypatch.setenv(ENV_API_URL, "https://from-env.test")
        cfg = load()
        assert cfg.api_url == "https://from-env.test"
        assert cfg.token == "sca_from_file"


# ---------------------------------------------------------------------------
# save_token() — create parent dirs, preserve api_url, chmod 0600
# ---------------------------------------------------------------------------


class TestSaveToken:
    def test_creates_config_file_and_writes_token(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        fake_token: str,
    ) -> None:
        save_token(fake_token)

        path = config_path()
        assert path.exists()
        content = path.read_text()
        assert fake_token in content

        # Verify roundtrip via load()
        cfg = load()
        assert cfg.token == fake_token

    def test_creates_parent_directory_if_missing(
        self,
        isolated_config_home: Path,
        fake_token: str,
    ) -> None:
        target_dir = isolated_config_home / "sellerclaw"
        assert not target_dir.exists()

        save_token(fake_token)
        assert target_dir.is_dir()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
    def test_config_file_has_mode_0600(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        fake_token: str,
    ) -> None:
        save_token(fake_token)
        mode = stat.S_IMODE(config_path().stat().st_mode)
        assert mode == 0o600, f"expected mode 0600, got {oct(mode)}"

    def test_preserves_existing_api_url(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        fake_api_url: str,
        fake_token: str,
    ) -> None:
        # Seed config with a non-default api_url; save_token must not clobber it.
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'api_url = "{fake_api_url}"\n')

        save_token(fake_token)

        cfg = load()
        assert cfg.api_url == fake_api_url
        assert cfg.token == fake_token

    def test_overwrites_previous_token(
        self,
        isolated_config_home: Path,  # noqa: ARG002
    ) -> None:
        save_token("sca_one")
        save_token("sca_two")
        assert load().token == "sca_two"


# ---------------------------------------------------------------------------
# clear_token()
# ---------------------------------------------------------------------------


class TestClearToken:
    def test_removes_token_but_keeps_api_url(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        fake_api_url: str,
        fake_token: str,
    ) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'api_url = "{fake_api_url}"\ntoken = "{fake_token}"\n')

        clear_token()

        cfg = load()
        assert cfg.token is None
        assert cfg.api_url == fake_api_url

    def test_noop_when_config_missing(
        self,
        isolated_config_home: Path,  # noqa: ARG002
    ) -> None:
        # Should not raise even if config file doesn't exist.
        clear_token()
        assert load().token is None

    def test_noop_when_token_key_missing(
        self,
        isolated_config_home: Path,  # noqa: ARG002
        fake_api_url: str,
    ) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'api_url = "{fake_api_url}"\n')

        clear_token()
        cfg = load()
        assert cfg.token is None
        assert cfg.api_url == fake_api_url


# ---------------------------------------------------------------------------
# Module sanity — make sure constants aren't accidentally renamed
# ---------------------------------------------------------------------------


def test_module_exposes_expected_constants() -> None:
    assert _config.ENV_TOKEN == "SELLERCLAW_TOKEN"
    assert _config.ENV_API_URL == "SELLERCLAW_API_URL"
    assert _config.DEFAULT_API_URL.startswith("https://")
