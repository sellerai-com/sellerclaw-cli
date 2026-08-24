"""Commands that send a file rather than JSON.

``facebook-ads upload-image`` used to be declared as a body command, so the obvious call —
``upload-image -b @photo.png`` — read the picture as text and died on its first byte with a
``UnicodeDecodeError`` before any request was made. There was no way to upload an ad image at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli._command_group import REGISTRY, upload_payload
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.cli import app
from sellerclaw_cli.mcp_server import describe_command, run_command

pytestmark = pytest.mark.unit

runner = CliRunner()

# A one-pixel PNG: real bytes, none of which survive being read as UTF-8 text.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415408d763f8cfc0000003010100b5d3f7e50000000049454e44ae426082"
)


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@pytest.fixture
def image(tmp_path: Path) -> Path:
    target = tmp_path / "earbuds.png"
    target.write_bytes(_PNG)
    return target


@respx.mock
def test_upload_image_posts_the_file_itself(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    image: Path,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/ads/facebook/images").mock(
        return_value=httpx.Response(200, json={"images": {"earbuds.png": {"hash": "h1"}}})
    )

    result = runner.invoke(app, ["facebook-ads", "upload-image", str(image)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"]["images"]["earbuds.png"]["hash"] == "h1"
    request = route.calls[0].request
    assert request.headers["content-type"].startswith("multipart/form-data")
    # The picture's own bytes travelled, not a description of them.
    assert _PNG in request.content
    assert b"earbuds.png" in request.content


@respx.mock
def test_upload_image_can_rename_the_stored_file(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    image: Path,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/ads/facebook/images").mock(
        return_value=httpx.Response(200, json={"hash": "h2"})
    )

    result = runner.invoke(
        app, ["facebook-ads", "upload-image", str(image), "--filename", "square-1080.png"]
    )

    assert result.exit_code == 0, result.output
    request = route.calls[0].request
    assert b"square-1080.png" in request.content
    # The server names the stored file from the query too, so both spellings agree.
    assert request.url.params["filename"] == "square-1080.png"


def test_upload_image_no_longer_takes_a_json_body(image: Path) -> None:
    """The old spelling has to fail as a usage error, not as a crash on the image's first byte."""
    result = runner.invoke(app, ["facebook-ads", "upload-image", "-b", f"@{image}"])

    assert result.exit_code != 0
    assert "UnicodeDecodeError" not in result.output


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        pytest.param("earbuds.png", "image/png", id="png"),
        pytest.param("earbuds.jpg", "image/jpeg", id="jpeg"),
        pytest.param("earbuds.bin", "application/octet-stream", id="unknown-extension"),
    ],
)
def test_upload_payload_names_the_type_from_the_file(
    tmp_path: Path, filename: str, expected_type: str
) -> None:
    target = tmp_path / filename
    target.write_bytes(_PNG)

    assert upload_payload(target) == {"file": (filename, _PNG, expected_type)}


def test_upload_payload_refuses_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(UserInputError, match="failed to read file"):
        upload_payload(tmp_path / "nope.png")


def test_upload_payload_refuses_an_empty_file(tmp_path: Path) -> None:
    """Zero bytes is not a picture, and Meta stores it as a broken image rather than refusing."""
    target = tmp_path / "empty.png"
    target.write_bytes(b"")

    with pytest.raises(UserInputError, match="is empty"):
        upload_payload(target)


def test_describe_announces_the_file_argument() -> None:
    """An upload takes its file as an argument, and it is not a path placeholder — so a caller
    reading only ``positionals`` would think the command takes nothing at all."""
    schema = describe_command("facebook-ads", "upload-image")

    assert schema["upload_file"] is True
    assert schema["takes_body"] is False


@respx.mock
def test_the_mcp_tool_uploads_from_a_local_path(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    image: Path,
) -> None:
    assert REGISTRY, "the CLI app must be imported for the MCP registry to be populated"
    route = respx.post(f"{fake_api_url}/agent/ads/facebook/images").mock(
        return_value=httpx.Response(200, json={"hash": "h3"})
    )

    result = run_command("facebook-ads", "upload-image", positionals={"file": str(image)})

    assert result == {"hash": "h3"}
    assert _PNG in route.calls[0].request.content


def test_the_mcp_tool_says_which_argument_carries_the_file() -> None:
    with pytest.raises(UserInputError, match="local path"):
        run_command("facebook-ads", "upload-image")
