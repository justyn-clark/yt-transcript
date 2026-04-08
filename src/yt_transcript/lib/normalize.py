"""Transcript text normalization."""

import re


def format_timestamp(seconds: float) -> str:
    """Format seconds as [HH:MM:SS] or [MM:SS]."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"[{h:d}:{m:02d}:{s:02d}]"
    return f"[{m:02d}:{s:02d}]"


def sanitize_title(title: str) -> str:
    """Sanitize a title for use as a filename."""
    # Remove characters that are problematic in filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', "", title)
    # Collapse whitespace
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    # Truncate to a reasonable length
    if len(sanitized) > 120:
        sanitized = sanitized[:120].rsplit(" ", 1)[0]
    return sanitized or "Untitled"


def clean_text(text: str) -> str:
    """Clean transcript text: remove artifacts, normalize whitespace."""
    # Remove common VTT/SRT artifacts
    text = re.sub(r"\[Music\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[Applause\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[Laughter\]", "", text, flags=re.IGNORECASE)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
