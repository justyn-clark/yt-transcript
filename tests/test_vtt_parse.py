"""Tests for VTT parser - verifies dedupe only removes adjacent duplicates."""

import tempfile
from pathlib import Path

from yt_transcript.lib.ytdlp import _parse_vtt, _vtt_time_to_seconds


def _write_vtt(content: str) -> Path:
    """Write VTT content to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".vtt", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


def test_basic_parse():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello world

00:00:04.000 --> 00:00:08.000
This is a test
"""
    segments = _parse_vtt(_write_vtt(vtt))
    assert len(segments) == 2
    assert segments[0].text == "Hello world"
    assert segments[1].text == "This is a test"


def test_adjacent_duplicate_removed():
    """Adjacent identical segments (VTT overlap artifact) should be deduped."""
    vtt = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello world

00:00:03.500 --> 00:00:06.000
Hello world

00:00:06.000 --> 00:00:10.000
Something new
"""
    segments = _parse_vtt(_write_vtt(vtt))
    assert len(segments) == 2
    assert segments[0].text == "Hello world"
    assert segments[1].text == "Something new"


def test_non_adjacent_repeated_text_preserved():
    """Legitimate repeated text at different points should be preserved."""
    vtt = """WEBVTT

00:00:01.000 --> 00:00:04.000
Thank you

00:00:04.000 --> 00:00:08.000
That was wonderful

00:00:08.000 --> 00:00:12.000
Thank you
"""
    segments = _parse_vtt(_write_vtt(vtt))
    assert len(segments) == 3
    texts = [s.text for s in segments]
    assert texts == ["Thank you", "That was wonderful", "Thank you"]


def test_repeated_phrase_chorus():
    """A chorus-like pattern with repeated lines should keep all instances."""
    vtt = """WEBVTT

00:00:01.000 --> 00:00:05.000
La la la

00:00:05.000 --> 00:00:09.000
Something different

00:00:09.000 --> 00:00:13.000
La la la

00:00:13.000 --> 00:00:17.000
Another line

00:00:17.000 --> 00:00:21.000
La la la
"""
    segments = _parse_vtt(_write_vtt(vtt))
    assert len(segments) == 5
    assert segments[0].text == "La la la"
    assert segments[2].text == "La la la"
    assert segments[4].text == "La la la"


def test_vtt_tags_stripped():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:04.000
<c.colorE5E5E5>Hello</c> <c.colorCCCCCC>world</c>
"""
    segments = _parse_vtt(_write_vtt(vtt))
    assert len(segments) == 1
    assert segments[0].text == "Hello world"


def test_empty_segments_skipped():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:04.000


00:00:04.000 --> 00:00:08.000
Actual content
"""
    segments = _parse_vtt(_write_vtt(vtt))
    assert len(segments) == 1
    assert segments[0].text == "Actual content"


def test_vtt_time_to_seconds():
    assert _vtt_time_to_seconds("00:00:01.000") == 1.0
    assert _vtt_time_to_seconds("01:02:03.500") == 3723.5
    assert _vtt_time_to_seconds("00:10:30.000") == 630.0
