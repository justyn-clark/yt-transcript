"""Caption retrieval via youtube-transcript-api."""

import logging

from youtube_transcript_api import YouTubeTranscriptApi

from .models import Segment, TranscriptResult

logger = logging.getLogger(__name__)

PREFERRED_LANGS = ["en", "en-US", "en-GB"]


def fetch_captions(video_id: str) -> TranscriptResult | None:
    """Attempt to fetch captions using youtube-transcript-api.

    Tries manual captions first, then auto-generated.
    Returns None if no captions are available.
    """
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
    except Exception:
        logger.info("No transcripts available via API for %s", video_id)
        return None

    # Try manual captions first
    retrieval_method = "captions"
    quality_flags: list[str] = []
    transcript = None

    try:
        transcript = transcript_list.find_manually_created_transcript(PREFERRED_LANGS)
    except Exception:
        pass

    if transcript is None:
        # Try any manually created English variant
        for t in transcript_list:
            if not t.is_generated and t.language_code.startswith("en"):
                transcript = t
                break

    if transcript is None:
        # Fall back to auto-generated
        try:
            transcript = transcript_list.find_generated_transcript(PREFERRED_LANGS)
            retrieval_method = "auto_captions"
            quality_flags.append("used_auto_captions")
        except Exception:
            pass

    if transcript is None:
        # Try any auto-generated English variant
        for t in transcript_list:
            if t.is_generated and t.language_code.startswith("en"):
                transcript = t
                retrieval_method = "auto_captions"
                quality_flags.append("used_auto_captions")
                break

    if transcript is None:
        logger.info("No English transcript found for %s", video_id)
        return None

    try:
        entries = transcript.fetch()
    except Exception:
        logger.warning("Failed to fetch transcript content for %s", video_id, exc_info=True)
        return None

    language = transcript.language_code
    segments = _entries_to_segments(entries)
    full_text = " ".join(s.text for s in segments)

    if len(segments) < 3:
        quality_flags.append("transcript_short")

    return TranscriptResult(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title="",
        channel_name="",
        language=language,
        retrieval_method=retrieval_method,
        segments=segments,
        full_text=full_text,
        quality_flags=quality_flags,
    )


def _entries_to_segments(entries) -> list[Segment]:
    """Convert youtube-transcript-api FetchedTranscript to Segment objects."""
    segments = []
    for i, entry in enumerate(entries):
        text = entry.text.strip()
        if not text:
            continue
        start = float(entry.start)
        duration = float(entry.duration)
        segments.append(
            Segment(
                idx=i,
                start_seconds=round(start, 2),
                end_seconds=round(start + duration, 2),
                text=text,
            )
        )
    return segments
