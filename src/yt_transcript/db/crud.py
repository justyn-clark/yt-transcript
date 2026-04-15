"""Database CRUD operations."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..lib.models import TranscriptResult
from .tables import MediaItem, TranscriptSegment


async def find_by_source(session: AsyncSession, source_type: str, source_id: str) -> MediaItem | None:
    """Find an existing media item by source type and ID."""
    stmt = (
        select(MediaItem)
        .where(
            MediaItem.source_type == source_type,
            MediaItem.source_id == source_id,
        )
        .options(selectinload(MediaItem.segments))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def find_by_id(session: AsyncSession, item_id: uuid.UUID) -> MediaItem | None:
    """Find a media item by its UUID."""
    stmt = select(MediaItem).where(MediaItem.id == item_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _merge_payload(
    existing: dict[str, Any] | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Merge structured payload data without losing previously stored context."""
    if existing is None:
        return None if extra is None else dict(extra)
    if extra is None:
        return dict(existing)

    merged = dict(existing)
    for key, value in extra.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_payload(current, value)
        else:
            merged[key] = value
    return merged


async def upsert_transcript(
    session: AsyncSession,
    tr: TranscriptResult,
    *,
    raw_payload: dict[str, Any] | None = None,
) -> MediaItem:
    """Insert or update a transcript record and its segments."""
    existing = await find_by_source(session, "youtube", tr.video_id)

    now = datetime.now(timezone.utc)

    if existing:
        # Update existing record
        existing.title = tr.title or existing.title
        existing.channel_name = tr.channel_name or existing.channel_name
        existing.language = tr.language
        existing.retrieval_method = tr.retrieval_method
        existing.transcript_status = "done"
        existing.transcript_text = tr.full_text
        existing.quality_flags = tr.quality_flags
        if raw_payload is not None:
            existing.raw_payload = _merge_payload(existing.raw_payload, raw_payload)
        existing.updated_at = now
        if tr.duration_seconds:
            existing.duration_seconds = tr.duration_seconds
        if tr.published_at:
            existing.published_at = tr.published_at

        # Delete old segments and re-insert
        await session.execute(delete(TranscriptSegment).where(TranscriptSegment.media_item_id == existing.id))
        await session.flush()
        existing.segments.clear()

        for seg in tr.segments:
            existing.segments.append(
                TranscriptSegment(
                    media_item_id=existing.id,
                    idx=seg.idx,
                    start_seconds=seg.start_seconds,
                    end_seconds=seg.end_seconds,
                    text=seg.text,
                    tokens_estimate=len(seg.text.split()),
                )
            )

        await session.commit()
        return existing

    # New record
    item = MediaItem(
        source_type="youtube",
        source_id=tr.video_id,
        url=tr.url,
        title=tr.title,
        channel_name=tr.channel_name,
        published_at=tr.published_at,
        duration_seconds=tr.duration_seconds,
        language=tr.language,
        retrieval_method=tr.retrieval_method,
        transcript_status="done",
        transcript_text=tr.full_text,
        raw_payload=_merge_payload(None, raw_payload),
        quality_flags=tr.quality_flags,
        created_at=now,
        updated_at=now,
    )
    session.add(item)
    await session.flush()

    for seg in tr.segments:
        session.add(
            TranscriptSegment(
                media_item_id=item.id,
                idx=seg.idx,
                start_seconds=seg.start_seconds,
                end_seconds=seg.end_seconds,
                text=seg.text,
                tokens_estimate=len(seg.text.split()),
            )
        )

    await session.commit()
    return item


async def set_status(session: AsyncSession, item_id: uuid.UUID, status: str) -> None:
    """Update the transcript status."""
    item = await find_by_id(session, item_id)
    if item:
        item.transcript_status = status
        item.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def set_notes_path(session: AsyncSession, item_id: uuid.UUID, notes_path: str) -> None:
    """Record the markdown note path."""
    item = await find_by_id(session, item_id)
    if item:
        item.transcript_markdown_path = notes_path
        item.updated_at = datetime.now(timezone.utc)
        await session.commit()
