"""Scraper de noticias (Requirement 9).

Fuentes HTML (sitio de la UNAB, con selectores CSS) y RSS (Google News por tema). Cada noticia
se clasifica por palabras clave en: ingenieria-sistemas, tecnologia, educacion o general, y se
guarda con su fuente (source_name) y fecha de publicación. En las fuentes externas se descartan
las noticias "general": solo interesan las de educación, tecnología e ingeniería de sistemas.
n8n lo ejecuta cada 6 horas (workflow "Scraper de noticias").
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Awaitable, Callable, Sequence
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel

from .models import Article, ScraperReport
from .stores import NewsStore

log = logging.getLogger("scraper")

Fetcher = Callable[[str], Awaitable[str]]


class SourceConfig(BaseModel):
    url: str
    name: str = "UNAB"
    type: str = "html"                      # html | rss
    default_category: str = "general"       # si las palabras clave no deciden
    keep_general: bool = True               # False = descarta noticias que no sean de los 3 temas
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
# Abreviaturas (3 letras) en español e inglés: el sitio WordPress de la UNAB publica "Nov 17, 2026"
_MONTH_ABBR = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6, "jul": 7,
               "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}


def _month(name: str) -> int | None:
    return _MONTHS.get(name) or _MONTH_ABBR.get(name[:3])


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
    mo = _month(mon)
    if mo is None:
        return None
    try:
        return datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None


# Palabras clave (sin tildes, minúsculas). El orden importa: la categoría más específica primero.
CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("ingenieria-sistemas", ("ingenieria de sistemas", "ingeniero de sistemas", "ingenieria informatica",
                             "software", "programacion", "programador", "ciberseguridad", "hackathon", "hackaton",
                             "desarrollo web", "base de datos", "bases de datos", "algoritm", "computacion",
                             "devops")),
    ("tecnologia", ("tecnolog", "inteligencia artificial", " ia ", "digital", "ciencia de datos", "datos",
                    "nube", "robot", "innovacion", "internet", " 5g", "machine learning", "chatgpt", " iot",
                    "ciencia", "startup", "ingenieria")),
    ("educacion", ("educacion", "educativ", "estudiant", "universidad", "universitari", "academic", "beca",
                   "matricula", "docente", "profesor", "investigacion", "semillero", "curso", "posgrado",
                   "pregrado", "icfes", "saber pro", "aprendizaje", "colegio", "graduad", "maestria",
                   "doctorado", "acreditacion", "inscripcion")),
]


def classify(text: str, default: str = "general") -> str:
    low = " " + _strip_accents(text.lower()) + " "
    for category, words in CATEGORY_KEYWORDS:
        if any(w in low for w in words):
            return category
    return default


NS_MEDIA = "{http://search.yahoo.com/mrss/}"
NS_CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def _first_img(html: str, base: str = "") -> str | None:
    """Primera imagen de un fragmento HTML (src, data-src o la primera de srcset)."""
    if not html or "<img" not in html:
        return None
    img = BeautifulSoup(html, "html.parser").find("img")
    if img is None:
        return None
    src = img.get("data-src") or img.get("src") or (img.get("srcset") or "").split(" ")[0]
    if not src or src.startswith("data:"):
        return None
    return urljoin(base, src)


def rss_image(item: ET.Element) -> str | None:
    """Imagen de un ítem RSS: media:content / media:thumbnail, enclosure de imagen o <img> en el HTML."""
    for tag in ("content", "thumbnail"):
        for el in item.iter(NS_MEDIA + tag):
            url = el.get("url", "")
            medium = el.get("medium", "") or el.get("type", "")
            if url and ("image" in medium or url.lower().split("?")[0].endswith(IMG_EXT) or tag == "thumbnail"):
                return url
    enc = item.find("enclosure")
    if enc is not None and enc.get("url") and "image" in (enc.get("type") or "image"):
        return enc.get("url")
    return _first_img(item.findtext(NS_CONTENT) or "") or _first_img(item.findtext("description") or "")


def og_image(html: str, base: str) -> str | None:
    """Imagen de portada de una página (og:image o twitter:image)."""
    soup = BeautifulSoup(html, "html.parser")
    for attr, name in (("property", "og:image"), ("name", "twitter:image"), ("property", "og:image:url")):
        el = soup.find("meta", attrs={attr: name})
        if el and el.get("content"):
            return urljoin(base, el["content"].strip())
    return None


def parse_rss(xml_text: str, source: SourceConfig) -> list[Article]:
    """RSS 2.0 (Google News, El Tiempo, Enter.co, ...): title, link, pubDate, source, description, imagen."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[Article] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        src_el = item.find("source")
        src_name = src_el.text.strip() if src_el is not None and src_el.text else source.name
        # Google News agrega " - Medio" al final del título
        if src_name and title.endswith(" - " + src_name):
            title = title[: -len(" - " + src_name)].strip()
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published = datetime.now(timezone.utc)
        desc = BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(" ", strip=True)
        # Google News repite "título + medio" en la descripción: en ese caso el resumen es el título
        summary = title if not desc or desc.startswith(title) else desc
        out.append(Article(title=title[:500], published_at=published, summary=summary[:2000],
                           source_url=link, source_name=(src_name or source.name)[:120],
                           image_url=rss_image(item),
                           tags=[c.text.strip() for c in item.findall("category") if c.text]))
    return out


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
                                summary=(summary or title)[:2000], source_url=urljoin(source.url, href),
                                source_name=source.name, image_url=_first_img(str(item), source.url)))
    return articles


ALLOWED_DOMAINS = tuple(d.strip().lower() for d in os.getenv("NEWS_ALLOWED_DOMAINS", "unab.edu.co").split(",") if d.strip())


def _allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return not ALLOWED_DOMAINS or any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


async def enrich_images(articles: Sequence[Article], fetcher: Fetcher, limit: int = 25) -> int:
    """Busca og:image en la página de las noticias sin imagen (no aplica a los enlaces de Google News,
    que redirigen con JavaScript). Devuelve cuántas imágenes encontró."""
    found = 0
    for a in [x for x in articles if not x.image_url and "news.google.com" not in x.source_url][:limit]:
        try:
            a.image_url = og_image(await fetcher(a.source_url), a.source_url)
            found += bool(a.image_url)
        except Exception as exc:
            log.info("Sin imagen para %s: %s", a.source_url, exc)
    return found


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
        found = parse_rss(html, src) if src.type == "rss" else parse_articles(html, src)
        for a in found:
            a.category = classify(f"{a.title} {a.summary} {' '.join(a.tags)}", src.default_category)
        # Solo noticias de los dominios permitidos (por defecto, solo la UNAB)
        found = [a for a in found if _allowed(a.source_url)]
        if not src.keep_general:
            found = [a for a in found if a.category != "general"]
        report.total_extracted += len(found)
        for a in found:
            collected.setdefault(a.source_url, a)  # dedup dentro de la misma corrida

    batch = list(collected.values())
    existing = await store.existing_urls([a.source_url for a in batch])
    new = [a for a in batch if a.source_url not in existing]
    await enrich_images(new, fetcher)
    report.with_image = sum(1 for a in new if a.image_url)
    report.total_inserted = await store.insert(new) if new else 0
    report.skipped_duplicates = report.total_extracted - report.total_inserted
    for a in new:
        report.by_category[a.category] = report.by_category.get(a.category, 0) + 1
    log.info("Scraper: fuentes=%d extraidos=%d insertados=%d duplicados=%d fallidas=%s",
             report.total_sources, report.total_extracted, report.total_inserted,
             report.skipped_duplicates, report.failed_sources)
    return report
