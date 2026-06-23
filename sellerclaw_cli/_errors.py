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
    exit_code = 3
    code = "auth_error"


class ServerError(CliError):
    exit_code = 2
    code = "server_error"


class NetworkError(CliError):
    exit_code = 2
    code = "network_error"
