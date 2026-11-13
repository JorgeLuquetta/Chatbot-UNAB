"""Chunking por tokens: máximo 512 tokens, overlap de 50 (Requirement 8.1)."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol, Sequence


class Tokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...
    def decode(self, tokens: Sequence[int]) -> str: ...


def chunk_tokens(tokens: Sequence[int], max_tokens: int = 512, overlap: int = 50) -> list[list[int]]:
    """Divide una secuencia de tokens en ventanas de `max_tokens` con `overlap` compartido.

    Garantías (Property 9):
      * cada chunk tiene 1..max_tokens tokens;
      * para chunks consecutivos, los últimos `overlap` tokens del anterior son el
        prefijo del siguiente;
      * la concatenación sin solapamiento reconstruye la secuencia original.
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens debe ser > 0")
    if not 0 <= overlap < max_tokens:
        raise ValueError("overlap debe estar en [0, max_tokens)")
    tokens = list(tokens)
    if not tokens:
        return []
    step = max_tokens - overlap
    chunks: list[list[int]] = []
    start = 0
    while True:
        chunks.append(tokens[start:start + max_tokens])
        if start + max_tokens >= len(tokens):
            break
        start += step
    return chunks


class _SimpleTokenizer:
    """Tokenizador de respaldo (palabras/puntuación) si tiktoken no está disponible."""

    _pattern = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}
        self._inverse: list[str] = []

    def encode(self, text: str) -> list[int]:
        out = []
        for piece in self._pattern.findall(text):
            if piece not in self._vocab:
                self._vocab[piece] = len(self._inverse)
                self._inverse.append(piece)
            out.append(self._vocab[piece])
        return out

    def decode(self, tokens: Sequence[int]) -> str:
        return "".join(self._inverse[t] for t in tokens)


@lru_cache(maxsize=1)
def get_tokenizer() -> Tokenizer:
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # sin red / sin caché: tokenizador aproximado
        return _SimpleTokenizer()


def chunk_text(text: str, max_tokens: int = 512, overlap: int = 50,
               tokenizer: Tokenizer | None = None) -> list[str]:
    tok = tokenizer or get_tokenizer()
    return [tok.decode(c) for c in chunk_tokens(tok.encode(text), max_tokens, overlap)]
