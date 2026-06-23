from __future__ import annotations

import logging
import os
import re

_WORKSPACE_PATTERN = re.compile(r"(?:^|/)workspace-(?P<id>[^/]+)(?:/|$)")
_VALID_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_ID_LENGTH = 64

_logger = logging.getLogger(__name__)


def resolve_agent_id(cwd: str | None = None) -> str | None:
    """Extract an agent_id from a workspace-<id> path segment in the given cwd.

    Returns None when no segment matches or when the extracted id fails validation.
    Defaults cwd to os.getcwd() so callers can stay zero-arg in production.
    """
    path = cwd if cwd is not None else os.getcwd()
    matches = _WORKSPACE_PATTERN.findall(path)
    if not matches:
        return None
    candidate = matches[-1]
    if not _VALID_ID_PATTERN.match(candidate):
        return None
    if not 1 <= len(candidate) <= _MAX_ID_LENGTH:
        return None
    _logger.debug("agent_id_resolved id=%s", candidate)
    return candidate
