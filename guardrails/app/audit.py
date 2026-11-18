"""Auditoría de rechazos en guardrails_audit_log (Requirement 11.5)."""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

log = logging.getLogger("guardrails.audit")


@dataclass
class AuditLogEntry:
    session_id: str
    rejection_type: str          # input_injection | input_invalid | output_scope | output_prohibited
    rejection_reason: str
    raw_content_hash: str        # SHA-256 del contenido (nunca el contenido en claro)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, session_id: str, rejection_type: str, reason: str, content: str) -> "AuditLogEntry":
        return cls(session_id=session_id or "desconocida", rejection_type=rejection_type,
                   rejection_reason=reason or "sin motivo", raw_content_hash=sha256(content))


def sha256(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


class AuditSink(Protocol):
    async def write(self, entry: AuditLogEntry) -> None: ...


class MemoryAuditSink:
    def __init__(self) -> None:
        self.entries: list[AuditLogEntry] = []

    async def write(self, entry: AuditLogEntry) -> None:
        self.entries.append(entry)


class PostgresAuditSink:
    def __init__(self, dsn: str, ssl: str | None) -> None:
        self.dsn, self.ssl, self._pool = dsn, ssl, None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5, ssl=self.ssl,
                                                   statement_cache_size=0, command_timeout=5)
        return self._pool

    async def write(self, entry: AuditLogEntry) -> None:
        try:
            pool = await self._get_pool()
            await pool.execute(
                "INSERT INTO guardrails_audit_log (id, timestamp, session_id, rejection_type, rejection_reason, "
                "raw_content_hash) VALUES ($1, $2, $3, $4, $5, $6)",
                entry.id, entry.timestamp, entry.session_id, entry.rejection_type,
                entry.rejection_reason, entry.raw_content_hash,
            )
        except Exception:
            # La auditoría no debe tumbar la validación: se deja rastro en el log del contenedor.
            log.exception("No se pudo escribir en guardrails_audit_log: %s", entry)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()


class LoggingAuditSink:
    async def write(self, entry: AuditLogEntry) -> None:
        log.warning("RECHAZO %s session=%s motivo=%s hash=%s", entry.rejection_type, entry.session_id,
                    entry.rejection_reason, entry.raw_content_hash)


def default_sink() -> AuditSink:
    dsn = os.getenv("SUPABASE_DB_URL", "")
    if not dsn:
        log.warning("SUPABASE_DB_URL no definida: la auditoría solo se escribirá en el log")
        return LoggingAuditSink()
    ssl_env = os.getenv("DB_SSL", "require")
    return PostgresAuditSink(dsn, None if ssl_env in ("", "disable", "false") else ssl_env)
