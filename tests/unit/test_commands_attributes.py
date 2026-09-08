from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "11111111-1111-4111-8111-111111111111"
PRODUCT_ID = "22222222-2222-4222-8222-222222222222"
CATEGORY = "66784"
JOB_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_schema_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/attributes/schema").mock(
        return_value=httpx.Response(
            200, json={"platform": "ebay", "category_external_id": CATEGORY, "attributes": []}
        )
    )
    result = runner.invoke(
        app,
        [
            "attributes",
            "schema",
            "-b",
            json.dumps({"store_id": STORE_ID, "category_external_id": CATEGORY}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"store_id": STORE_ID, "category_external_id": CATEGORY}


@respx.mock
def test_map_queues_a_job_for_the_products_it_is_given(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The caller states its products; the kind that picks the job's shape is the command's own."""
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/bulk-listing-jobs").mock(
        return_value=httpx.Response(
            202,
            json={"id": JOB_ID, "kind": "map_attributes", "status": "queued", "items": []},
        )
    )
    result = runner.invoke(
        app,
        [
            "attributes",
            "map",
            STORE_ID,
            "-b",
            json.dumps({"product_ids": [PRODUCT_ID]}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"product_ids": [PRODUCT_ID], "kind": "map_attributes"}
    # The queued job comes back with the exact command that reads it, so the id is never a dead end.
    assert "listings bulk-job" in result.stdout


@respx.mock
def test_map_waits_for_the_finished_job_when_asked(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A mapping run takes minutes, so --wait has to return the answer, not the queued row."""
    respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/bulk-listing-jobs").mock(
        return_value=httpx.Response(
            202, json={"id": JOB_ID, "kind": "map_attributes", "status": "queued", "items": []}
        )
    )
    poll = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/bulk-listing-jobs/{JOB_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": JOB_ID,
                "kind": "map_attributes",
                "status": "succeeded",
                "succeeded_count": 1,
                "failed_count": 0,
                "pending_count": 0,
                "items": [
                    {
                        "product_id": PRODUCT_ID,
                        "status": "succeeded",
                        "result": {"filled_attributes": ["Brand"]},
                    }
                ],
            },
        )
    )
    result = runner.invoke(
        app,
        ["--wait", "attributes", "map", STORE_ID, "-b", json.dumps({"product_ids": [PRODUCT_ID]})],
    )
    assert result.exit_code == 0, result.stderr
    assert poll.call_count >= 1
    assert "succeeded" in result.stdout


@respx.mock
def test_map_missing_required_field_is_rejected_client_side(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/bulk-listing-jobs").mock(
        return_value=httpx.Response(202, json={})
    )
    result = runner.invoke(
        app,
        ["attributes", "map", STORE_ID, "-b", json.dumps({"products": [PRODUCT_ID]})],
    )
    assert result.exit_code != 0
    assert route.call_count == 0  # never reaches the server with a known-bad body
