#!/usr/bin/env bash
# Ejecuta todas las pruebas Python. Opcional: TEST_DB_URL apuntando a un PostgreSQL
# con pgvector y db/schema.sql + db/seed.sql aplicados para las pruebas de integración.
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q -r mcp-server/requirements-dev.txt -r guardrails/requirements-dev.txt
(cd mcp-server && python -m pytest -q)
(cd guardrails && python -m pytest -q)
python -m pytest -q tests/integration
echo "Android: cd android && ./gradlew test"
