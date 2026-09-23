from __future__ import annotations

import time
from dataclasses import dataclass

from sellerclaw_cli._client import Client
from sellerclaw_cli._errors import AuthError, NetworkError

_DEVICE_CODE_PATH = "/agent/auth/device/code"
_DEVICE_TOKEN_PATH = "/agent/auth/device/token"
_PASSWORD_TOKEN_PATH = "/agent/auth/token"
_SLOW_DOWN_STEP_SECONDS = 5

#: Error codes the server may answer a poll with, in the caller's words. Anything not listed keeps
#: the raw code, which is all we can honestly say about a code we do not know.
_POLL_ERROR_MESSAGES = {
    # Almost always a code that ran out while nobody approved it — the raw "invalid_device_code"
    # reads like a bug in the CLI and leaves the person with nothing to do about it.
    "invalid_device_code": (
        "This login code is no longer valid — it may have expired. Run the login again to get a "
        "new one."
    ),
}


@dataclass(frozen=True)
class DeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


def request_device_code(api_url: str) -> DeviceCode:
    """POST /agent/auth/device/code. Returns parsed DeviceCode."""
    with Client(base_url=api_url, token=None) as client:
        body = client.request("POST", _DEVICE_CODE_PATH)
    return DeviceCode(
        device_code=body["device_code"],
        user_code=body["user_code"],
        verification_uri=body["verification_uri"],
        expires_in=int(body["expires_in"]),
        interval=int(body["interval"]),
    )


def poll_device_token(
    api_url: str,
    device_code: str,
    *,
    interval: int,
    expires_in: int,
) -> str:
    """Poll /agent/auth/device/token until granted or expired. Returns the agent_token (sca_...).

    A dropped connection is not a failed login. By the time this runs the person is already looking
    at the code and approving it in a browser; one SSL EOF or reset in the minutes that takes used
    to abort the whole thing with "unexpected CLI error: NetworkError" and throw the code away. So a
    transport failure is treated like any other poll that did not answer yet — wait the polling
    interval and ask again — and only the code's own expiry ends the wait. Errors the *server*
    sends (authorization_pending, slow_down, access_denied, …) are untouched: those are answers.
    """
    current_interval = interval
    started = time.monotonic()
    unreachable = False

    with Client(base_url=api_url, token=None) as client:
        while True:
            if time.monotonic() - started >= expires_in:
                raise AuthError(_expired_message(unreachable=unreachable))

            try:
                body = client.request("POST", _DEVICE_TOKEN_PATH, json={"device_code": device_code})
            except NetworkError:
                unreachable = True
                time.sleep(current_interval)
                continue
            unreachable = False

            token = body.get("agent_token") if isinstance(body, dict) else None
            if isinstance(token, str) and token:
                return token

            err = body.get("error") if isinstance(body, dict) else None
            if err is None or err == "authorization_pending":
                pass
            elif err == "slow_down":
                current_interval += _SLOW_DOWN_STEP_SECONDS
            else:
                raise AuthError(
                    _POLL_ERROR_MESSAGES.get(err, f"Device authorization failed: {err}")
                )

            time.sleep(current_interval)


def _expired_message(*, unreachable: bool) -> str:
    """Why the wait ended. Telling someone they did not approve in time is wrong when the CLI never
    managed to ask — so a wait that ran out mid-outage says which of the two it was."""
    if not unreachable:
        return "Device code expired before authorization was granted."
    return (
        "Device code expired before authorization was granted, and the last attempts could not "
        "reach the API — check the connection and run the login again."
    )


def password_login(api_url: str, email: str, password: str) -> str:
    """POST /agent/auth/token with email+password. Returns the agent_token."""
    with Client(base_url=api_url, token=None) as client:
        body = client.request("POST", _PASSWORD_TOKEN_PATH, json={"email": email, "password": password})

    token = body.get("agent_token") if isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        raise AuthError("Login response did not include an agent_token.")
    return token
