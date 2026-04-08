"""Tests for the ingestion pipeline with mocked dependencies."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from yt_transcript.lib.models import Segment, TranscriptResult, VideoMetadata
from yt_transcript.lib.pipeline import PipelineOptions, ingest_youtube_url


def _mock_transcript(video_id="dQw4w9WgXcQ"):
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
    )


def _mock_metadata(video_id="dQw4w9WgXcQ"):
    return VideoMetadata(
        video_id=video_id,
        title="Test Title",
        channel_name="Test Channel",
        duration_seconds=120,
    )


@pytest.mark.asyncio
async def test_ingest_only_mode():
    """Ingest with both DB and notes disabled returns transcript data only."""
    opts = PipelineOptions(persist_to_db=False, persist_notes=False)

    with (
        patch("yt_transcript.lib.pipeline.captions") as mock_captions,
        patch("yt_transcript.lib.pipeline.ytdlp") as mock_ytdlp,
    ):
        mock_captions.fetch_captions.return_value = _mock_transcript()
        mock_ytdlp.fetch_metadata.return_value = _mock_metadata()

        result = await ingest_youtube_url("https://youtu.be/dQw4w9WgXcQ", opts)

    assert result.status == "done"
    assert result.db_status == "skipped"
    assert result.notes_status == "skipped"
    assert result.id == ""
    assert result.notes_path is None
    assert result.segment_count == 2


@pytest.mark.asyncio
async def test_ingest_with_notes():
    """Ingest with notes enabled writes a file and reports notes_status=ok."""
    with tempfile.TemporaryDirectory() as tmp:
        opts = PipelineOptions(persist_to_db=False, persist_notes=True)

        with (
            patch("yt_transcript.lib.pipeline.captions") as mock_captions,
            patch("yt_transcript.lib.pipeline.ytdlp") as mock_ytdlp,
            patch("yt_transcript.lib.pipeline.settings") as mock_settings,
            patch("yt_transcript.lib.notes.settings") as mock_notes_settings,
        ):
            mock_captions.fetch_captions.return_value = _mock_transcript()
            mock_ytdlp.fetch_metadata.return_value = _mock_metadata()
            mock_settings.notes_enabled = True
            mock_settings.notes_dir = Path(tmp)
            mock_settings.tmp_dir = Path(tmp) / "tmp"
            mock_notes_settings.notes_dir = Path(tmp)
            mock_notes_settings.notes_subdir = "Transcripts/YouTube"

            result = await ingest_youtube_url("https://youtu.be/dQw4w9WgXcQ", opts)

        assert result.notes_status == "ok"
        assert result.notes_path is not None
        assert Path(result.notes_path).exists()


@pytest.mark.asyncio
async def test_caption_fallback_to_ytdlp():
    """When captions API returns None, pipeline falls back to yt-dlp subtitles."""
    opts = PipelineOptions(persist_to_db=False, persist_notes=False)

    with (
        patch("yt_transcript.lib.pipeline.captions") as mock_captions,
        patch("yt_transcript.lib.pipeline.ytdlp") as mock_ytdlp,
    ):
        mock_captions.fetch_captions.return_value = None
        mock_ytdlp.fetch_metadata.return_value = _mock_metadata()
        mock_ytdlp.fetch_subtitles.return_value = _mock_transcript()

        result = await ingest_youtube_url("https://youtu.be/dQw4w9WgXcQ", opts)

    assert result.status == "done"
    mock_ytdlp.fetch_subtitles.assert_called_once()


@pytest.mark.asyncio
async def test_asr_fallback():
    """When captions and yt-dlp both fail, pipeline falls to ASR."""
    from yt_transcript.workers.asr_client import ASRJobResult

    opts = PipelineOptions(persist_to_db=False, persist_notes=False)

    asr_result = ASRJobResult(
        job_id="test",
        status="done",
        language="en",
        segments=[
            Segment(idx=0, start_seconds=0.0, end_seconds=5.0, text="ASR text"),
        ],
        text="ASR text",
    )

    with (
        patch("yt_transcript.lib.pipeline.captions") as mock_captions,
        patch("yt_transcript.lib.pipeline.ytdlp") as mock_ytdlp,
        patch("yt_transcript.lib.pipeline.transcribe_audio", new_callable=AsyncMock) as mock_asr,
        patch("yt_transcript.lib.pipeline.asr_result_to_transcript") as mock_convert,
        patch("yt_transcript.lib.pipeline.settings") as mock_settings,
    ):
        mock_captions.fetch_captions.return_value = None
        mock_ytdlp.fetch_metadata.return_value = _mock_metadata()
        mock_ytdlp.fetch_subtitles.return_value = None
        mock_ytdlp.download_audio.return_value = Path("/tmp/fake/audio.wav")
        mock_asr.return_value = asr_result
        mock_convert.return_value = TranscriptResult(
            video_id="dQw4w9WgXcQ",
            url="https://youtu.be/dQw4w9WgXcQ",
            title="",
            channel_name="",
            language="en",
            retrieval_method="asr",
            segments=asr_result.segments,
            full_text="ASR text",
            quality_flags=["used_asr"],
        )
        mock_settings.tmp_dir = Path("/tmp/yt-test")

        result = await ingest_youtube_url("https://youtu.be/dQw4w9WgXcQ", opts)

    assert result.status == "done"
    assert result.retrieval_method == "asr"


@pytest.mark.asyncio
async def test_force_asr_skips_captions():
    """--force-asr skips caption retrieval entirely."""
    from yt_transcript.workers.asr_client import ASRJobResult

    opts = PipelineOptions(persist_to_db=False, persist_notes=False, force_asr=True)

    asr_result = ASRJobResult(
        job_id="test",
        status="done",
        language="en",
        segments=[Segment(idx=0, start_seconds=0.0, end_seconds=5.0, text="Forced ASR")],
        text="Forced ASR",
    )

    with (
        patch("yt_transcript.lib.pipeline.captions") as mock_captions,
        patch("yt_transcript.lib.pipeline.ytdlp") as mock_ytdlp,
        patch("yt_transcript.lib.pipeline.transcribe_audio", new_callable=AsyncMock) as mock_asr,
        patch("yt_transcript.lib.pipeline.asr_result_to_transcript") as mock_convert,
        patch("yt_transcript.lib.pipeline.settings") as mock_settings,
    ):
        mock_ytdlp.fetch_metadata.return_value = _mock_metadata()
        mock_ytdlp.download_audio.return_value = Path("/tmp/fake/audio.wav")
        mock_asr.return_value = asr_result
        mock_convert.return_value = TranscriptResult(
            video_id="dQw4w9WgXcQ",
            url="https://youtu.be/dQw4w9WgXcQ",
            title="",
            channel_name="",
            language="en",
            retrieval_method="asr",
            segments=asr_result.segments,
            full_text="Forced ASR",
            quality_flags=["used_asr"],
        )
        mock_settings.tmp_dir = Path("/tmp/yt-test")

        result = await ingest_youtube_url("https://youtu.be/dQw4w9WgXcQ", opts)

    # Captions should never have been called
    mock_captions.fetch_captions.assert_not_called()
    assert result.retrieval_method == "asr"
