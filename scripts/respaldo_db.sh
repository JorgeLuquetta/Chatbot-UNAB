#!/usr/bin/env bash
# Respaldo diario de Supabase PostgreSQL (timer unab-backup). Guarda 7 días en ~/respaldos-chatbot.
# El URL se toma del entorno del servicio mcp-server sin imprimir las credenciales.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${BACKUP_DIR:-$HOME/respaldos-chatbot}"
mkdir -p "$DEST"
docker compose run --rm --no-deps --entrypoint sh mcp-server \
  -c 'printf "SUPABASE_DB_URL=%s\n" "$SUPABASE_DB_URL"' |
  docker run --rm --network host --env-file /dev/stdin -e PGSSLMODE=require postgres:16-alpine \
    sh -ec 'pg_dump --dbname="$SUPABASE_DB_URL" --clean --if-exists --no-owner --no-acl' |
  gzip > "$DEST/chatbot-$(date +%F).sql.gz"
find "$DEST" -name 'chatbot-*.sql.gz' -mtime +7 -delete
echo "Respaldo listo: $DEST/chatbot-$(date +%F).sql.gz"
