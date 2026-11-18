"""Pipeline de ingesta: extracción → chunking → embeddings → pgvector (Requirement 8)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Sequence

from .chunking import Tokenizer, chunk_text
from .embeddings import Embedder
from .extract import SUPPORTED, extract_text
from .models import ChunkRecord, IngestionError, IngestionReport
from .stores import DocumentStore

log = logging.getLogger("ingesta")


def resolve_paths(file_paths: Sequence[str], base_dir: Path) -> list[Path]:
    """Restringe la ingesta a archivos dentro de `base_dir`. Lista vacía = todos los soportados."""
    base = base_dir.resolve()
    if not file_paths:
        return sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    out = []
    for raw in file_paths:
        p = Path(raw)
        p = (p if p.is_absolute() else base / p).resolve()
        if base not in p.parents and p != base:
            raise ValueError(f"Ruta fuera del directorio permitido: {raw}")
        out.append(p)
    return out


async def ingest_documents(
    paths: Sequence[Path],
    store: DocumentStore,
    embedder: Embedder,
    *,
    extractor: Callable[[Path], str] = extract_text,
    tokenizer: Tokenizer | None = None,
    max_tokens: int = 512,
    overlap: int = 50,
) -> IngestionReport:
    report = IngestionReport(total_documents=len(paths))
    for path in paths:
        name = path.name
        try:
            text = extractor(path)
            if not text.strip():
                raise ValueError("el documento no contiene texto extraíble")
            pieces = chunk_text(text, max_tokens, overlap, tokenizer)
            embeddings = await embedder.embed(pieces)  # internamente en lotes de 100
            if len(embeddings) != len(pieces):
                raise RuntimeError(f"{len(pieces)} chunks pero {len(embeddings)} embeddings")
            records = [
                ChunkRecord(document_name=name, chunk_index=i, total_chunks=len(pieces),
                            content=piece, embedding=emb)
                for i, (piece, emb) in enumerate(zip(pieces, embeddings))
            ]
            await store.upsert_chunks(records)
        except Exception as exc:  # un documento fallido no detiene el proceso
            log.error("Error ingiriendo %s: %s", name, exc)
            report.errors.append(IngestionError(document_name=name, error_message=str(exc)))
            continue
        report.processed_documents += 1
        report.total_chunks += len(records)
        report.total_embeddings += len(embeddings)
        log.info("%s: %d chunks almacenados", name, len(records))

    log.info("Ingesta finalizada: documentos=%d procesados=%d chunks=%d embeddings=%d errores=%d",
             report.total_documents, report.processed_documents, report.total_chunks,
             report.total_embeddings, len(report.errors))
    return report
