"""Generación de embeddings: Ollama local (por defecto), OpenAI o hash determinista (tests). Columna de 1536 dims."""
from __future__ import annotations

import hashlib
import math
from typing import Protocol, Sequence

from .config import settings


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 batch_size: int | None = None) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
        self._model = model or settings.embedding_model
        self._batch = batch_size or settings.embedding_batch_size

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self._batch):  # lotes de 100
            batch = list(texts[i:i + self._batch])
            resp = await self._client.embeddings.create(model=self._model, input=batch)
            vectors.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
        if len(vectors) != len(texts):
            raise RuntimeError(f"Se esperaban {len(texts)} embeddings y llegaron {len(vectors)}")
        return vectors


class OllamaEmbedder:
    """Embeddings locales y gratuitos con Ollama (por defecto granite-embedding:278m, multilingüe, 768 dims).

    La columna es vector(1536); los vectores más cortos se rellenan con ceros. El relleno no cambia
    la similitud coseno, así que la búsqueda es equivalente y se puede volver a OpenAI sin migrar el esquema.
    """

    def __init__(self, base_url: str | None = None, model: str | None = None, dim: int | None = None,
                 batch_size: int = 16, timeout_s: float = 120.0) -> None:
        self._url = (base_url or settings.ollama_url).rstrip("/") + "/api/embed"
        self._model = model or settings.ollama_embed_model
        self._dim = dim or settings.embedding_dim
        self._batch = batch_size
        self._timeout = timeout_s

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import httpx

        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for i in range(0, len(texts), self._batch):
                batch = list(texts[i:i + self._batch])
                resp = await client.post(self._url, json={"model": self._model, "input": batch, "keep_alive": -1})
                resp.raise_for_status()
                vectors.extend(resp.json()["embeddings"])
        if len(vectors) != len(texts):
            raise RuntimeError(f"Se esperaban {len(texts)} embeddings y llegaron {len(vectors)}")
        return [self._pad(v) for v in vectors]

    def _pad(self, vec: Sequence[float]) -> list[float]:
        if len(vec) > self._dim:
            raise RuntimeError(f"El modelo devuelve {len(vec)} dimensiones; la columna admite {self._dim}")
        return list(vec) + [0.0] * (self._dim - len(vec))


class HashEmbedder:
    """Embedder determinista sin red, para tests y desarrollo local."""

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in (text.lower().split() or [""]):
            h = int.from_bytes(hashlib.sha256(word.encode()).digest()[:8], "big")
            vec[h % self.dim] += 1.0 if (h >> 63) == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def to_pgvector(vec: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.7g}" for v in vec) + "]"
