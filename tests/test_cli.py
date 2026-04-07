"""CLI smoke tests for each persistence mode."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from yt_transcript.cli.main import cli
from yt_transcript.lib.models import IngestResult


def _mock_result(**overrides):
    defaults = dict(
        id="",
        source_type="youtube",
        source_id="dQw4w9WgXcQ",
        status="done",
        retrieval_method="captions",
        language="en",
        segment_count=10,
        title="Test Video",
        url="https://youtu.be/dQw4w9WgXcQ",
        db_status="skipped",
        notes_status="skipped",
        notes_path=None,
    )
    defaults.update(overrides)
    return IngestResult(**defaults)


def _run_cli(args, mock_result):
    runner = CliRunner()
    with patch("yt_transcript.cli.main.ingest_youtube_url", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = mock_result
        result = runner.invoke(cli, args)
    return result


def test_cli_ingest_only():
    """CLI with --no-db --no-notes runs ingest-only mode."""
    result = _run_cli(
        ["youtube", "dQw4w9WgXcQ", "--no-db", "--no-notes"],
        _mock_result(),
    )
    assert result.exit_code == 0
    assert "Done: Test Video" in result.output
    assert "DB:         skipped" in result.output
    assert "Notes:      skipped" in result.output


def test_cli_with_db():
    """CLI with DB enabled shows db_status."""
    result = _run_cli(
        ["youtube", "dQw4w9WgXcQ", "--no-notes"],
        _mock_result(id="abc-123", db_status="ok"),
    )
    assert result.exit_code == 0
    assert "DB:         ok" in result.output
    assert "DB ID:      abc-123" in result.output


def test_cli_with_notes():
    """CLI with notes enabled shows notes_status and path."""
    result = _run_cli(
        ["youtube", "dQw4w9WgXcQ", "--no-db"],
        _mock_result(notes_status="ok", notes_path="/tmp/test/note.md"),
    )
    assert result.exit_code == 0
    assert "Notes:      ok" in result.output
    assert "Note path:  /tmp/test/note.md" in result.output


def test_cli_json_output():
    """CLI --json outputs structured JSON with per-sink status."""
    result = _run_cli(
        ["youtube", "dQw4w9WgXcQ", "--no-db", "--no-notes", "--json"],
        _mock_result(),
    )
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["status"] == "done"
    assert data["db_status"] == "skipped"
    assert data["notes_status"] == "skipped"
    assert data["notes_path"] is None


def test_cli_error_handling():
    """CLI surfaces TranscriptError cleanly."""
    from yt_transcript.lib.errors import TranscriptError

    runner = CliRunner()
    with patch("yt_transcript.cli.main.ingest_youtube_url", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.side_effect = TranscriptError("invalid_url", "bad url")
        result = runner.invoke(cli, ["youtube", "not-a-url"])

    assert result.exit_code == 1
    assert "invalid_url" in result.output
