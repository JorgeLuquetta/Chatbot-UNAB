"""Clasificación de noticias, parser RSS, middleware de argumentos MCP y resumen del plan académico."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.academic import plan_summary
from app.scraper import SourceConfig, classify, parse_rss

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Nuevo programa de desarrollo de software - El Tiempo</title><link>https://n.example/1</link>
<pubDate>Thu, 19 Nov 2026 13:00:00 GMT</pubDate><source url="https://eltiempo.com">El Tiempo</source>
<description>&lt;a&gt;Nuevo programa de desarrollo de software&lt;/a&gt; El Tiempo</description></item>
<item><title>Resultados del fútbol</title><link>https://n.example/2</link><pubDate>bad</pubDate></item>
</channel></rss>"""


def test_classify_categories():
    assert classify("Hackatón de ingeniería de sistemas en la UNAB") == "ingenieria-sistemas"
    assert classify("La inteligencia artificial llega a las aulas") == "tecnologia"
    assert classify("Abiertas inscripciones para becas de posgrado") == "educacion"
    assert classify("Resultados del fútbol") == "general"
    assert classify("Resultados del fútbol", default="educacion") == "educacion"


def test_parse_rss_source_and_date():
    items = parse_rss(RSS, SourceConfig(url="https://news.example/rss", name="Google News", type="rss"))
    assert len(items) == 2
    first = items[0]
    assert first.title == "Nuevo programa de desarrollo de software"   # sin " - El Tiempo"
    assert first.source_name == "El Tiempo"
    assert first.published_at.isoformat().startswith("2026-11-19")
    assert first.summary == first.title                                # descripción = título + medio
    assert items[1].source_name == "Google News"                        # sin <source>: nombre de la fuente


def test_parse_rss_invalid_xml():
    assert parse_rss("<html>no es rss", SourceConfig(url="x", type="rss")) == []


def test_strip_unknown_args():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": "get_academic_plan",
                      "arguments": {"student_id": "U1", "toolCallId": "x", "allowed": True}}}
    assert main._clean(msg) is True
    assert msg["params"]["arguments"] == {"student_id": "U1"}
    assert main._clean({"method": "tools/list"}) is False


def test_plan_summary_text():
    plan = json.loads("""{
      "student": {"student_id": "U1", "full_name": "Ana", "program": "Ingeniería de Sistemas", "current_semester": 6},
      "status": {"gpa": 4.45, "standing": "excelencia", "approved_credits": 50, "total_credits": 75,
                 "progress_percentage": 66.7, "failed_courses": 0, "in_progress": [{"course_name": "Ciencia de Datos"}]},
      "enrollment": {"term": "2027-1", "max_credits": 21, "credits": 7,
                     "courses": [{"course_code": "ISC701", "course_name": "Inteligencia Artificial", "credits": 3,
                                  "repeat": false, "conditional": true,
                                  "conditional_on": [{"course_name": "Ciencia de Datos"}]}],
                     "blocked": []},
      "projection": {"remaining_credits": 16, "terms_remaining": 2, "estimated_graduation_term": "2027-2", "on_track": true},
      "recommendations": [{"type": "investigacion", "text": "Postúlate a un semillero."}]}""")
    text = plan_summary(plan)
    assert "promedio ponderado 4.45" in text
    assert "ISC701 Inteligencia Artificial, 3 créditos (condicionada a aprobar Ciencia de Datos)" in text
    assert "grado estimado en el periodo 2027-2" in text
    assert "- Postúlate a un semillero." in text


def test_solo_noticias_unab(monkeypatch):
    import app.scraper as sc
    monkeypatch.setattr(sc, "ALLOWED_DOMAINS", ("unab.edu.co",))
    assert sc._allowed("https://unab.edu.co/noticia-1/")
    assert sc._allowed("https://www.unab.edu.co/noticias/x")
    assert not sc._allowed("https://www.eltiempo.com/tecnosfera/x")
    assert not sc._allowed("https://news.google.com/rss/articles/abc")
    assert not sc._allowed("https://unab.edu.co.malicioso.com/x")


def test_rss_tags_classify():
    xml = """<rss><channel><item><title>Nuevo laboratorio</title><link>https://unab.edu.co/lab/</link>
    <pubDate>Thu, 19 Nov 2026 13:00:00 GMT</pubDate><category><![CDATA[Ingeniería de Sistemas]]></category></item></channel></rss>"""
    [a] = parse_rss(xml, SourceConfig(url="https://unab.edu.co/feed/", type="rss"))
    assert a.tags == ["Ingeniería de Sistemas"]
    assert classify(f"{a.title} {' '.join(a.tags)}") == "ingenieria-sistemas"
    assert "tags" not in a.model_dump()          # no se guarda en la BD


def test_external_clients_read_only():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main
    call = lambda name: {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {}}}
    assert main._is_write_call(call("ingest_documents"))
    assert main._is_write_call(call("run_news_scraper"))
    assert not main._is_write_call(call("get_academic_plan"))
    assert not main._is_write_call({"method": "tools/list"})


def test_ccd_summary_text():
    from app.academic import ccd_summary
    ccd = {"student_id": "U1", "diagnostic": {"score": 88, "level": "avanzado"},
           "badge": {"earned": False, "required_done": 2, "required_total": 4, "electives_done": 0,
                     "next": "CCD03 Gestión de información y búsqueda académica"},
           "courses": [{"course_code": "CCD02", "course_name": "Herramientas ofimáticas", "required": True,
                        "level": "básico", "status": "homologated", "grade": None}],
           "enrollment_info": "Cosmos UNAB"}
    text = ccd_summary(ccd)
    assert "88 puntos, nivel avanzado" in text
    assert "2 de 4 cursos obligatorios" in text
    assert "homologado por la prueba diagnóstica" in text
    assert "YA TOMADOS" in text
    assert "Siguiente curso recomendado: CCD03" in text
