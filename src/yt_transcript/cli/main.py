"""CLI entrypoint for yt-transcript."""

import asyncio
import json
import logging
import sys

import click

from ..lib.errors import TranscriptError
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


def main():
    cli()


if __name__ == "__main__":
    main()
