# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

yt-transcript is a local-first YouTube transcript ingestion service. Accepts a YouTube URL, retrieves the transcript through a three-tier fallback strategy, optionally persists to Postgres, and optionally exports a markdown note.

## Common Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_url.py -v

# Lint
ruff check src/ tests/

# Full verification (lint + tests)
ruff check src/ tests/ && pytest tests/ -v

# Run the API server (127.0.0.1:8420)
python -m yt_transcript.api.server

# CLI usage
yt-transcript youtube "https://youtu.be/VIDEO_ID"

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Architecture

### Ingestion Pipeline (`lib/pipeline.py`)

The central orchestrator. For a given YouTube URL it runs these stages in order:

1. **resolve_url** — extract video ID via `lib/url.py`
2. **fetch_metadata** — get title/channel/duration via `lib/ytdlp.py`
3. **retrieve transcript** — three-tier fallback:
   - `lib/captions.py` — youtube-transcript-api (manual captions first, then auto-generated)
   - `lib/ytdlp.py` — yt-dlp subtitle download + VTT parse
   - `workers/asr_client.py` — audio download + remote faster-whisper worker
4. **normalize** — `lib/normalize.py` cleans the text
5. **persist_db** — upsert to Postgres via `db/crud.py` (when enabled)
6. **write_notes** — markdown note via `lib/notes.py` (when `NOTES_DIR` is configured)

### Two entry points into the pipeline

- **CLI** (`cli/main.py`) — Click CLI, registered as `yt-transcript` console script. Uses `asyncio.run()` to call the async pipeline.
- **HTTP API** (`api/app.py`) — FastAPI app on port 8420. Endpoints under `/v1/transcripts/`.

### Persistence model

Both sinks (DB and notes) are independently optional. The `IngestResult` reports per-sink status (`db_status`, `notes_status`) so partial success is explicit, not hidden.

Note export is conditional: enabled by default when `NOTES_DIR` is configured, disabled when it is not. Can be overridden per-invocation.

### Data layer

- **Domain models** (`lib/models.py`) — pure dataclasses (`Segment`, `TranscriptResult`, `IngestResult`), not ORM.
- **ORM tables** (`db/tables.py`) — SQLAlchemy 2.0 mapped classes: `MediaItem`, `TranscriptSegment`, `TranscriptEmbedding`. All use async sessions via `asyncpg`.
- **CRUD** (`db/crud.py`) — `upsert_transcript` does insert-or-update with segment replacement.
- **Migrations** — Alembic with sync Postgres URL in `alembic.ini`. The `env.py` imports `Base` from `db.tables`.

### Error handling

`lib/errors.py` defines `TranscriptError` (a dataclass + Exception) with factory functions. Both CLI and API convert these to structured output.

### Configuration

All settings via `YT_TRANSCRIPT_` env vars, managed by pydantic-settings in `config.py`. Copy `.env.example` to `.env`.

### Key constraints

- The ASR worker (`workers/asr_client.py`) assumes a shared filesystem with the worker host — it sends a local file path, not audio bytes.
- The `transcript_embeddings` table exists in the schema but embeddings are not implemented. The table is reserved for future use and not exposed in the public API.
- The `raw_payload` column on `media_items` is reserved but not yet populated.

## SMALL Harness

This repo uses the SMALL execution harness (`.small/` directory). Human-owned files (`intent.small.yml`, `constraints.small.yml`) must not be modified without approval. SMALL files must only be modified via the `small` CLI, never edited directly.
