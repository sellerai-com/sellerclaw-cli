from __future__ import annotations

import time
from dataclasses import dataclass

from sellerclaw_cli._client import Client
from sellerclaw_cli._errors import AuthError

_DEVICE_CODE_PATH = "/agent/auth/device/code"
_DEVICE_TOKEN_PATH = "/agent/auth/device/token"
_PASSWORD_TOKEN_PATH = "/agent/auth/token"
_SLOW_DOWN_STEP_SECONDS = 5


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
    """Poll /agent/auth/device/token until granted or expired. Returns the agent_token (sca_...)."""
    current_interval = interval
    started = time.monotonic()

    with Client(base_url=api_url, token=None) as client:
        while True:
            if time.monotonic() - started >= expires_in:
                raise AuthError("Device code expired before authorization was granted.")

            body = client.request("POST", _DEVICE_TOKEN_PATH, json={"device_code": device_code})

            token = body.get("agent_token") if isinstance(body, dict) else None
            if isinstance(token, str) and token:
                return token

            err = body.get("error") if isinstance(body, dict) else None
            if err is None or err == "authorization_pending":
                pass
            elif err == "slow_down":
                current_interval += _SLOW_DOWN_STEP_SECONDS
            else:
                raise AuthError(f"Device authorization failed: {err}")

            time.sleep(current_interval)


def password_login(api_url: str, email: str, password: str) -> str:
    """POST /agent/auth/token with email+password. Returns the agent_token."""
    with Client(base_url=api_url, token=None) as client:
        body = client.request("POST", _PASSWORD_TOKEN_PATH, json={"email": email, "password": password})

    token = body.get("agent_token") if isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        raise AuthError("Login response did not include an agent_token.")
    return token
