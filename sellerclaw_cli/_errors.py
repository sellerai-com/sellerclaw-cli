from __future__ import annotations


class CliError(Exception):
    """Base class for all CLI-raised errors that should be translated into the structured stderr contract."""

    exit_code: int = 1
    code: str = "error"

    def __init__(self, message: str, *, status: int | None = None, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


class UserInputError(CliError):
    exit_code = 1
    code = "user_error"


class ApiError(CliError):
    exit_code = 1
    code = "api_error"


class AuthError(CliError):
    """Not authenticated: no token, or one the API rejects (401).

    Kept apart from :class:`PermissionDeniedError` on purpose — signing in again fixes
    this one and only this one, so only this one carries the ``auth login`` hint.
    """

    exit_code = 3
    code = "auth_error"


class PermissionDeniedError(CliError):
    """Authenticated, but this caller may not do this (403).

    Re-authenticating changes nothing: the token is fine, the action is not the caller's
    to take (e.g. a sub-agent reaching for something only the supervisor owns). Grouped
    with the other "fix the call" errors, hence exit ``1``.
    """

    exit_code = 1
    code = "permission_error"


class ServerError(CliError):
    exit_code = 2
    code = "server_error"


class NetworkError(CliError):
    exit_code = 2
    code = "network_error"
