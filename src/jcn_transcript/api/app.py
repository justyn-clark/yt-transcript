"""FastAPI application for jcn-transcript."""

import logging
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..db.crud import find_by_id, find_by_source
from ..db.engine import async_session
from ..lib.errors import TranscriptError
from ..lib.pipeline import PipelineOptions, ingest_youtube_url

logger = logging.getLogger(__name__)

app = FastAPI(
    title="JCN Transcript",
    version="0.1.0",
    description="Local-first YouTube transcript ingestion service",
)


class YouTubeIngestRequest(BaseModel):
    url: str
    persist_to_vault: bool = True
    persist_to_pg: bool = True
    embed: bool = False
    open_note: bool = False
    force_asr: bool = False


class IngestResponse(BaseModel):
    id: str
    source_type: str
    source_id: str
    status: str
    retrieval_method: str
    language: str
    vault_path: str | None
    segment_count: int
    title: str
    url: str


class ErrorResponse(BaseModel):
    error_type: str
    message: str
    details: dict = {}


class MediaItemResponse(BaseModel):
    id: str
    source_type: str
    source_id: str
    url: str
    title: str | None
    channel_name: str | None
    language: str | None
    retrieval_method: str
    transcript_status: str
    vault_path: str | None
    segment_count: int
    quality_flags: list | None


@app.post("/v1/transcripts/youtube", response_model=IngestResponse)
async def ingest_youtube(req: YouTubeIngestRequest):
    """Ingest a YouTube video transcript."""
    options = PipelineOptions(
        persist_to_vault=req.persist_to_vault,
        persist_to_pg=req.persist_to_pg,
        embed=req.embed,
        open_note=req.open_note,
        force_asr=req.force_asr,
    )
    try:
        result = await ingest_youtube_url(req.url, options)
        return IngestResponse(
            id=result.id,
            source_type=result.source_type,
            source_id=result.source_id,
            status=result.status,
            retrieval_method=result.retrieval_method,
            language=result.language,
            vault_path=result.vault_path,
            segment_count=result.segment_count,
            title=result.title,
            url=result.url,
        )
    except TranscriptError as e:
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        logger.exception("Unexpected error during ingestion")
        raise HTTPException(status_code=500, detail={"error_type": "unexpected", "message": str(e)})


@app.get("/v1/transcripts/{item_id}", response_model=MediaItemResponse)
async def get_transcript(item_id: str):
    """Get a transcript record by ID."""
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    async with async_session() as session:
        item = await find_by_id(session, uid)
        if not item:
            raise HTTPException(status_code=404, detail="Not found")

        # Load segments count
        await session.refresh(item, ["segments"])

        return MediaItemResponse(
            id=str(item.id),
            source_type=item.source_type,
            source_id=item.source_id,
            url=item.url,
            title=item.title,
            channel_name=item.channel_name,
            language=item.language,
            retrieval_method=item.retrieval_method,
            transcript_status=item.transcript_status,
            vault_path=item.transcript_markdown_path,
            segment_count=len(item.segments),
            quality_flags=item.quality_flags,
        )


@app.get("/v1/transcripts/by-source/{video_id}", response_model=MediaItemResponse)
async def get_transcript_by_source(video_id: str):
    """Get a transcript record by YouTube video ID."""
    async with async_session() as session:
        item = await find_by_source(session, "youtube", video_id)
        if not item:
            raise HTTPException(status_code=404, detail="Not found")

        await session.refresh(item, ["segments"])

        return MediaItemResponse(
            id=str(item.id),
            source_type=item.source_type,
            source_id=item.source_id,
            url=item.url,
            title=item.title,
            channel_name=item.channel_name,
            language=item.language,
            retrieval_method=item.retrieval_method,
            transcript_status=item.transcript_status,
            vault_path=item.transcript_markdown_path,
            segment_count=len(item.segments),
            quality_flags=item.quality_flags,
        )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "jcn-transcript"}
