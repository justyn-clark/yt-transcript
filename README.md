# yt-transcript

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red)](https://www.sqlalchemy.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Pydantic](https://img.shields.io/badge/pydantic--settings-2.1%2B-e92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2024%2B-FF0000?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Local-first YouTube transcript ingestion service.

Accepts a YouTube URL, retrieves the transcript through a multi-tier fallback strategy, optionally persists to Postgres, and optionally exports a markdown note.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# Edit .env - see Configuration below
```

### Database (optional)

Postgres is required only when database persistence is enabled (the default).

```bash
createdb yt_transcript
alembic upgrade head
```

To skip database persistence entirely, use `--no-db` on the CLI or `"persist_to_db": false` in API requests.

### Markdown note export (optional)

Set `YT_TRANSCRIPT_NOTES_DIR` to a directory path to enable markdown note export.
Any directory works. If you use [Obsidian](https://obsidian.md/), point this at your vault root for the best experience - the notes include YAML frontmatter and tags that Obsidian indexes automatically.

When `NOTES_DIR` is not set, note export is disabled by default. You can also pass `--no-notes` on the CLI to skip it per-invocation.

## CLI

```bash
# Ingest a YouTube video (DB + notes if configured)
yt-transcript youtube "https://youtu.be/VIDEO_ID"

# JSON output
yt-transcript youtube "https://youtu.be/VIDEO_ID" --json

# Skip note export
yt-transcript youtube "https://youtu.be/VIDEO_ID" --no-notes

# Skip database
yt-transcript youtube "https://youtu.be/VIDEO_ID" --no-db

# Ingest only (no DB, no notes)
yt-transcript youtube "https://youtu.be/VIDEO_ID" --no-db --no-notes

# Force ASR (skip subtitle retrieval)
yt-transcript youtube "https://youtu.be/VIDEO_ID" --force-asr

# Open the note after creation
yt-transcript youtube "https://youtu.be/VIDEO_ID" --open-note

# Verbose logging
yt-transcript -v youtube "https://youtu.be/VIDEO_ID"
```

### Normalizing transcript notes

Auto-captions are split into short 2–3 second lines that break mid-sentence. `format-note` reflowing them into readable paragraphs without modifying the original:

```bash
yt-transcript format-note "path/to/note.md"
# → writes path/to/note-normalized.md
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--gap N` | `5` | Timestamp gap (seconds) that starts a new paragraph |
| `--max-words N` | `75` | Word count ceiling per paragraph |

Paragraph breaks are triggered by whichever condition fires first: a pause longer than `--gap` seconds in the video, or accumulating `--max-words` words. The first word of each paragraph is capitalized. The original `.md` file is never touched.

## HTTP API

```bash
# Start the API server (default: 127.0.0.1:8420)
python -m yt_transcript.api.server
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/transcripts/youtube` | Ingest a YouTube video |
| `GET` | `/v1/transcripts/{id}` | Get transcript by UUID |
| `GET` | `/v1/transcripts/by-source/{video_id}` | Get transcript by YouTube video ID |
| `GET` | `/health/live` | Process liveness check |
| `GET` | `/health/ready` | Dependency readiness check |

### Ingest request

```bash
curl -X POST http://127.0.0.1:8420/v1/transcripts/youtube \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/VIDEO_ID"}'
```

### Ingest response

The response includes per-sink status for honest reporting of partial success:

```json
{
  "id": "uuid",
  "source_type": "youtube",
  "source_id": "VIDEO_ID",
  "status": "done",
  "retrieval_method": "captions",
  "language": "en",
  "segment_count": 42,
  "title": "Video Title",
  "url": "https://youtu.be/VIDEO_ID",
  "db_status": "ok",
  "notes_status": "ok",
  "notes_path": "/path/to/note.md"
}
```

`db_status` and `notes_status` are each one of: `ok`, `skipped`, `failed`.

## Persistence modes

The service supports four persistence modes, chosen per-invocation:

| Mode | CLI flags | API fields | What happens |
|------|-----------|------------|--------------|
| Ingest only | `--no-db --no-notes` | `persist_to_db: false, persist_notes: false` | Retrieve and return transcript data |
| DB only | `--no-notes` | `persist_notes: false` | Persist to Postgres |
| Notes only | `--no-db` | `persist_to_db: false` | Write markdown note |
| DB + Notes | *(default when both configured)* | *(default)* | Both sinks |

Note export defaults to on when `NOTES_DIR` is configured, off when it is not.

## Transcript retrieval

Transcripts are retrieved through a three-tier fallback:

1. **youtube-transcript-api** - manual captions first, then auto-generated
2. **yt-dlp** - subtitle download and VTT parse
3. **ASR** - audio download + remote faster-whisper worker

Each transcript records its `retrieval_method` (`captions`, `auto_captions`, or `asr`) and `quality_flags` for operator review.

## Configuration

All settings are environment variables with prefix `YT_TRANSCRIPT_`. See `.env.example` for a complete template.

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://localhost:5432/yt_transcript` | When using DB | Async Postgres URL |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://localhost:5432/yt_transcript` | When using DB | Sync Postgres URL (Alembic) |
| `NOTES_DIR` | *(unset)* | When using notes | Directory for markdown note export |
| `NOTES_SUBDIR` | `Transcripts/YouTube` | No | Subdirectory within notes dir |
| `ASR_WORKER_URL` | `http://localhost:8787` | When using ASR | ASR worker endpoint |
| `ASR_WORKER_TIMEOUT` | `300` | No | ASR request timeout (seconds) |
| `TMP_DIR` | `/tmp/yt-transcript` | No | Temp directory for downloads |
| `API_HOST` | `127.0.0.1` | No | API bind address |
| `API_PORT` | `8420` | No | API port |

## Storage

- **Postgres**: `media_items` (provenance), `transcript_segments` (timestamped text)
- **Markdown notes**: Frontmatter + timestamped transcript at `NOTES_DIR/NOTES_SUBDIR/YYYY/`

## Limitations

- **ASR fallback requires shared filesystem**: The ASR worker client sends a local file path to the worker, not the audio bytes. Both the service and the ASR worker must have access to the same filesystem path. This is the only supported ASR topology in v0.1.0.
- **Embeddings are not implemented**: The database schema includes a `transcript_embeddings` table reserved for future use. No embedding generation, storage, or query is exposed in v0.1.0.
- **`raw_payload` column is reserved**: The `media_items.raw_payload` JSONB column exists in the schema but is not populated. It is reserved for future use (e.g., storing raw yt-dlp metadata).

## Development

```bash
# Install with dev dependencies (includes psycopg2-binary for Alembic migrations)
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run a single test
pytest tests/test_url.py -v

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Full verification (lint + tests)
ruff check src/ tests/ && pytest tests/ -v
```

## Release status

**v0.1.0 release candidate** - local-first transcript ingestion with Postgres and markdown note export. Suitable for personal and small-team use.

Not included in v0.1.0: embeddings, remote ASR file upload, queue-based job orchestration, frontend UI.
