"""Tests for transcript content API endpoints."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from yt_transcript.api.app import app

    return TestClient(app)


def _mock_session():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.refresh = AsyncMock()
    return session


def _mock_item():
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        source_type="youtube",
        source_id="abc123",
        url="https://youtu.be/abc123",
        title="Example title",
        channel_name="Example channel",
        language="en",
        retrieval_method="captions",
        transcript_status="done",
        transcript_markdown_path="/tmp/example.md",
        transcript_text="First second third",
        quality_flags=["used_auto_captions"],
        segments=[
            SimpleNamespace(idx=2, start_seconds=12.0, end_seconds=18.25, text="third", tokens_estimate=1),
            SimpleNamespace(idx=0, start_seconds=0.0, end_seconds=4.0, text="first", tokens_estimate=1),
            SimpleNamespace(idx=1, start_seconds=4.0, end_seconds=12.0, text="second", tokens_estimate=1),
        ],
    )


@pytest.mark.parametrize(
    ("path_template", "patch_target", "path_arg_name"),
    [
        ("/v1/transcripts/{item_id}/content", "yt_transcript.api.app.find_by_id", "item_id"),
        ("/v1/transcripts/by-source/{video_id}/content", "yt_transcript.api.app.find_by_source", "video_id"),
    ],
)
def test_content_endpoints_return_transcript_text_and_ordered_segments(
    client, path_template, patch_target, path_arg_name
):
    mock_session = _mock_session()
    item = _mock_item()
    path_value = item.id if path_arg_name == "item_id" else item.source_id

    with patch("yt_transcript.api.app.async_session", return_value=mock_session):
        with patch(patch_target, return_value=item):
            response = client.get(path_template.format(**{path_arg_name: path_value}))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(item.id)
    assert data["transcript_text"] == item.transcript_text
    assert [segment["idx"] for segment in data["segments"]] == [0, 1, 2]
    assert [segment["text"] for segment in data["segments"]] == ["first", "second", "third"]
    assert data["segment_count"] == 3
    assert data["quality_flags"] == ["used_auto_captions"]
    mock_session.refresh.assert_awaited_once()


def test_content_endpoint_invalid_uuid(client):
    response = client.get("/v1/transcripts/not-a-uuid/content")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid UUID"
