from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

DEFAULT_API_URL = "https://api.sellerclaw.ai"
ENV_TOKEN = "SELLERCLAW_TOKEN"
ENV_API_URL = "SELLERCLAW_API_URL"
ENV_XDG_CONFIG_HOME = "XDG_CONFIG_HOME"

_CONFIG_DIR = "sellerclaw"
_CONFIG_FILE = "config.toml"


@dataclass(frozen=True)
class Config:
    api_url: str
    token: str | None


def config_path() -> Path:
    """Return the absolute path to the config.toml file, respecting XDG_CONFIG_HOME."""
    xdg = os.environ.get(ENV_XDG_CONFIG_HOME)
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / _CONFIG_DIR / _CONFIG_FILE


def load() -> Config:
    """Resolve config from env > config file > defaults."""
    file_values = _read_file()
    api_url = os.environ.get(ENV_API_URL) or file_values.get("api_url") or DEFAULT_API_URL
    token = os.environ.get(ENV_TOKEN) or file_values.get("token") or None
    return Config(api_url=api_url, token=token)


def save_token(token: str) -> None:
    """Persist the token to config.toml with 0600 permissions. Preserves any existing api_url."""
    values = _read_file()
    values["token"] = token
    _write_file(values)


def clear_token() -> None:
    """Remove the token key from config.toml. No-op if file or key is missing."""
    path = config_path()
    if not path.exists():
        return
    values = _read_file()
    if "token" not in values:
        return
    values.pop("token", None)
    _write_file(values)


def _read_file() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            parsed = tomllib.load(fh)
    except tomllib.TOMLDecodeError:
        return {}
    return {k: v for k, v in parsed.items() if isinstance(v, str)}


def _write_file(values: dict[str, str]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(values, fh)
    # chmod after write — trade-off: tiny window where the file is world-readable on permissive umasks,
    # but avoids platform-specific os.open(..., O_CREAT, 0o600) dance. Acceptable for a CLI.
    try:
        path.chmod(0o600)
    except OSError:
        # Non-POSIX filesystems may not support chmod; silently skip.
        pass
