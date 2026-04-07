"""Tests for text normalization."""

from jcn_transcript.lib.normalize import clean_text, format_timestamp, sanitize_title


def test_format_timestamp_minutes():
    assert format_timestamp(0) == "[00:00]"
    assert format_timestamp(65) == "[01:05]"
    assert format_timestamp(599) == "[09:59]"


def test_format_timestamp_hours():
    assert format_timestamp(3600) == "[1:00:00]"
    assert format_timestamp(3661) == "[1:01:01]"


def test_sanitize_title_basic():
    assert sanitize_title("My Video Title") == "My Video Title"


def test_sanitize_title_special_chars():
    assert sanitize_title('Video: "Test" <Title>') == "Video Test Title"


def test_sanitize_title_long():
    title = "A" * 200
    result = sanitize_title(title)
    assert len(result) <= 120


def test_sanitize_title_empty():
    assert sanitize_title("") == "Untitled"


def test_clean_text_music_tags():
    assert clean_text("Hello [Music] world") == "Hello world"


def test_clean_text_whitespace():
    assert clean_text("  hello   world  ") == "hello world"
