#!/usr/bin/env bash
# Deja el sistema siempre encendido en la VM (ejecutar una vez, desde la carpeta del proyecto):
#   ./scripts/instalar_persistencia.sh
#
# * Docker y cloudflared arrancan con el sistema.
# * Los contenedores tienen restart: always y sus datos en volúmenes (n8n_data, pg_data, ollama_models, ...).
# * unab-watchdog.timer: cada 2 min revisa y levanta lo que no responda (scripts/watchdog.sh).
# * unab-backup.timer: respaldo diario de PostgreSQL a las 03:00 (scripts/respaldo_db.sh), 7 días.
set -eu
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
chmod +x "$DIR/scripts/watchdog.sh" "$DIR/scripts/respaldo_db.sh"

sudo tee /etc/systemd/system/unab-watchdog.service >/dev/null <<EOF
[Unit]
Description=Vigilante del Chatbot UNAB
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=$DIR
ExecStart=$DIR/scripts/watchdog.sh
EOF

sudo tee /etc/systemd/system/unab-watchdog.timer >/dev/null <<EOF
[Unit]
Description=Vigilante del Chatbot UNAB cada 2 minutos

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
EOF

sudo tee /etc/systemd/system/unab-backup.service >/dev/null <<EOF
[Unit]
Description=Respaldo diario de PostgreSQL del Chatbot UNAB
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/scripts/respaldo_db.sh
EOF

sudo tee /etc/systemd/system/unab-backup.timer >/dev/null <<EOF
[Unit]
Description=Respaldo diario de PostgreSQL (03:00)

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now docker unab-watchdog.timer unab-backup.timer
systemctl list-unit-files cloudflared.service >/dev/null 2>&1 && sudo systemctl enable --now cloudflared
systemctl list-timers --all | grep -E "unab-(watchdog|backup)"
