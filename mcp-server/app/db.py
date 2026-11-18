"""Pool de conexiones asyncpg hacia Supabase PostgreSQL."""
from __future__ import annotations

import asyncio

import asyncpg

from .config import settings

_pool: asyncpg.Pool | None = None
_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    global _pool
    async with _lock:
        if _pool is None:
            if not settings.db_url:
                raise RuntimeError("SUPABASE_DB_URL no está configurada")
            ssl = None if settings.db_ssl in ("", "disable", "false") else settings.db_ssl
            _pool = await asyncpg.create_pool(
                dsn=settings.db_url,
                min_size=1,
                max_size=10,
                ssl=ssl,
                statement_cache_size=0,  # compatible con el pooler de Supabase
                command_timeout=15,
            )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
