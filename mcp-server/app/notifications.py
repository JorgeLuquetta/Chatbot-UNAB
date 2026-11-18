"""Ventana de notificaciones push de 48h (Requirement 14.1 / Property 24).

Esta lógica es la referencia en Python; el workflow n8n "Notificaciones Push"
usa la misma regla en n8n/code/events_in_window.js.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")
WINDOW = timedelta(hours=48)


def parse_event_date(value: str) -> datetime | None:
    """'2026-11-14' se interpreta como medianoche hora Colombia; ISO con hora se respeta."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=BOGOTA)


def event_key(event: dict) -> str:
    return f"{str(event.get('event_name', '')).strip()}|{str(event.get('event_date', '')).strip()}"


def events_in_window(events: Iterable[dict], now: datetime | None = None, window: timedelta = WINDOW) -> list[dict]:
    """Eventos con fecha en el intervalo (now, now + 48h]."""
    now = now or datetime.now(timezone.utc)
    out = []
    for e in events:
        dt = parse_event_date(e.get("event_date", ""))
        if dt is not None and now < dt <= now + window:
            out.append({**e, "event_key": event_key(e)})
    return out
