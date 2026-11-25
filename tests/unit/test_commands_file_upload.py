"""Commands that send a file rather than JSON.

``facebook-ads upload-image`` used to be declared as a body command, so the obvious call —
``upload-image -b @photo.png`` — read the picture as text and died on its first byte with a
``UnicodeDecodeError`` before any request was made. There was no way to upload an ad image at all.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.mcpserver.exceptions import ToolError
from typer.testing import CliRunner

from sellerclaw_cli import mcp_server
from sellerclaw_cli._command_group import REGISTRY, upload_payload
from sellerclaw_cli._errors import LocalFileUnreachableError, UserInputError
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


@respx.mock
def test_a_storefront_picture_goes_up_from_a_local_file(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    image: Path,
) -> None:
    """The shop's library takes a file as well as a link: a link back to our own storage is the one
    the server may not be able to fetch."""
    route = respx.post(f"{fake_api_url}/agent/sellercart/media").mock(
        return_value=httpx.Response(201, json={"url": "https://media.example/earbuds.png"})
    )

    result = runner.invoke(app, ["sellercart-media", "upload", str(image)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"]["url"] == "https://media.example/earbuds.png"
    request = route.calls[0].request
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert _PNG in request.content


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


@pytest.fixture
def through_the_hosted_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    """A call that came in over the hosted HTTP connector, which carries its own OAuth bearer."""
    monkeypatch.setattr(mcp_server, "_request_token", lambda: "owner-oauth-token")
    monkeypatch.setenv("SELLERCLAW_MCP_APPS_BASE", "https://staging-app.sellerclaw.ai/")


@pytest.mark.parametrize(
    ("group", "command"),
    [
        pytest.param("files", "upload", id="files-upload"),
        pytest.param("facebook-ads", "upload-image", id="ad-image"),
    ],
)
@pytest.mark.parametrize(
    "where",
    [
        pytest.param("owner-device", id="a-path-on-the-owners-computer"),
        pytest.param("server-disk", id="a-path-that-exists-on-the-server-is-not-read-either"),
    ],
)
@respx.mock(assert_all_called=False)
def test_the_hosted_connector_refuses_a_local_path_and_says_how_to_get_the_file_in(
    through_the_hosted_connector: None,  # noqa: ARG001
    env_pointing_at_fake_api: None,  # noqa: ARG001
    image: Path,
    group: str,
    command: str,
    where: str,
    respx_mock: respx.MockRouter,
) -> None:
    """Production, 2026-11-24: seven tries at a photo on the owner's Mac, each "No such file". The
    server cannot see the owner's device, and must never read its own disk in the owner's name."""
    local_path = "/Users/owner/Desktop/battery.jpg" if where == "owner-device" else str(image)
    anything = respx_mock.route().mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(LocalFileUnreachableError) as raised:
        run_command(group, command, positionals={"file": local_path})

    assert anything.call_count == 0
    assert raised.value.code == "local_file_unreachable"
    assert raised.value.message == (
        f"{group} {command} sends a file from the computer it runs on, and this SellerClaw connector "
        f"runs on SellerClaw's servers: it cannot open {local_path}, which is on the owner's device. "
        "To get the file in: where you can run commands on that computer, `files upload-link` hands "
        'out a one-time address — send the file to it with `curl -F "file=@<local path>" "<upload_url>"`; '
        "if it is online, `files from-url` with its link saves it; otherwise ask the owner to upload it "
        "on their SellerClaw Library page (https://staging-app.sellerclaw.ai/artifacts?upload=1), then "
        "`files list` finds it. Each answers a download_url, which a listing's images or any other "
        "command that takes a link to the file accepts."
    )


def test_the_hosted_refusal_reaches_the_assistant_under_its_own_code(
    through_the_hosted_connector: None,  # noqa: ARG001
) -> None:
    """The registered tool hands the refusal back whole, so the assistant reads the way forward."""
    with pytest.raises(ToolError) as raised:
        asyncio.run(
            mcp_server.build_server().call_tool(
                "sellerclaw_write",
                {"group": "files", "command": "upload", "positionals": {"file": "C:\\Users\\owner\\battery.jpg"}},
            )
        )

    text = str(raised.value)
    error = json.loads(text[text.index("{") :])["error"]
    assert error["code"] == "local_file_unreachable"
    assert "https://staging-app.sellerclaw.ai/artifacts?upload=1" in error["message"]


def test_upload_link_is_a_write_that_takes_how_many_links() -> None:
    schema = describe_command("files", "upload-link")

    assert schema["tool"] == "sellerclaw_write"
    assert schema["path"] == "/agent/files/upload-links"
    assert [field["name"] for field in schema["body_fields"]] == ["count"]
    assert "upload_file" not in schema


@pytest.mark.parametrize(
    ("body", "sent"),
    [
        pytest.param(None, None, id="one-link-by-default"),
        pytest.param({"count": 7}, {"count": 7}, id="one-per-photo"),
    ],
)
@respx.mock
def test_the_hosted_connector_hands_out_upload_links(
    through_the_hosted_connector: None,  # noqa: ARG001
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    body: dict[str, int] | None,
    sent: dict[str, int] | None,
) -> None:
    """Unlike `files upload`, nothing here touches a disk: the server hands out addresses."""
    answer = {"links": [{"upload_url": "https://api.sellerclaw.ai/agent/files/upload-links/t1"}]}
    route = respx.post(f"{fake_api_url}/agent/files/upload-links").mock(
        return_value=httpx.Response(201, json=answer)
    )

    result = run_command("files", "upload-link", body=body)

    assert result == answer
    request_body = route.calls[0].request.content
    assert (json.loads(request_body) if request_body else None) == sent


@pytest.mark.parametrize(
    ("args", "sent"),
    [
        pytest.param([], {}, id="one-link-by-default"),
        pytest.param(["--count", "3"], {"count": 3}, id="a-batch"),
    ],
)
@respx.mock
def test_cli_upload_link_posts_the_count(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    args: list[str],
    sent: dict[str, int],
) -> None:
    route = respx.post(f"{fake_api_url}/agent/files/upload-links").mock(
        return_value=httpx.Response(201, json={"links": []})
    )

    result = runner.invoke(app, ["files", "upload-link", *args])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls[0].request.content) == sent
