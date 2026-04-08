"""Configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "YT_TRANSCRIPT_", "env_file": ".env", "extra": "ignore"}

    # Postgres
    database_url: str = "postgresql+asyncpg://localhost:5432/yt_transcript"
    database_url_sync: str = "postgresql://localhost:5432/yt_transcript"

    # Markdown note export (optional - disabled when not set)
    notes_dir: Path | None = None
    notes_subdir: str = "Transcripts/YouTube"

    # Studio ASR worker
    asr_worker_url: str = "http://localhost:8787"
    asr_worker_timeout: int = 300

    # Temp files
    tmp_dir: Path = Path("/tmp/yt-transcript")

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8420

    @property
    def notes_enabled(self) -> bool:
        """Note export is enabled when a notes directory is configured."""
        return self.notes_dir is not None


settings = Settings()
