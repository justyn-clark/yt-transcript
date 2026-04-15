"""CLI entrypoint for yt-transcript."""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

import click

from ..lib.errors import TranscriptError
from ..lib.normalize import reflow_transcript_lines
from ..lib.pipeline import PipelineOptions, ingest_youtube_url


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """Local-first YouTube transcript ingestion."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
@click.argument("url")
@click.option("--force-asr", is_flag=True, help="Skip subtitle retrieval and go straight to ASR")
@click.option("--no-notes", is_flag=True, help="Skip markdown note export")
@click.option("--no-db", is_flag=True, help="Skip database persistence")
@click.option("--open-note", is_flag=True, help="Open the note after creation")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output result as JSON")
def youtube(url: str, force_asr: bool, no_notes: bool, no_db: bool, open_note: bool, json_out: bool):
    """Ingest a YouTube video transcript.

    Accepts a YouTube URL or video ID.
    """
    options = PipelineOptions(
        persist_notes=False if no_notes else None,
        persist_to_db=not no_db,
        open_note=open_note,
        force_asr=force_asr,
    )

    try:
        result = asyncio.run(ingest_youtube_url(url, options))
    except TranscriptError as e:
        if json_out:
            click.echo(json.dumps(e.to_dict(), indent=2))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        if json_out:
            click.echo(json.dumps({"error_type": "unexpected", "message": str(e)}, indent=2))
        else:
            click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)

    if json_out:
        click.echo(
            json.dumps(
                {
                    "id": result.id,
                    "source_type": result.source_type,
                    "source_id": result.source_id,
                    "status": result.status,
                    "retrieval_method": result.retrieval_method,
                    "language": result.language,
                    "segment_count": result.segment_count,
                    "title": result.title,
                    "url": result.url,
                    "db_status": result.db_status,
                    "notes_status": result.notes_status,
                    "notes_path": result.notes_path,
                },
                indent=2,
            )
        )
    else:
        click.echo(f"Done: {result.title}")
        click.echo(f"  Video ID:   {result.source_id}")
        click.echo(f"  Method:     {result.retrieval_method}")
        click.echo(f"  Language:   {result.language}")
        click.echo(f"  Segments:   {result.segment_count}")
        click.echo(f"  DB:         {result.db_status}")
        click.echo(f"  Notes:      {result.notes_status}")
        if result.notes_path:
            click.echo(f"  Note path:  {result.notes_path}")
        if result.id:
            click.echo(f"  DB ID:      {result.id}")


@cli.command("format-note")
@click.argument("note_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--gap", default=5, show_default=True, help="Timestamp gap (seconds) that triggers a paragraph break.")
@click.option("--max-words", default=75, show_default=True, help="Word count ceiling per paragraph.")
def format_note(note_path: Path, gap: int, max_words: int):
    """Reflow a transcript note into readable paragraphs.

    Writes a normalized copy alongside the original as <name>-normalized.md.
    The original file is never modified.
    """
    _TS_LINE = re.compile(r"^\[(\d+:\d{2}(?::\d{2})?)\] (.+)$")

    source = note_path.read_text(encoding="utf-8")

    # Split into sections: everything before "## Transcript", the heading, and the body
    transcript_marker = "\n## Transcript\n"
    marker_idx = source.find(transcript_marker)
    if marker_idx == -1:
        raise click.ClickException("No '## Transcript' section found in the file.")

    preamble = source[: marker_idx + len(transcript_marker)]
    body = source[marker_idx + len(transcript_marker) :]

    # Parse timestamped lines from the transcript body
    raw_lines: list[tuple[str, str]] = []
    other_lines: list[str] = []
    for line in body.splitlines():
        m = _TS_LINE.match(line.strip())
        if m:
            raw_lines.append((m.group(1), m.group(2)))
        elif line.strip():
            other_lines.append(line)

    if not raw_lines:
        raise click.ClickException("No timestamped lines ([MM:SS] text) found in the transcript section.")

    paragraphs = reflow_transcript_lines(raw_lines, gap_threshold_s=gap, max_words=max_words)

    transcript_body = "\n\n".join(f"[{ts}] {text}" for ts, text in paragraphs)
    normalized = preamble + transcript_body + "\n"

    out_path = note_path.with_name(note_path.stem + "-normalized" + note_path.suffix)
    out_path.write_text(normalized, encoding="utf-8")
    click.echo(f"Normalized note written: {out_path}")
    click.echo(f"  {len(raw_lines)} caption lines → {len(paragraphs)} paragraphs")


def main():
    cli()


if __name__ == "__main__":
    main()
