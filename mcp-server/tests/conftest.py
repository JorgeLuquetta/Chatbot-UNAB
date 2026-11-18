import os
import sys
from pathlib import Path

import pytest
from hypothesis import settings as hyp_settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Mínimo 100 iteraciones por property test (estrategia de testing del diseño)
hyp_settings.register_profile("ci", max_examples=100, deadline=None)
hyp_settings.load_profile("ci")

TEST_DB_URL = os.getenv("TEST_DB_URL")  # p. ej. postgresql://postgres@localhost:5432/chatbot_test


@pytest.fixture
def anyio_backend():
    return "asyncio"
