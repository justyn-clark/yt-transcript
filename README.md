# jcn-transcript

Local-first YouTube transcript ingestion service for JCN.

Accepts a YouTube URL, retrieves the transcript (subtitle-first, ASR fallback), persists to Postgres with segments, and writes an Obsidian vault note.

## Setup

```bash
# Create venv and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Copy and configure environment
cp .env.example .env

# Start Postgres and run migrations
brew services start postgresql@18
createdb jcn_transcript
alembic upgrade head
```

## CLI

```bash
# Ingest a YouTube video
jcn-transcript youtube "https://youtu.be/VIDEO_ID"

# JSON output
jcn-transcript youtube "https://youtu.be/VIDEO_ID" --json

# Skip vault note
jcn-transcript youtube "https://youtu.be/VIDEO_ID" --no-vault

# Skip database
jcn-transcript youtube "https://youtu.be/VIDEO_ID" --no-db

# Force ASR (skip subtitle retrieval)
jcn-transcript youtube "https://youtu.be/VIDEO_ID" --force-asr

# Open the vault note after creation
jcn-transcript youtube "https://youtu.be/VIDEO_ID" --open-note

# Verbose logging
jcn-transcript -v youtube "https://youtu.be/VIDEO_ID"
```

## HTTP API

```bash
# Start the API server (default: 127.0.0.1:8420)
python -m jcn_transcript.api.server
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/transcripts/youtube` | Ingest a YouTube video |
| `GET` | `/v1/transcripts/{id}` | Get transcript by UUID |
| `GET` | `/v1/transcripts/by-source/{video_id}` | Get transcript by YouTube video ID |
| `GET` | `/health` | Health check |

### Ingest request

```bash
curl -X POST http://127.0.0.1:8420/v1/transcripts/youtube \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/VIDEO_ID"}'
```

## Architecture

```
src/jcn_transcript/
  api/          FastAPI HTTP service
  cli/          Click CLI
  db/           SQLAlchemy models, CRUD, engine
  lib/          Core logic: captions, yt-dlp, pipeline, vault writer
  workers/      ASR worker client (Mac Studio dispatch)
```

### Retrieval Priority

1. **youtube-transcript-api** - manual captions, then auto-generated
2. **yt-dlp** - subtitle download and VTT parse fallback
3. **ASR** - audio download + Mac Studio faster-whisper worker

### Storage

- **Postgres**: `media_items` (provenance), `transcript_segments` (timestamped text), `transcript_embeddings` (future)
- **Obsidian vault**: Markdown note with frontmatter at `Inbox/Transcripts/YouTube/YYYY/`

### Provenance

Every transcript records `retrieval_method` (captions | auto_captions | asr) and `quality_flags` for operator review.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Configuration

All settings are via environment variables prefixed with `JCN_TRANSCRIPT_`. See `.env.example` for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://justin@localhost:5432/jcn_transcript` | Async Postgres URL |
| `VAULT_PATH` | `~/Documents/.../jcn-obsidian-vault` | Obsidian vault root |
| `ASR_WORKER_URL` | `http://studio.local:8787` | Mac Studio ASR endpoint |
| `API_HOST` | `127.0.0.1` | API bind address |
| `API_PORT` | `8420` | API port |
| `EMBEDDINGS_ENABLED` | `false` | Enable embedding generation |
