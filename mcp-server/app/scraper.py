"""Scraper one-shot de noticias UNAB (Requirement 9)."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Sequence
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pydantic import BaseModel

from .models import Article, ScraperReport
from .stores import NewsStore

log = logging.getLogger("scraper")

Fetcher = Callable[[str], Awaitable[str]]


class SourceConfig(BaseModel):
    url: str
    item_selector: str = "article"
    title_selector: str = "h1, h2, h3, h4"
    date_selector: str = "time, .date, .fecha, [class*=date], [class*=fecha]"
    summary_selector: str = "p, .summary, .resumen, .excerpt"
    link_selector: str = "a[href]"


def load_sources(path: Path) -> list[SourceConfig]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [SourceConfig(**s) if isinstance(s, dict) else SourceConfig(url=s) for s in data.get("sources", [])]


def make_http_fetcher(timeout_s: float = 10.0) -> Fetcher:
    import httpx

    async def fetch(url: str) -> str:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True,
                                     headers={"User-Agent": "UNAB-Chatbot-Scraper/1.0 (proyecto academico)"}) as c:
            r = await c.get(url)
            r.raise_for_status()
            return r.text

    return fetch


_MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
           "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def parse_date(text: str | None) -> datetime | None:
    """Entiende ISO-8601, dd/mm/aaaa y '12 de noviembre de 2026' / 'noviembre 12, 2026'."""
    if not text:
        return None
    t = text.strip()
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    low = _strip_accents(t.lower())
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", low)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)(?:\s+de)?\s+(\d{4})", low) or None
    if m:
        d, mon, y = int(m.group(1)), m.group(2), int(m.group(3))
    else:
        m = re.search(r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})", low)
        if not m:
            return None
        mon, d, y = m.group(1), int(m.group(2)), int(m.group(3))
    if mon not in _MONTHS:
        return None
    try:
        return datetime(y, _MONTHS[mon], d, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_articles(html: str, source: SourceConfig) -> list[Article]:
    soup = BeautifulSoup(html, "html.parser")
    articles: list[Article] = []
    for item in soup.select(source.item_selector):
        title_el = item.select_one(source.title_selector)
        link_el = item.select_one(source.link_selector)
        if title_el is None or link_el is None:
            continue
        title = title_el.get_text(" ", strip=True)
        href = link_el.get("href", "").strip()
        if not title or not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        date_el = item.select_one(source.date_selector)
        raw_date = (date_el.get("datetime") or date_el.get_text(" ", strip=True)) if date_el else None
        published = parse_date(raw_date) or datetime.now(timezone.utc)
        summary_el = item.select_one(source.summary_selector)
        summary = summary_el.get_text(" ", strip=True) if summary_el else ""
        articles.append(Article(title=title[:500], published_at=published,
                                summary=(summary or title)[:2000], source_url=urljoin(source.url, href)))
    return articles


async def run_news_scraper(sources: Sequence[SourceConfig], store: NewsStore, fetcher: Fetcher) -> ScraperReport:
    report = ScraperReport(total_sources=len(sources))
    collected: dict[str, Article] = {}
    for src in sources:
        try:
            html = await fetcher(src.url)
        except Exception as exc:  # URL inalcanzable: registrar y continuar
            log.warning("Fuente inalcanzable %s: %s", src.url, exc)
            report.failed_sources.append(src.url)
            continue
        found = parse_articles(html, src)
        report.total_extracted += len(found)
        for a in found:
            collected.setdefault(a.source_url, a)  # dedup dentro de la misma corrida

    batch = list(collected.values())
    existing = await store.existing_urls([a.source_url for a in batch])
    new = [a for a in batch if a.source_url not in existing]
    report.total_inserted = await store.insert(new) if new else 0
    report.skipped_duplicates = report.total_extracted - report.total_inserted
    log.info("Scraper: fuentes=%d extraidos=%d insertados=%d duplicados=%d fallidas=%s",
             report.total_sources, report.total_extracted, report.total_inserted,
             report.skipped_duplicates, report.failed_sources)
    return report
