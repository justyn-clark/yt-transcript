"""Main ingestion pipeline orchestrator."""

import dataclasses
import logging
import shutil
import time
from dataclasses import dataclass, field
from typing import Any

from ..config import settings
from ..db.crud import set_notes_path, upsert_transcript
from ..db.engine import async_session
from ..lib import captions, errors, ytdlp
from ..lib.models import IngestResult, TranscriptResult
from ..lib.normalize import clean_text
from ..lib.notes import write_note
from ..lib.url import canonical_url, extract_video_id
from ..workers.asr_client import asr_result_to_transcript, transcribe_audio

logger = logging.getLogger(__name__)


@dataclass
class PipelineOptions:
    persist_to_db: bool = True
    persist_notes: bool | None = None  # None = auto (on when notes_dir is configured)
    open_note: bool = False
    force_asr: bool = False

    @property
    def should_persist_notes(self) -> bool:
        if self.persist_notes is not None:
            return self.persist_notes
        return settings.notes_enabled


@dataclass
class PipelineLog:
    job_id: str = ""
    source_url: str = ""
    video_id: str = ""
    retrieval_path: str = ""
    stages: list[dict[str, Any]] = field(default_factory=list)
    status: str = ""
    note_path: str = ""
    db_id: str = ""
    total_seconds: float = 0

    def stage(self, name: str, duration: float, status: str = "ok", detail: str = ""):
        self.stages.append({"name": name, "duration_seconds": round(duration, 2), "status": status, "detail": detail})


async def ingest_youtube_url(url: str, options: PipelineOptions | None = None) -> IngestResult:
    """Full ingestion pipeline for a YouTube URL."""
    import uuid

    opts = options or PipelineOptions()
    log = PipelineLog(job_id=str(uuid.uuid4()), source_url=url)
    pipeline_start = time.monotonic()

    # Step 1: Resolve video ID
    t0 = time.monotonic()
    video_id = extract_video_id(url)
    if not video_id:
        raise errors.invalid_url(url)
    log.video_id = video_id
    log.stage("resolve_url", time.monotonic() - t0)

    # Step 2: Fetch metadata
    t0 = time.monotonic()
    metadata = ytdlp.fetch_metadata(video_id)
    log.stage("fetch_metadata", time.monotonic() - t0, detail="found" if metadata else "none")

    # Step 3: Retrieve transcript
    transcript: TranscriptResult | None = None

    if not opts.force_asr:
        # Step 3A: youtube-transcript-api
        t0 = time.monotonic()
        transcript = captions.fetch_captions(video_id)
        log.stage("captions_api", time.monotonic() - t0, status="ok" if transcript else "miss")

        # Step 3B: yt-dlp subtitle fallback
        if transcript is None:
            t0 = time.monotonic()
            transcript = ytdlp.fetch_subtitles(video_id)
            log.stage("ytdlp_subtitles", time.monotonic() - t0, status="ok" if transcript else "miss")

    # Step 3C: ASR fallback
    if transcript is None:
        t0 = time.monotonic()
        audio_path = ytdlp.download_audio(video_id)
        if audio_path is None:
            log.stage("audio_download", time.monotonic() - t0, status="failed")
            raise errors.audio_download_failed(video_id, "yt-dlp could not extract audio")

        log.stage("audio_download", time.monotonic() - t0)

        t0 = time.monotonic()
        asr_result = await transcribe_audio(video_id, audio_path)
        if asr_result.status != "done":
            log.stage("asr_transcribe", time.monotonic() - t0, status="failed", detail=asr_result.error)
            _cleanup_tmp(video_id)
            raise errors.asr_failed(video_id, asr_result.error)

        transcript = asr_result_to_transcript(video_id, asr_result)
        log.stage("asr_transcribe", time.monotonic() - t0)

        _cleanup_tmp(video_id)

    if transcript is None:
        raise errors.transcript_not_found(video_id)

    log.retrieval_path = transcript.retrieval_method

    # Enrich transcript with metadata
    if metadata:
        transcript.title = metadata.title or transcript.title
        transcript.channel_name = metadata.channel_name or transcript.channel_name
        transcript.published_at = metadata.published_at
        transcript.duration_seconds = metadata.duration_seconds
        transcript.language = metadata.language or transcript.language
        if not metadata.channel_name:
            transcript.quality_flags.append("no_channel_metadata")
        if metadata.language and metadata.language != "en":
            transcript.quality_flags.append("language_inferred")

    # Step 4: Normalize
    t0 = time.monotonic()
    transcript.full_text = clean_text(transcript.full_text)
    log.stage("normalize", time.monotonic() - t0)

    # Step 5: Persist to Postgres
    db_id = ""
    db_item_id = None
    db_status = "skipped"
    sink_failed = False
    if opts.persist_to_db:
        t0 = time.monotonic()
        try:
            raw_payload = _build_raw_payload(metadata, log)
            async with async_session() as session:
                item = await upsert_transcript(session, transcript, raw_payload=raw_payload)
                db_item_id = item.id
                db_id = str(item.id)
                log.db_id = db_id
            db_status = "ok"
            log.stage("persist_db", time.monotonic() - t0)
        except Exception as e:
            db_status = "failed"
            sink_failed = True
            log.stage("persist_db", time.monotonic() - t0, status="failed", detail=str(e))
            logger.warning("Failed to persist transcript to DB: %s", e)

    # Step 6: Write markdown note
    notes_path = ""
    notes_status = "skipped"
    if opts.should_persist_notes:
        t0 = time.monotonic()
        try:
            notes_path = write_note(transcript)
            log.note_path = notes_path
            notes_status = "ok"
            log.stage("write_notes", time.monotonic() - t0)

            # Update DB with note path
            if db_item_id is not None:
                try:
                    async with async_session() as session:
                        await set_notes_path(session, db_item_id, notes_path)
                    log.stage("update_note_path", time.monotonic() - t0, detail="ok")
                except Exception as e:
                    db_status = "failed"
                    sink_failed = True
                    log.stage("update_note_path", time.monotonic() - t0, status="failed", detail=str(e))
                    logger.warning("Failed to update DB with note path: %s", e)
        except errors.TranscriptError as e:
            notes_status = "failed"
            sink_failed = True
            log.stage("write_notes", time.monotonic() - t0, status="failed", detail=str(e))
            logger.warning("Failed to write notes: %s", e)
        except Exception as e:
            notes_status = "failed"
            sink_failed = True
            log.stage("write_notes", time.monotonic() - t0, status="failed", detail=str(e))
            logger.warning("Failed to write notes: %s", e)

    # Open note if requested
    if opts.open_note and notes_path:
        import subprocess

        try:
            subprocess.Popen(["open", notes_path])
        except Exception:
            pass

    log.status = "partial" if sink_failed else "done"
    log.total_seconds = round(time.monotonic() - pipeline_start, 2)

    logger.info(
        "Ingestion complete: job=%s video=%s method=%s segments=%d time=%.1fs",
        log.job_id,
        video_id,
        transcript.retrieval_method,
        len(transcript.segments),
        log.total_seconds,
    )

    return IngestResult(
        id=db_id,
        source_type="youtube",
        source_id=video_id,
        status=log.status,
        retrieval_method=transcript.retrieval_method,
        language=transcript.language,
        segment_count=len(transcript.segments),
        title=transcript.title,
        url=canonical_url(video_id),
        db_status=db_status,
        notes_status=notes_status,
        notes_path=notes_path or None,
    )


def _cleanup_tmp(video_id: str) -> None:
    """Clean up temporary files for a video."""
    tmp_dir = settings.tmp_dir / video_id
    if tmp_dir.exists():
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


def _build_raw_payload(metadata: Any, log: PipelineLog) -> dict[str, Any]:
    """Build a JSON-serializable payload for persistence and later audit."""
    payload: dict[str, Any] = {
        "pipeline": {
            "job_id": log.job_id,
            "source_url": log.source_url,
            "video_id": log.video_id,
            "retrieval_path": log.retrieval_path or None,
            "stages": list(log.stages),
        }
    }
    if metadata is not None:
        payload["metadata"] = _jsonable(dataclasses.asdict(metadata))
    return payload


def _jsonable(value: Any) -> Any:
    """Convert dataclass-derived values into JSON-safe primitives."""
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
