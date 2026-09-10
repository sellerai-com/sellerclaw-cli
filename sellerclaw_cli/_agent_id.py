"""Which agent this process is calling as.

Two answers, in order. The workspace in the path is the first: OpenClaw gives every agent a
``workspace-<id>`` directory and opens its shells there, so the cwd names the agent for free.
It stops naming it the moment a command steps outside — ``cd /tmp && sellerclaw …`` to reach a
file it just wrote is enough — and an unnamed call is read by the cloud as the supervisor, which
refuses anything only the assignee may do. So the session key the runtime puts in the shell's
environment is the second answer: it opens with the same agent id and survives any ``cd``.

``None`` means neither names one — a CLI run from a person's terminal, where the cloud's own
default is the right reading.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping

from sellerclaw_cli._session_key import session_key_agent_id

_WORKSPACE_PATTERN = re.compile(r"(?:^|/)workspace-(?P<id>[^/]+)(?:/|$)")
_VALID_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_ID_LENGTH = 64

_logger = logging.getLogger(__name__)


def resolve_agent_id(
    cwd: str | None = None, environ: Mapping[str, str] | None = None
) -> str | None:
    """Extract an agent_id from a workspace-<id> path segment, else from the session key.

    Returns None when neither names one or when the extracted id fails validation. Defaults cwd
    to os.getcwd() and environ to os.environ so callers can stay zero-arg in production.
    """
    path = cwd if cwd is not None else os.getcwd()
    matches = _WORKSPACE_PATTERN.findall(path)
    # A path that names a workspace answers for itself, even when the name it holds turns out to
    # be unusable: falling through to the session there would answer with an agent the path did
    # not name.
    candidate = matches[-1] if matches else session_key_agent_id(environ)
    if candidate is None:
        return None
    if not _VALID_ID_PATTERN.match(candidate):
        return None
    if not 1 <= len(candidate) <= _MAX_ID_LENGTH:
        return None
    _logger.debug("agent_id_resolved id=%s", candidate)
    return candidate
