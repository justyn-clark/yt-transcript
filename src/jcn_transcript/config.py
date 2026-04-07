"""Configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "JCN_TRANSCRIPT_", "env_file": ".env"}

    # Postgres
    database_url: str = "postgresql+asyncpg://justin@localhost:5432/jcn_transcript"
    database_url_sync: str = "postgresql://justin@localhost:5432/jcn_transcript"

    # Obsidian vault
    vault_path: Path = Path.home() / "Documents" / "Justyn Clark Network" / "REPOS" / "jcn-obsidian-vault"
    vault_transcript_dir: str = "Inbox/Transcripts/YouTube"

    # Studio ASR worker
    asr_worker_url: str = "http://studio.local:8787"
    asr_worker_timeout: int = 300

    # Temp files
    tmp_dir: Path = Path("/tmp/jcn-transcript")

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8420

    # Embedding
    embeddings_enabled: bool = False
    embedding_model: str = ""
    embedding_dimension: int = 0


settings = Settings()
