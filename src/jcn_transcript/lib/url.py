"""YouTube URL parsing and validation."""

import re
from urllib.parse import parse_qs, urlparse

# Patterns that match YouTube video URLs
_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=(?P<id>[A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/(?P<id>[A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/v/(?P<id>[A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/(?P<id>[A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?://)?youtu\.be/(?P<id>[A-Za-z0-9_-]{11})"),
]

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url: str) -> str | None:
    """Extract a YouTube video ID from a URL or bare ID string.

    Returns the 11-character video ID, or None if the input is not a valid YouTube URL.
    """
    url = url.strip()

    # Bare video ID
    if _VIDEO_ID_RE.match(url):
        return url

    for pattern in _PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group("id")

    # Fallback: parse query string for ?v= param
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        v = qs.get("v")
        if v and _VIDEO_ID_RE.match(v[0]):
            return v[0]

    return None


def canonical_url(video_id: str) -> str:
    """Return the canonical YouTube URL for a video ID."""
    return f"https://youtu.be/{video_id}"
