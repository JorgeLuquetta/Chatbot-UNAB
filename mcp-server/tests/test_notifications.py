"""Property 24: ventana de notificaciones push de 48 horas."""
from datetime import datetime, timedelta, timezone

from hypothesis import given
from hypothesis import strategies as st

from app.notifications import BOGOTA, events_in_window

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)


# Feature: chatbot-apoyo-academico, Property 24: Notificaciones push dentro de ventana de 48 horas
@given(offsets=st.lists(st.integers(min_value=-10 * 24 * 60, max_value=10 * 24 * 60), max_size=40))
def test_property_24_window(offsets):
    events = [{"event_name": f"E{i}", "event_date": (NOW + timedelta(minutes=m)).isoformat()}
              for i, m in enumerate(offsets)]
    selected = {e["event_name"] for e in events_in_window(events, NOW)}
    for i, m in enumerate(offsets):
        inside = 0 < m <= 48 * 60
        assert (f"E{i}" in selected) == inside


def test_boundaries_and_date_only():
    events = [
        {"event_name": "ahora", "event_date": NOW.isoformat()},
        {"event_name": "limite", "event_date": (NOW + timedelta(hours=48)).isoformat()},
        {"event_name": "fuera", "event_date": (NOW + timedelta(hours=48, seconds=1)).isoformat()},
        {"event_name": "solo-fecha", "event_date": "2026-11-13"},
        {"event_name": "invalida", "event_date": "13 de nov"},
    ]
    names = [e["event_name"] for e in events_in_window(events, NOW)]
    assert names == ["limite", "solo-fecha"]
    assert datetime.fromisoformat("2026-11-13").replace(tzinfo=BOGOTA) > NOW


def test_event_key_is_stable():
    [e] = events_in_window([{"event_name": "Parciales", "event_date": "2026-11-13"}], NOW)
    assert e["event_key"] == "Parciales|2026-11-13"
