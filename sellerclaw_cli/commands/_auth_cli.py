from __future__ import annotations

import getpass
import sys

import typer

from sellerclaw_cli import _auth, _config
from sellerclaw_cli._errors import AuthError, UserInputError
from sellerclaw_cli._output import OutputFormat, print_ok
from sellerclaw_cli._runtime import emit_error

app = typer.Typer(
    name="auth",
    help="Manage authentication for the SellerClaw Agent API.",
    no_args_is_help=True,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name="auth")


@app.command("login", help="Authenticate via device flow (default) or email/password (--password).")
def login(
    ctx: typer.Context,
    password: bool = typer.Option(  # noqa: B008
        False,
        "--password",
        help="Use password login instead of device flow. Reads email and password from stdin.",
    ),
) -> None:
    cfg = _config.load()
    try:
        if password:
            token = _password_login_interactive(cfg.api_url)
        else:
            token = _device_login(cfg.api_url)
    except (AuthError, UserInputError) as err:
        emit_error(err)
        return

    _config.save_token(token)
    fmt = ctx.obj.get("format", OutputFormat.JSON) if ctx.obj else OutputFormat.JSON
    print_ok(
        {
            "authenticated": True,
            "api_url": cfg.api_url,
            "config_path": str(_config.config_path()),
        },
        fmt=fmt,
    )


@app.command("logout", help="Remove the stored token from the config file.")
def logout(ctx: typer.Context) -> None:
    _config.clear_token()
    fmt = ctx.obj.get("format", OutputFormat.JSON) if ctx.obj else OutputFormat.JSON
    print_ok(
        {"authenticated": False, "config_path": str(_config.config_path())},
        fmt=fmt,
    )


@app.command("whoami", help="Show whether a token is configured and which API URL the CLI will use.")
def whoami(ctx: typer.Context) -> None:
    cfg = _config.load()
    fmt = ctx.obj.get("format", OutputFormat.JSON) if ctx.obj else OutputFormat.JSON
    print_ok(
        {
            "authenticated": cfg.token is not None,
            "api_url": cfg.api_url,
            "config_path": str(_config.config_path()),
        },
        fmt=fmt,
    )


def _device_login(api_url: str) -> str:
    device = _auth.request_device_code(api_url)
    # Human-facing prompts go to stderr so stdout stays clean for JSON consumers.
    print(
        f"Open {device.verification_uri}\n"
        f"Enter the code: {device.user_code}\n"
        f"(waiting up to {device.expires_in}s, polling every {device.interval}s...)",
        file=sys.stderr,
    )
    return _auth.poll_device_token(
        api_url,
        device.device_code,
        interval=device.interval,
        expires_in=device.expires_in,
    )


def _password_login_interactive(api_url: str) -> str:
    if sys.stdin.isatty():
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")
    else:
        # Non-tty (piped): expect two lines — email, then password.
        lines = sys.stdin.read().splitlines()
        if len(lines) < 2:
            raise UserInputError(
                "--password expects 'email\\npassword' on stdin when stdin is not a tty"
            )
        email = lines[0].strip()
        password = lines[1]
    if not email or not password:
        raise UserInputError("email and password must both be non-empty")
    return _auth.password_login(api_url, email, password)
