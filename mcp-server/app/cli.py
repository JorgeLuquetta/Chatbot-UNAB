"""Ejecución manual del pipeline de ingesta y del scraper.

Uso dentro del contenedor:
    docker compose exec mcp-server python -m app.cli ingest            # todos los archivos de /data/ccd
    docker compose exec mcp-server python -m app.cli ingest plan.pdf   # archivos específicos
    docker compose exec mcp-server python -m app.cli scrape            # fuentes de sources.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from .db import close_pool
from .server import _ingest, _scrape


async def _main(args: argparse.Namespace) -> None:
    try:
        if args.command == "ingest":
            report = await _ingest(args.files)
        else:
            report = await _scrape(args.urls)
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    finally:
        await close_pool()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_ing = sub.add_parser("ingest", help="Ingerir documentos CCD")
    p_ing.add_argument("files", nargs="*", help="Rutas relativas a /data/ccd (vacío = todos)")
    p_scr = sub.add_parser("scrape", help="Ejecutar scraper de noticias")
    p_scr.add_argument("urls", nargs="*", help="URLs a raspar (vacío = sources.json)")
    asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    main()
