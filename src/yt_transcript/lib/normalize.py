"""Transcript text normalization."""

import re


def reflow_transcript_lines(
    timestamped_lines: list[tuple[str, str]],
    gap_threshold_s: int = 5,
    max_words: int = 75,
) -> list[tuple[str, str]]:
    """Merge fragmented caption lines into readable paragraphs.

    Starts a new paragraph when the timestamp gap exceeds gap_threshold_s
    seconds OR the accumulated word count reaches max_words.

    Args:
        timestamped_lines: List of (timestamp_str, text) pairs, e.g. [("00:03", "hello world"), ...]
        gap_threshold_s: Seconds between lines that triggers a paragraph break.
        max_words: Word count ceiling that triggers a paragraph break.

    Returns:
        List of (timestamp_str, paragraph_text) pairs.
    """

    def _ts_to_seconds(ts: str) -> int:
        parts = [int(p) for p in ts.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return parts[0] * 3600 + parts[1] * 60 + parts[2]

    paragraphs: list[tuple[str, str]] = []
    current_ts: str | None = None
    current_words: list[str] = []
    prev_s: int | None = None

    def _flush() -> None:
        nonlocal current_ts, current_words, prev_s
        if current_words:
            para = " ".join(current_words)
            para = para[0].upper() + para[1:] if para else para
            paragraphs.append((current_ts, para))  # type: ignore[arg-type]
        current_ts = None
        current_words = []
        prev_s = None

    for ts, text in timestamped_lines:
        text = text.strip()
        cur_s = _ts_to_seconds(ts)

        if current_ts is not None:
            gap = cur_s - prev_s if prev_s is not None else 0
            word_count = sum(len(w.split()) for w in current_words)
            if gap > gap_threshold_s or word_count >= max_words:
                _flush()

        if current_ts is None:
            current_ts = ts
        current_words.append(text)
        prev_s = cur_s

    _flush()
    return paragraphs


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
