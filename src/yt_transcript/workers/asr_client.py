"""Client for the Mac Studio ASR worker."""

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..config import settings
from ..lib.models import Segment, TranscriptResult

logger = logging.getLogger(__name__)


@dataclass
class ASRJobResult:
    job_id: str
    status: str
    language: str = "en"
    segments: list[Segment] = field(default_factory=list)
    text: str = ""
    error: str = ""


async def transcribe_audio(video_id: str, audio_path: Path) -> ASRJobResult:
    """Send audio to the Mac Studio worker for transcription.

    The worker is expected to expose POST /v1/transcribe with:
    - job_id: str
    - audio_path: str (shared filesystem path)
    - language_hint: str
    - model: str
    - return_segments: bool
    """
    job_id = str(uuid.uuid4())
    url = f"{settings.asr_worker_url}/v1/transcribe"

    payload = {
        "job_id": job_id,
        "audio_path": str(audio_path),
        "language_hint": "en",
        "model": "base.en",
        "return_segments": True,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.asr_worker_timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            segments = [
                Segment(
                    idx=s.get("idx", i),
                    start_seconds=s.get("start_seconds", 0),
                    end_seconds=s.get("end_seconds", 0),
                    text=s.get("text", ""),
                )
                for i, s in enumerate(data.get("segments", []))
            ]

            return ASRJobResult(
                job_id=data.get("job_id", job_id),
                status=data.get("status", "done"),
                language=data.get("language", "en"),
                segments=segments,
                text=data.get("text", ""),
            )
    except httpx.ConnectError:
        logger.error("ASR worker unreachable at %s", settings.asr_worker_url)
        return ASRJobResult(job_id=job_id, status="failed", error=f"Worker unreachable at {settings.asr_worker_url}")
    except httpx.HTTPStatusError as e:
        logger.error("ASR worker returned error: %s", e.response.status_code)
        return ASRJobResult(job_id=job_id, status="failed", error=f"HTTP {e.response.status_code}")
    except Exception as e:
        logger.error("ASR worker error: %s", e)
        return ASRJobResult(job_id=job_id, status="failed", error=str(e))


def asr_result_to_transcript(video_id: str, result: ASRJobResult) -> TranscriptResult:
    """Convert an ASR job result to a TranscriptResult."""
    quality_flags = ["used_asr"]
    if result.status != "done":
        quality_flags.append("low_confidence_asr")

    return TranscriptResult(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title="",
        channel_name="",
        language=result.language,
        retrieval_method="asr",
        segments=result.segments,
        full_text=result.text or " ".join(s.text for s in result.segments),
        quality_flags=quality_flags,
    )
