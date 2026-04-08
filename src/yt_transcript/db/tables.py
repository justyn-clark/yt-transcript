"""SQLAlchemy ORM models for transcript storage."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MediaItem(Base):
    __tablename__ = "media_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    channel_name: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(Text)
    retrieval_method: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    transcript_text: Mapped[str | None] = mapped_column(Text)
    transcript_markdown_path: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    quality_flags: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="media_item", cascade="all, delete-orphan", order_by="TranscriptSegment.idx"
    )
    embeddings: Mapped[list["TranscriptEmbedding"]] = relationship(
        back_populates="media_item", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_media_items_source"),)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[float] = mapped_column(Numeric, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Numeric, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_estimate: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    media_item: Mapped["MediaItem"] = relationship(back_populates="segments")

    __table_args__ = (UniqueConstraint("media_item_id", "idx", name="uq_transcript_segments_media_idx"),)


class TranscriptEmbedding(Base):
    __tablename__ = "transcript_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False
    )
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transcript_segments.id", ondelete="CASCADE")
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Embedding stored as JSONB array until pgvector is confirmed
    embedding: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    media_item: Mapped["MediaItem"] = relationship(back_populates="embeddings")
