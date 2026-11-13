"""Properties 13, 14 y 15 (scraper de noticias) con HTTP simulado."""
import asyncio
from datetime import datetime, timezone

from hypothesis import given
from hypothesis import strategies as st

from app.scraper import SourceConfig, parse_date, run_news_scraper
from app.stores import InMemoryNewsStore

safe_text = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ÁÉÍÓÚáéíóúñ0123456789", min_size=1, max_size=40).filter(str.strip)


def _html(items):
    body = "".join(
        f'<article><h2>{t}</h2><time datetime="2026-11-{(i % 28) + 1:02d}">x</time>'
        f'<p>{s}</p><a href="/noticias/{slug}">ver</a></article>'
        for i, (t, s, slug) in enumerate(items)
    )
    return f"<html><body>{body}</body></html>"


item_st = st.tuples(safe_text, safe_text, st.text(alphabet="abcdefghij0123456789-", min_size=1, max_size=15))
site_st = st.lists(item_st, max_size=6)


def _fetcher(pages: dict[str, str], down: set[str]):
    async def fetch(url):
        if url in down:
            raise ConnectionError("host inalcanzable")
        return pages[url]
    return fetch


def _sources(n):
    return [SourceConfig(url=f"https://unab{i}.test/noticias") for i in range(n)]


# Feature: chatbot-apoyo-academico, Property 13: Artículos almacenados contienen todos los campos requeridos
@given(sites=st.lists(site_st, min_size=1, max_size=4))
def test_property_13_required_fields(sites):
    srcs = _sources(len(sites))
    pages = {s.url: _html(items) for s, items in zip(srcs, sites)}
    store = InMemoryNewsStore()
    asyncio.run(run_news_scraper(srcs, store, _fetcher(pages, set())))
    for a in store.rows.values():
        assert a.title and a.summary and a.source_url and a.published_at is not None


# Feature: chatbot-apoyo-academico, Property 14: Tolerancia a errores en el scraper
@given(sites=st.lists(site_st, min_size=1, max_size=6), data=st.data())
def test_property_14_unreachable_sources(sites, data):
    srcs = _sources(len(sites))
    pages = {s.url: _html(items) for s, items in zip(srcs, sites)}
    down = set(data.draw(st.lists(st.sampled_from([s.url for s in srcs]), unique=True)))
    report = asyncio.run(run_news_scraper(srcs, InMemoryNewsStore(), _fetcher(pages, down)))
    assert sorted(report.failed_sources) == sorted(down)
    expected = sum(len(items) for s, items in zip(srcs, sites) if s.url not in down)
    assert report.total_extracted == expected


# Feature: chatbot-apoyo-academico, Property 15: Idempotencia del scraper (deduplicación por source_url)
@given(sites=st.lists(site_st, min_size=1, max_size=4))
def test_property_15_idempotent(sites):
    srcs = _sources(len(sites))
    pages = {s.url: _html(items) for s, items in zip(srcs, sites)}
    store = InMemoryNewsStore()
    asyncio.run(run_news_scraper(srcs, store, _fetcher(pages, set())))
    after_first = len(store.rows)
    second = asyncio.run(run_news_scraper(srcs, store, _fetcher(pages, set())))
    assert len(store.rows) == after_first
    assert second.total_inserted == 0


def test_parse_date_formats():
    assert parse_date("2026-11-12T10:00:00Z") == datetime(2026, 11, 12, 10, tzinfo=timezone.utc)
    assert parse_date("12/11/2026").date().isoformat() == "2026-11-12"
    assert parse_date("Publicado el 3 de marzo de 2026").month == 3
    assert parse_date("Noviembre 5, 2026").day == 5
    assert parse_date("sin fecha") is None
