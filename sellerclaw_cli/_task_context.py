"""Per-agent 'active task' pointer + short-id prefix expansion.

An agent works one task at a time, but each ``sellerclaw`` call is a separate process, so the
task id has to be repeated on every follow-up (start → add-note → complete). Copying a 36-char
UUID by hand across calls is error-prone — a single wrong character yields a 404 on the wrong id.

Two ergonomics helpers live here:
  * an **active-task pointer** — ``start`` records the task per agent, so later commands can omit
    the id and act on the active task;
  * **prefix expansion** — a short id prefix is expanded against the caller's task list.

State is keyed by the caller's agent id (derived from the ``workspace-<id>`` cwd) so concurrent
subagents on one machine never clobber each other's active task.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from sellerclaw_cli._config import config_path

_STATE_FILE = "state.toml"
_ACTIVE_TABLE = "active"
_DEFAULT_AGENT_KEY = "_default"


def _state_path() -> Path:
    """State file lives next to config.toml (same XDG-aware directory)."""
    return config_path().parent / _STATE_FILE


def _agent_key(agent_id: str | None) -> str:
    return agent_id or _DEFAULT_AGENT_KEY


def _read_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _write_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(state, fh)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def get_active(slot: str, agent_id: str | None) -> str | None:
    """Return the active task id saved for ``slot`` + agent, or None."""
    table = _read_state().get(_ACTIVE_TABLE)
    if not isinstance(table, dict):
        return None
    by_agent = table.get(slot)
    if not isinstance(by_agent, dict):
        return None
    value = by_agent.get(_agent_key(agent_id))
    return value if isinstance(value, str) and value else None


def set_active(slot: str, agent_id: str | None, task_id: str) -> None:
    """Record ``task_id`` as the active task for ``slot`` + agent."""
    state = _read_state()
    table = state.setdefault(_ACTIVE_TABLE, {})
    if not isinstance(table, dict):
        table = {}
        state[_ACTIVE_TABLE] = table
    by_agent = table.setdefault(slot, {})
    if not isinstance(by_agent, dict):
        by_agent = {}
        table[slot] = by_agent
    by_agent[_agent_key(agent_id)] = task_id
    _write_state(state)


def collect_ids(data: Any) -> list[str]:
    """Best-effort: pull task ids out of a list-response body.

    Handles a bare JSON array of task objects and the common ``{"tasks"|"items"|"results": [...]}``
    envelopes, reading each element's ``id``. Tolerant by design — an unrecognised shape yields no
    ids and prefix expansion simply falls through to the server.
    """
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = None
        for key in ("tasks", "items", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                rows = value
                break
        if rows is None:
            rows = next(
                (v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)),
                [],
            )
    else:
        return []
    return [str(row["id"]) for row in rows if isinstance(row, dict) and row.get("id")]
