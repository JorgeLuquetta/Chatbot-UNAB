"""Configuración leída desde variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_key: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))
    # asyncpg necesita la cadena de conexión PostgreSQL (no la URL REST de Supabase)
    db_url: str = field(default_factory=lambda: os.getenv("SUPABASE_DB_URL", ""))
    db_ssl: str = field(default_factory=lambda: os.getenv("DB_SSL", "require"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    embedding_dim: int = 1536
    embedding_batch_size: int = 100
    chunk_max_tokens: int = 512
    chunk_overlap: int = 50
    ccd_data_dir: Path = field(default_factory=lambda: Path(os.getenv("CCD_DATA_DIR", "/data/ccd")))
    sources_file: Path = field(default_factory=lambda: Path(os.getenv("NEWS_SOURCES_FILE", "/app/sources.json")))
    http_timeout_s: float = 10.0
    host: str = field(default_factory=lambda: os.getenv("MCP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("MCP_PORT", "8000")))


settings = Settings()
