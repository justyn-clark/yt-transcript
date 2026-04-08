"""yt-dlp based subtitle retrieval and metadata extraction."""

import json
import logging
import re
import subprocess
from pathlib import Path

from ..config import settings
from .models import Segment, TranscriptResult, VideoMetadata

logger = logging.getLogger(__name__)


def fetch_metadata(video_id: str) -> VideoMetadata | None:
    """Fetch video metadata via yt-dlp without downloading."""
    url = f"https://youtu.be/{video_id}"
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-playlist",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("yt-dlp metadata failed for %s: %s", video_id, result.stderr[:200])
            return None

        data = json.loads(result.stdout)
        from datetime import datetime

        published_at = None
        upload_date = data.get("upload_date")
        if upload_date and len(upload_date) == 8:
            try:
                published_at = datetime.strptime(upload_date, "%Y%m%d")
            except ValueError:
                pass

        return VideoMetadata(
            video_id=video_id,
            title=data.get("title", ""),
            channel_name=data.get("channel", "") or data.get("uploader", ""),
            published_at=published_at,
            duration_seconds=data.get("duration"),
            language=data.get("language") or "en",
        )
    except subprocess.TimeoutExpired:
        logger.warning("yt-dlp metadata timed out for %s", video_id)
        return None
    except Exception:
        logger.warning("yt-dlp metadata error for %s", video_id, exc_info=True)
        return None


def fetch_subtitles(video_id: str) -> TranscriptResult | None:
    """Fetch subtitles via yt-dlp as a fallback when youtube-transcript-api fails."""
    url = f"https://youtu.be/{video_id}"
    tmp_dir = settings.tmp_dir / video_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    quality_flags: list[str] = []
    retrieval_method = "captions"

    # Try manual subtitles first
    sub_file = _download_subs(url, tmp_dir, auto=False)
    if sub_file is None:
        # Try auto-generated
        sub_file = _download_subs(url, tmp_dir, auto=True)
        if sub_file is not None:
            retrieval_method = "auto_captions"
            quality_flags.append("used_auto_captions")
            quality_flags.append("subtitle_parse_fallback")

    if sub_file is None:
        logger.info("No subtitles available via yt-dlp for %s", video_id)
        return None

    quality_flags.append("subtitle_parse_fallback")
    segments = _parse_vtt(sub_file)

    if not segments:
        logger.warning("Failed to parse subtitle file for %s", video_id)
        return None

    full_text = " ".join(s.text for s in segments)

    if len(segments) < 3:
        quality_flags.append("transcript_short")

    return TranscriptResult(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title="",
        channel_name="",
        language="en",
        retrieval_method=retrieval_method,
        segments=segments,
        full_text=full_text,
        quality_flags=list(set(quality_flags)),
    )


def download_audio(video_id: str) -> Path | None:
    """Download audio only for ASR fallback."""
    url = f"https://youtu.be/{video_id}"
    tmp_dir = settings.tmp_dir / video_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / "audio.wav"

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--audio-format",
                "wav",
                "--audio-quality",
                "0",
                "-o",
                str(out_path),
                "--no-playlist",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning("Audio download failed for %s: %s", video_id, result.stderr[:200])
            return None

        # yt-dlp may append extension
        if out_path.exists():
            return out_path
        wav_path = out_path.with_suffix(".wav")
        if wav_path.exists():
            return wav_path

        # Check for any audio file in tmp_dir
        for f in tmp_dir.iterdir():
            if f.suffix in (".wav", ".m4a", ".mp3", ".opus", ".webm"):
                return f

        return None
    except subprocess.TimeoutExpired:
        logger.warning("Audio download timed out for %s", video_id)
        return None
    except Exception:
        logger.warning("Audio download error for %s", video_id, exc_info=True)
        return None


def _download_subs(url: str, tmp_dir: Path, auto: bool) -> Path | None:
    """Download subtitle file via yt-dlp."""
    args = [
        "yt-dlp",
        "--skip-download",
        "--no-playlist",
        "--sub-lang",
        "en",
        "--sub-format",
        "vtt",
        "--convert-subs",
        "vtt",
        "-o",
        str(tmp_dir / "subs"),
    ]
    if auto:
        args.append("--write-auto-sub")
    else:
        args.append("--write-sub")
    args.append(url)

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, Exception):
        return None

    # Find the subtitle file
    for f in tmp_dir.iterdir():
        if f.suffix == ".vtt":
            return f
    return None


def _parse_vtt(path: Path) -> list[Segment]:
    """Parse a VTT subtitle file into segments."""
    text = path.read_text(encoding="utf-8", errors="replace")
    segments: list[Segment] = []
    idx = 0

    # Match timestamp lines: 00:00:01.000 --> 00:00:04.000
    timestamp_re = re.compile(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})")
    # Strip VTT tags
    tag_re = re.compile(r"<[^>]+>")

    lines = text.split("\n")
    i = 0
    prev_text: str | None = None

    while i < len(lines):
        m = timestamp_re.match(lines[i].strip())
        if m:
            start = _vtt_time_to_seconds(m.group(1))
            end = _vtt_time_to_seconds(m.group(2))
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() and not timestamp_re.match(lines[i].strip()):
                line = tag_re.sub("", lines[i].strip())
                if line:
                    text_lines.append(line)
                i += 1
            segment_text = " ".join(text_lines).strip()
            # Only skip immediately adjacent identical segments (VTT overlap artifact)
            if segment_text and segment_text != prev_text:
                seg = Segment(idx=idx, start_seconds=round(start, 2), end_seconds=round(end, 2), text=segment_text)
                segments.append(seg)
                idx += 1
            prev_text = segment_text
        else:
            i += 1

    return segments


def _vtt_time_to_seconds(ts: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm) to seconds."""
    parts = ts.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s
