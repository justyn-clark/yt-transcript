"""Tests for markdown note writer."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from yt_transcript.lib.errors import TranscriptError
from yt_transcript.lib.models import Segment, TranscriptResult
from yt_transcript.lib.notes import check_notes_dir_writable, write_note


def _make_result(**overrides) -> TranscriptResult:
    defaults = dict(
        video_id="abc123test1",
        url="https://youtu.be/abc123test1",
        title="Test Video Title",
        channel_name="Test Channel",
        language="en",
        retrieval_method="captions",
        segments=[
            Segment(idx=0, start_seconds=0.0, end_seconds=4.2, text="Hello world"),
            Segment(idx=1, start_seconds=4.2, end_seconds=8.0, text="This is a test"),
        ],
        full_text="Hello world This is a test",
    )
    defaults.update(overrides)
    return TranscriptResult(**defaults)


def test_write_note_success():
    result = _make_result()

    with tempfile.TemporaryDirectory() as tmp:
        with patch("yt_transcript.lib.notes.settings") as mock_settings:
            mock_settings.notes_dir = Path(tmp)
            mock_settings.notes_subdir = "Transcripts/YouTube"

            path = write_note(result)
            assert Path(path).exists()

            content = Path(path).read_text()
            assert "video_id: abc123test1" in content
            assert "Test Video Title" in content
            assert "[00:00] Hello world" in content
            assert "[00:04] This is a test" in content
            assert "type: transcript" in content
            assert "source: youtube" in content


def test_write_note_with_explicit_dir():
    """write_note accepts an explicit notes_dir parameter."""
    result = _make_result()

    with tempfile.TemporaryDirectory() as tmp:
        with patch("yt_transcript.lib.notes.settings") as mock_settings:
            mock_settings.notes_dir = None
            mock_settings.notes_subdir = "Transcripts/YouTube"

            path = write_note(result, notes_dir=Path(tmp))
            assert Path(path).exists()


def test_write_note_raises_when_not_configured():
    """write_note raises a structured error when notes_dir is not set."""
    result = _make_result()

    with patch("yt_transcript.lib.notes.settings") as mock_settings:
        mock_settings.notes_dir = None

        with pytest.raises(TranscriptError) as exc_info:
            write_note(result)

        assert exc_info.value.error_type == "notes_not_configured"


def test_check_notes_dir_writable_true():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("yt_transcript.lib.notes.settings") as mock_settings:
            mock_settings.notes_dir = Path(tmp)
            mock_settings.notes_subdir = "Transcripts/YouTube"
            assert check_notes_dir_writable() is True


def test_check_notes_dir_writable_false_when_not_configured():
    with patch("yt_transcript.lib.notes.settings") as mock_settings:
        mock_settings.notes_dir = None
        assert check_notes_dir_writable() is False
