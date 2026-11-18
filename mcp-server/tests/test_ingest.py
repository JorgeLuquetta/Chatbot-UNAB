"""Properties 9, 10, 11 y 12 (pipeline de ingesta)."""
import asyncio
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from app.chunking import _SimpleTokenizer, chunk_text, chunk_tokens
from app.embeddings import HashEmbedder
from app.ingest import ingest_documents, resolve_paths
from app.stores import InMemoryDocumentStore


# Feature: chatbot-apoyo-academico, Property 9: Chunks cumplen la restricción de tamaño y overlap
@given(tokens=st.lists(st.integers(0, 100_000), max_size=3000),
       max_tokens=st.integers(60, 600), overlap=st.integers(0, 59))
def test_property_9_chunk_size_and_overlap(tokens, max_tokens, overlap):
    chunks = chunk_tokens(tokens, max_tokens, overlap)
    assert all(1 <= len(c) <= max_tokens for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        if overlap:
            assert prev[-overlap:] == nxt[:overlap]
    # Reconstrucción sin pérdida
    rebuilt = list(chunks[0]) if chunks else []
    for c in chunks[1:]:
        rebuilt.extend(c[overlap:])
    assert rebuilt == list(tokens)


@given(tokens=st.lists(st.integers(0, 50), min_size=1, max_size=2000))
def test_property_9_default_parameters(tokens):
    chunks = chunk_tokens(tokens)  # 512 / 50
    assert all(len(c) <= 512 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert prev[-50:] == nxt[:50]


docs_st = st.dictionaries(
    keys=st.text(alphabet="abcdefghij", min_size=1, max_size=8).map(lambda s: s + ".txt"),
    values=st.text(alphabet="abcdefghij áéí.,\n", min_size=1, max_size=3000).filter(str.strip),
    min_size=1, max_size=8,
)


def _run(docs: dict[str, str], failing: set[str] = frozenset(), store_fail: set[str] = frozenset()):
    class FlakyEmbedder(HashEmbedder):
        async def embed(self, texts):
            if any(t.startswith("FAIL") for t in texts):
                raise RuntimeError("API de embeddings no disponible")
            return await super().embed(texts)

    contents = {name: ("FAIL " + text if name in failing else text) for name, text in docs.items()}
    store = InMemoryDocumentStore(fail_on=set(store_fail))
    report = asyncio.run(ingest_documents(
        [Path(n) for n in contents], store, FlakyEmbedder(dim=32),
        extractor=lambda p: contents[p.name], tokenizer=_SimpleTokenizer(), max_tokens=64, overlap=8,
    ))
    return report, store


# Feature: chatbot-apoyo-academico, Property 10: Cardinalidad embeddings = cardinalidad chunks
@given(docs=docs_st)
def test_property_10_one_embedding_per_chunk(docs):
    report, store = _run(docs)
    assert report.total_embeddings == report.total_chunks == len(store.rows)


# Feature: chatbot-apoyo-academico, Property 11: Round-trip de almacenamiento de chunks
@given(docs=docs_st)
def test_property_11_roundtrip(docs):
    report, store = _run(docs)
    tok = _SimpleTokenizer()
    for name, text in docs.items():
        expected = chunk_text(text, 64, 8, tok)
        for i, piece in enumerate(expected):
            stored = asyncio.run(store.get_chunk(name, i))
            assert stored is not None and stored.content == piece and stored.total_chunks == len(expected)


# Feature: chatbot-apoyo-academico, Property 12: Tolerancia a errores en pipeline de ingesta
@given(docs=docs_st, data=st.data())
def test_property_12_error_tolerance(docs, data):
    names = sorted(docs)
    failing = set(data.draw(st.lists(st.sampled_from(names), unique=True)))
    emb_fail = {n for n in failing if data.draw(st.booleans())}
    store_fail = failing - emb_fail
    report, store = _run(docs, emb_fail, store_fail)
    assert report.total_documents == len(names)
    assert report.processed_documents == len(names) - len(failing)
    assert len(report.errors) == len(failing)
    assert {e.document_name for e in report.errors} == failing
    assert {n for (n, _) in store.rows} == set(names) - failing


def test_resolve_paths_blocks_traversal(tmp_path):
    (tmp_path / "plan.txt").write_text("hola")
    assert resolve_paths([], tmp_path) == [tmp_path / "plan.txt"]
    try:
        resolve_paths(["../etc/passwd"], tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("debió rechazar ruta fuera del directorio")


def test_ingest_real_docx(tmp_path):
    import docx

    d = docx.Document()
    for i in range(200):
        d.add_paragraph(f"Competencia {i}: el estudiante analiza datos y diseña modelos predictivos.")
    path = tmp_path / "ccd.docx"
    d.save(path)
    store = InMemoryDocumentStore()
    report = asyncio.run(ingest_documents([path], store, HashEmbedder(dim=16), tokenizer=_SimpleTokenizer()))
    assert report.processed_documents == 1 and report.total_chunks > 1 and not report.errors
