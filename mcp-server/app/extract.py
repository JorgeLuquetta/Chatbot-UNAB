"""Extracción de texto de documentos CCD (PDF / DOCX / TXT / MD)."""
from __future__ import annotations

from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n\n".join((page.extract_text() or "") for page in pdf.pages).strip()
    if suffix == ".docx":
        import docx

        d = docx.Document(str(path))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(parts).strip()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace").strip()
    raise ValueError(f"Formato no soportado: {suffix}")
