#!/usr/bin/env bash
# Respaldo diario de PostgreSQL (timer unab-backup). Guarda 7 días en ~/respaldos-chatbot.
#   Restaurar: gunzip -c ~/respaldos-chatbot/chatbot-AAAA-MM-DD.sql.gz | docker compose exec -T db psql -U postgres -d chatbot
set -eu
cd "$(dirname "$0")/.."
DEST="${BACKUP_DIR:-$HOME/respaldos-chatbot}"
mkdir -p "$DEST"
docker compose exec -T db pg_dump -U postgres -d chatbot --clean --if-exists | gzip > "$DEST/chatbot-$(date +%F).sql.gz"
find "$DEST" -name 'chatbot-*.sql.gz' -mtime +7 -delete
echo "Respaldo listo: $DEST/chatbot-$(date +%F).sql.gz"
