"""Markdown note writer for transcript export."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .errors import TranscriptError
from .models import TranscriptResult
from .normalize import format_timestamp, sanitize_title

logger = logging.getLogger(__name__)


def validate_notes_dir() -> Path:
    """Validate that notes_dir is configured and return it.

    Raises TranscriptError if notes_dir is not set.
    """
    if settings.notes_dir is None:
        raise TranscriptError(
            error_type="notes_not_configured",
            message="Markdown note export requested but NOTES_DIR is not configured. "
            "Set YT_TRANSCRIPT_NOTES_DIR to a directory path.",
        )
    return settings.notes_dir


def check_notes_dir_writable() -> bool:
    """Check whether the configured notes directory is writable."""
    if settings.notes_dir is None:
        return False
    try:
        target = settings.notes_dir / settings.notes_subdir
        target.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def write_note(result: TranscriptResult, notes_dir: Path | None = None) -> str:
    """Write a transcript note as a markdown file.

    Uses the provided notes_dir, falling back to settings.notes_dir.
    Returns the absolute path to the created note.

    Raises TranscriptError if no notes directory is available.
    """
    target_dir = notes_dir or validate_notes_dir()

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    year_str = now.strftime("%Y")

    title = result.title or result.video_id
    safe_title = sanitize_title(title)
    filename = f"{date_str} - {safe_title}.md"

    out_dir = target_dir / settings.notes_subdir / year_str
    out_dir.mkdir(parents=True, exist_ok=True)

    note_path = out_dir / filename

    # Build frontmatter
    published = ""
    if result.published_at:
        published = result.published_at.strftime("%Y-%m-%d")

    frontmatter = f"""---
type: transcript
source: youtube
video_id: {result.video_id}
url: {result.url}
title: "{_escape_yaml(title)}"
channel: "{_escape_yaml(result.channel_name)}"
published: {published}
duration_seconds: {result.duration_seconds or ""}
language: {result.language}
retrieval_method: {result.retrieval_method}
transcript_status: done
created_at: {now.isoformat()}
tags:
  - transcript
  - youtube
---"""

    # Build body
    transcript_lines = []
    for seg in result.segments:
        ts = format_timestamp(seg.start_seconds)
        transcript_lines.append(f"{ts} {seg.text}")

    body = f"""# {title}

## Metadata

- **URL**: {result.url}
- **Source**: YouTube
- **Video ID**: {result.video_id}
- **Channel**: {result.channel_name}
- **Retrieval method**: {result.retrieval_method}
- **Language**: {result.language}

## Transcript

{chr(10).join(transcript_lines)}
"""

    content = frontmatter + "\n\n" + body
    note_path.write_text(content, encoding="utf-8")

    logger.info("Note written: %s", note_path)
    return str(note_path)


def _escape_yaml(s: str) -> str:
    """Escape a string for YAML double-quoted values."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
