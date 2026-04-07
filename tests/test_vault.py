"""Tests for vault writer."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from jcn_transcript.lib.models import Segment, TranscriptResult
from jcn_transcript.lib.vault import write_vault_note


def test_write_vault_note():
    result = TranscriptResult(
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

    with tempfile.TemporaryDirectory() as tmp:
        with patch("jcn_transcript.lib.vault.settings") as mock_settings:
            mock_settings.vault_path = Path(tmp)
            mock_settings.vault_transcript_dir = "Inbox/Transcripts/YouTube"

            path = write_vault_note(result)
            assert Path(path).exists()

            content = Path(path).read_text()
            assert "video_id: abc123test1" in content
            assert "Test Video Title" in content
            assert "[00:00] Hello world" in content
            assert "[00:04] This is a test" in content
            assert "type: transcript" in content
            assert "source: youtube" in content
