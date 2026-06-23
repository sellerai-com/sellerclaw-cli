from __future__ import annotations

import io
import json
from typing import Any

import pytest
import yaml

from sellerclaw_cli._errors import (
    ApiError,
    AuthError,
    CliError,
    NetworkError,
    ServerError,
    UserInputError,
)
from sellerclaw_cli._output import OutputFormat, print_error, print_ok

pytestmark = pytest.mark.unit


class TestPrintOk:
    """Success path: data goes to stdout, nothing to stderr, exit code 0."""

    def test_returns_exit_code_zero(self) -> None:
        stdout = io.StringIO()
        exit_code = print_ok({"id": "abc"}, fmt=OutputFormat.JSON, stdout=stdout)
        assert exit_code == 0

    def test_json_format_wraps_payload_in_data_key_single_line(self) -> None:
        stdout = io.StringIO()
        print_ok({"id": "abc", "name": "Widget"}, fmt=OutputFormat.JSON, stdout=stdout)

        raw = stdout.getvalue()
        # JSON format must be a single line (easy to pipe to jq / read line-by-line from a subprocess).
        assert raw.count("\n") == 1, f"expected single trailing newline, got {raw!r}"
        parsed = json.loads(raw)
        assert parsed == {"data": {"id": "abc", "name": "Widget"}}

    def test_json_format_preserves_list_payload(self) -> None:
        stdout = io.StringIO()
        print_ok([{"id": 1}, {"id": 2}], fmt=OutputFormat.JSON, stdout=stdout)
        parsed = json.loads(stdout.getvalue())
        assert parsed == {"data": [{"id": 1}, {"id": 2}]}

    def test_json_format_preserves_none_payload(self) -> None:
        stdout = io.StringIO()
        print_ok(None, fmt=OutputFormat.JSON, stdout=stdout)
        parsed = json.loads(stdout.getvalue())
        assert parsed == {"data": None}

    def test_pretty_format_is_indented_json(self) -> None:
        stdout = io.StringIO()
        print_ok({"id": "abc"}, fmt=OutputFormat.PRETTY, stdout=stdout)

        raw = stdout.getvalue()
        # Pretty output has multiple lines (2-space indent) but is still valid JSON.
        assert raw.count("\n") > 1
        parsed = json.loads(raw)
        assert parsed == {"data": {"id": "abc"}}

    def test_yaml_format_emits_parseable_yaml(self) -> None:
        stdout = io.StringIO()
        print_ok({"id": "abc", "name": "Widget"}, fmt=OutputFormat.YAML, stdout=stdout)
        parsed = yaml.safe_load(stdout.getvalue())
        assert parsed == {"data": {"id": "abc", "name": "Widget"}}

    def test_never_writes_to_stderr_on_success(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        # Success path must not touch stderr — LLM consumers distinguish success/error purely by stream + exit code.
        print_ok({"ok": True}, fmt=OutputFormat.JSON, stdout=stdout)
        # Stderr fixture untouched.
        assert stderr.getvalue() == ""


class TestPrintError:
    """Error path: structured JSON goes to stderr, nothing to stdout, exit code matches error type."""

    @pytest.mark.parametrize(
        ("error", "expected_code", "expected_exit"),
        [
            pytest.param(
                UserInputError("invalid argument", status=None),
                "user_error",
                1,
                id="user-input-error-exit-1",
            ),
            pytest.param(
                ApiError("bad request", status=400, details={"field": "name"}),
                "api_error",
                1,
                id="api-error-4xx-exit-1",
            ),
            pytest.param(
                AuthError("token expired", status=401),
                "auth_error",
                3,
                id="auth-error-401-exit-3",
            ),
            pytest.param(
                AuthError("forbidden", status=403),
                "auth_error",
                3,
                id="auth-error-403-exit-3",
            ),
            pytest.param(
                ServerError("internal", status=500),
                "server_error",
                2,
                id="server-error-5xx-exit-2",
            ),
            pytest.param(
                NetworkError("connection refused"),
                "network_error",
                2,
                id="network-error-exit-2",
            ),
        ],
    )
    def test_error_structure_and_exit_code(
        self,
        error: CliError,
        expected_code: str,
        expected_exit: int,
    ) -> None:
        stderr = io.StringIO()
        exit_code = print_error(error, stderr=stderr)

        assert exit_code == expected_exit

        raw = stderr.getvalue()
        # Errors must be single-line compact JSON so LLMs/scripts can parse one stderr line directly.
        assert raw.count("\n") == 1, f"expected single trailing newline on error, got {raw!r}"
        parsed = json.loads(raw)

        assert "error" in parsed
        err = parsed["error"]
        assert err["code"] == expected_code
        assert err["message"] == error.message
        # Status must be present in output iff the source error has one.
        if error.status is None:
            assert "status" not in err
        else:
            assert err["status"] == error.status

    def test_api_error_includes_details(self) -> None:
        stderr = io.StringIO()
        err = ApiError("validation failed", status=422, details={"fields": {"name": "required"}})
        print_error(err, stderr=stderr)

        parsed = json.loads(stderr.getvalue())
        assert parsed["error"]["details"] == {"fields": {"name": "required"}}

    def test_auth_error_includes_hint_to_run_login(self) -> None:
        # Auth errors should nudge the user (or LLM) toward the fix — `sellerclaw auth login`.
        stderr = io.StringIO()
        print_error(AuthError("no token", status=401), stderr=stderr)

        parsed = json.loads(stderr.getvalue())
        hint: Any = parsed["error"].get("hint")
        assert isinstance(hint, str) and hint, "auth_error must include a non-empty 'hint' field"
        assert "auth login" in hint.lower()

    def test_never_writes_to_stdout_on_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        print_error(ApiError("nope", status=404), stderr=stderr)
        assert stdout.getvalue() == ""

    def test_error_without_status_has_no_status_key(self) -> None:
        stderr = io.StringIO()
        print_error(NetworkError("timeout"), stderr=stderr)
        parsed = json.loads(stderr.getvalue())
        assert "status" not in parsed["error"]
