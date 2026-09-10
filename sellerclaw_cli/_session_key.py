"""Which OpenClaw session the calling run is in — passed on so the server does not have to guess.

An agent runs the CLI from a shell that OpenClaw opens for its ``exec`` tool. The shell knows the
agent (``workspace-<id>`` in the cwd, see :mod:`._agent_id`) but nothing about the *run* — and the
run is what ties a task to the conversation it was asked for in, or an executor's task to the one
run that is doing it. SellerClaw's own channel plugin closes that gap by putting the session key
into the shell's environment; this module reads it back and the client sends it as
``X-Session-Key``.

Absent or malformed means "unknown", never an error: the server has a fallback for every use
of the header, and a CLI run from a terminal has no session to name.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

ENV_SESSION_KEY = "SELLERCLAW_SESSION_KEY"

#: The shape OpenClaw gives every session key: ``agent:<agent id>:<the rest>``. Anything else is
#: not a session key and is dropped rather than sent as one.
_SESSION_KEY_PATTERN = re.compile(r"^agent:(?P<agent_id>[A-Za-z0-9_-]+):\S+$")
_MAX_SESSION_KEY_LENGTH = 256


def resolve_session_key(environ: Mapping[str, str] | None = None) -> str | None:
    """The session key the environment names, or ``None`` when it names none worth sending."""
    source = os.environ if environ is None else environ
    raw = (source.get(ENV_SESSION_KEY) or "").strip()
    if not raw or len(raw) > _MAX_SESSION_KEY_LENGTH:
        return None
    if not _SESSION_KEY_PATTERN.match(raw):
        return None
    return raw


def session_key_agent_id(environ: Mapping[str, str] | None = None) -> str | None:
    """The agent the session key names, or ``None`` when the environment names no valid key.

    A session key always opens with the agent it belongs to, so it answers "who is calling" for
    any shell the runtime opened — including one that has since walked out of the agent's own
    workspace. See :mod:`._agent_id`, which uses it exactly for that.
    """
    key = resolve_session_key(environ)
    if key is None:
        return None
    match = _SESSION_KEY_PATTERN.match(key)
    return None if match is None else match.group("agent_id")
