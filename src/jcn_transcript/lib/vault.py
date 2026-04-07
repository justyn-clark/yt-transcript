"""Obsidian vault note writer."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .models import TranscriptResult
from .normalize import format_timestamp, sanitize_title

logger = logging.getLogger(__name__)


def write_vault_note(result: TranscriptResult) -> str:
    """Write a transcript note to the Obsidian vault.

    Returns the absolute path to the created note.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    year_str = now.strftime("%Y")

    title = result.title or result.video_id
    safe_title = sanitize_title(title)
    filename = f"{date_str} - {safe_title}.md"

    vault_dir = settings.vault_path / settings.vault_transcript_dir / year_str
    vault_dir.mkdir(parents=True, exist_ok=True)

    note_path = vault_dir / filename

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

    logger.info("Vault note written: %s", note_path)
    return str(note_path)


def _escape_yaml(s: str) -> str:
    """Escape a string for YAML double-quoted values."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
