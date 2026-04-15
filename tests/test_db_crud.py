"""Tests for transcript persistence CRUD behavior."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yt_transcript.db.crud import upsert_transcript
from yt_transcript.db.tables import MediaItem, TranscriptSegment
from yt_transcript.lib.models import Segment, TranscriptResult


class FakeSession:
    """Small async session double for CRUD tests."""

    def __init__(self):
        self.added: list[object] = []
        self.add = MagicMock(side_effect=self.added.append)
        self.execute = AsyncMock()
        self.flush = AsyncMock(side_effect=self._flush)
        self.commit = AsyncMock()

    async def _flush(self) -> None:
        for obj in self.added:
            if isinstance(obj, MediaItem) and obj.id is None:
                obj.id = uuid.UUID(int=1)


def _transcript(video_id: str = "dQw4w9WgXcQ") -> TranscriptResult:
    return TranscriptResult(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title="Test Title",
        channel_name="Test Channel",
        language="en",
        retrieval_method="captions",
        segments=[
            Segment(idx=0, start_seconds=0.0, end_seconds=5.0, text="Hello"),
            Segment(idx=1, start_seconds=5.0, end_seconds=10.0, text="World"),
        ],
        full_text="Hello World",
        duration_seconds=120,
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        quality_flags=["used_captions"],
    )


@pytest.mark.asyncio
async def test_upsert_transcript_stores_raw_payload_on_insert():
    session = FakeSession()
    transcript = _transcript()
    raw_payload = {
        "metadata": {"source": "yt-dlp", "language": "en"},
        "pipeline": {"job_id": "job-1", "stage": "captions"},
    }

    with patch("yt_transcript.db.crud.find_by_source", new=AsyncMock(return_value=None)):
        item = await upsert_transcript(session, transcript, raw_payload=raw_payload)

    assert item.raw_payload == raw_payload
    assert item.transcript_status == "done"
    assert item.title == transcript.title
    assert session.add.call_count == 3
    assert session.flush.await_count == 1
    assert session.commit.await_count == 1
    assert session.add.call_args_list[0].args[0].raw_payload == raw_payload
    assert isinstance(session.add.call_args_list[1].args[0], TranscriptSegment)
    assert session.add.call_args_list[1].args[0].media_item_id == uuid.UUID(int=1)


@pytest.mark.asyncio
async def test_upsert_transcript_merges_raw_payload_on_update():
    session = FakeSession()
    transcript = _transcript()
    transcript.title = "Updated Title"
    transcript.full_text = "Updated text"
    transcript.quality_flags = ["used_asr"]

    existing = MediaItem(
        id=uuid.UUID(int=2),
        source_type="youtube",
        source_id=transcript.video_id,
        url=transcript.url,
        title="Original Title",
        channel_name="Original Channel",
        published_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        duration_seconds=60,
        language="en",
        retrieval_method="captions",
        transcript_status="done",
        transcript_text="Original text",
        raw_payload={
            "metadata": {"source": "captions", "language": "en"},
            "pipeline": {"job_id": "job-1", "stage": "capture"},
            "unchanged": "keep",
        },
        quality_flags=["used_captions"],
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    existing.segments = [
        TranscriptSegment(
            media_item_id=existing.id,
            idx=99,
            start_seconds=99.0,
            end_seconds=100.0,
            text="stale",
            tokens_estimate=1,
        )
    ]

    raw_payload = {
        "pipeline": {"stage": "normalize"},
        "diagnostics": {"db_write": "ok"},
    }

    with patch("yt_transcript.db.crud.find_by_source", new=AsyncMock(return_value=existing)):
        item = await upsert_transcript(session, transcript, raw_payload=raw_payload)

    assert item is existing
    assert item.title == "Updated Title"
    assert item.transcript_text == "Updated text"
    assert item.raw_payload == {
        "metadata": {"source": "captions", "language": "en"},
        "pipeline": {"job_id": "job-1", "stage": "normalize"},
        "unchanged": "keep",
        "diagnostics": {"db_write": "ok"},
    }
    assert [segment.text for segment in item.segments] == ["Hello", "World"]
    assert session.execute.await_count == 1
    assert session.flush.await_count == 1
    assert session.commit.await_count == 1
