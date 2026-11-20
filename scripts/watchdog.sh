#!/usr/bin/env bash
# Vigilante del Chatbot UNAB: lo ejecuta un timer de systemd cada 2 minutos.
# Si algún servicio no responde, lo vuelve a levantar. Log: journalctl -u unab-watchdog
set -u
cd "$(dirname "$0")/.." || exit 1
# Segundos que lleva arriba un servicio (para no reiniciar uno que todavía está arrancando)
uptime_s() {
  local id started; id=$(docker compose ps -q "$1" 2>/dev/null) || return 1; [ -n "$id" ] || { echo 0; return; }
  started=$(docker inspect -f '{{.State.StartedAt}}' "$id" 2>/dev/null) || { echo 0; return; }
  echo $(( $(date +%s) - $(date -d "$started" +%s) ))
}
restart_if_old() { [ "$(uptime_s "$1")" -gt "${2:-180}" ] && { echo "$1 no responde, reiniciando"; docker compose restart "$1"; }; }
check() { curl -s -m 15 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null | grep -qE '^(2|3|4)'; }
# Health-check interno de un contenedor (los que no publican puertos)
healthy() { [ "$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$(docker compose ps -q "$1")" 2>/dev/null)" != "unhealthy" ]; }

# 1) Contenedores detenidos o que nunca arrancaron
# (se excluye ollama-pull: es una tarea de una sola vez que descarga los modelos)
SERVICES=$(docker compose config --services 2>/dev/null | grep -vx 'ollama-pull')
docker compose up -d --no-recreate --no-deps $SERVICES >/dev/null 2>&1 || echo "docker compose up falló"

# 2) Servicios que están arriba pero no responden
check http://localhost:9000/healthz || restart_if_old n8n
{ check http://localhost:9001/ && check http://localhost:9002/ && check http://localhost:9003/; } || restart_if_old web
for s in mcp-server guardrails; do healthy "$s" || restart_if_old "$s"; done
docker compose exec -T ollama ollama list >/dev/null 2>&1 || restart_if_old ollama
# Expo: la primera vez instala dependencias (npm ci), por eso tiene 10 min de margen
if docker compose config --services 2>/dev/null | grep -qx expo; then
  curl -s -m 10 -H "expo-platform: android" http://localhost:8081/status 2>/dev/null | grep -q running || restart_if_old expo 600
fi

# 3) Túnel de Cloudflare
systemctl is-active --quiet cloudflared || { echo "cloudflared caído, reiniciando"; systemctl restart cloudflared; }
exit 0
