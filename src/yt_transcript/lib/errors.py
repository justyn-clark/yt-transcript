"""Structured error types for the transcript pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranscriptError(Exception):
    error_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
        }


def _video_details(video_id: str, reason: str = "") -> dict[str, Any]:
    return {"video_id": video_id, "reason": reason}


def invalid_url(url: str) -> TranscriptError:
    return TranscriptError("invalid_url", f"Could not parse YouTube video ID from: {url}", {"url": url})


def transcript_not_found(video_id: str) -> TranscriptError:
    return TranscriptError("transcript_not_found", f"No transcript found for video: {video_id}", {"video_id": video_id})


def subtitles_unavailable(video_id: str, reason: str = "") -> TranscriptError:
    return TranscriptError(
        "subtitles_unavailable",
        f"Subtitles unavailable for {video_id}: {reason}",
        _video_details(video_id, reason),
    )


def subtitle_parse_failed(video_id: str, reason: str = "") -> TranscriptError:
    return TranscriptError(
        "subtitle_parse_failed",
        f"Failed to parse subtitles for {video_id}: {reason}",
        _video_details(video_id, reason),
    )


def audio_download_failed(video_id: str, reason: str = "") -> TranscriptError:
    return TranscriptError(
        "audio_download_failed",
        f"Failed to download audio for {video_id}: {reason}",
        _video_details(video_id, reason),
    )


def asr_worker_unreachable(url: str) -> TranscriptError:
    return TranscriptError("asr_worker_unreachable", f"ASR worker unreachable at: {url}", {"url": url})


def asr_failed(video_id: str, reason: str = "") -> TranscriptError:
    return TranscriptError(
        "asr_failed",
        f"ASR transcription failed for {video_id}: {reason}",
        _video_details(video_id, reason),
    )


def db_write_failed(reason: str) -> TranscriptError:
    return TranscriptError("db_write_failed", f"Database write failed: {reason}", {"reason": reason})


def notes_write_failed(path: str, reason: str) -> TranscriptError:
    return TranscriptError(
        "notes_write_failed",
        f"Note export failed at {path}: {reason}",
        {"path": path, "reason": reason},
    )
