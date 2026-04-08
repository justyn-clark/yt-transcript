"""Domain models for transcript data (not ORM - pure data)."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Segment:
    idx: int
    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class VideoMetadata:
    video_id: str
    title: str = ""
    channel_name: str = ""
    published_at: datetime | None = None
    duration_seconds: int | None = None
    language: str = "en"


@dataclass
class TranscriptResult:
    video_id: str
    url: str
    title: str
    channel_name: str
    language: str
    retrieval_method: str  # captions | auto_captions | asr
    segments: list[Segment]
    full_text: str
    metadata: VideoMetadata | None = None
    quality_flags: list[str] = field(default_factory=list)
    duration_seconds: int | None = None
    published_at: datetime | None = None


@dataclass
class IngestResult:
    id: str
    source_type: str
    source_id: str
    status: str
    retrieval_method: str
    language: str
    segment_count: int
    title: str
    url: str
    db_status: str = "skipped"  # skipped | ok | failed
    notes_status: str = "skipped"  # skipped | ok | failed
    notes_path: str | None = None
