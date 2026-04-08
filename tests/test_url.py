"""Tests for URL parsing."""

from yt_transcript.lib.url import canonical_url, extract_video_id


def test_standard_url():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_short_url():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_embed_url():
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_shorts_url():
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_url_with_extra_params():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_bare_video_id():
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_invalid_url():
    assert extract_video_id("https://example.com/not-youtube") is None


def test_empty_string():
    assert extract_video_id("") is None


def test_canonical_url():
    assert canonical_url("dQw4w9WgXcQ") == "https://youtu.be/dQw4w9WgXcQ"


def test_no_scheme():
    assert extract_video_id("youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_v_url():
    assert extract_video_id("https://www.youtube.com/v/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
