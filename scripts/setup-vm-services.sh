#!/usr/bin/env bash
# First installation only. Existing databases and service configs are preserved.
set -euo pipefail

if [[ "$(id -u)" != 0 ]]; then
  printf 'Run this script as root on the Ubuntu VM.\n' >&2
  exit 1
fi

for nen_command in runuser systemctl systemd-analyze install ss curl; do
  command -v "$nen_command" >/dev/null
done
test -d /run/systemd/system
id nen >/dev/null
test -x /srv/nen/api/.venv/bin/python
test -x /usr/local/bin/node
runuser -u nen -- test -r /srv/nen/web/.next/BUILD_ID
runuser -u nen -- test -r /srv/nen/web/node_modules/next/dist/bin/next

for nen_existing in /var/lib/nen/pact.db /etc/nen/api.env /etc/systemd/system/nen-api.service /etc/systemd/system/nen-web.service; do
  if [[ -e "$nen_existing" || -L "$nen_existing" ]]; then
    printf 'Stopped: %s already exists. Review it before continuing; nothing will be reset.\n' "$nen_existing" >&2
    exit 1
  fi
done

nen_listeners="$(ss -H -ltn '( sport = :3000 or sport = :8000 )')"
if [[ -n "$nen_listeners" ]]; then
  printf 'Stopped: an existing process is listening on port 3000 or 8000:\n%s\n' "$nen_listeners" >&2
  exit 1
fi

umask 027
install -d -o root -g nen -m 0750 /etc/nen
install -d -o nen -g nen -m 0750 /var/lib/nen

cat > /etc/nen/api.env <<'ENV'
DATABASE_URL=sqlite:////var/lib/nen/pact.db
PACT_DEBUG=false
# Initial preview uses HTTP on loopback through an encrypted SSH tunnel.
# Change to true before publishing the application over HTTPS.
PACT_COOKIE_SECURE=false
ENV
chown root:nen /etc/nen/api.env
chmod 0640 /etc/nen/api.env

cat > /etc/systemd/system/nen-api.service <<'UNIT'
[Unit]
Description=Nen API
After=network.target

[Service]
Type=exec
User=nen
Group=nen
WorkingDirectory=/srv/nen/api
EnvironmentFile=/etc/nen/api.env
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/srv/nen/api/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/nen

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/nen-web.service <<'UNIT'
[Unit]
Description=Nen website
After=network.target nen-api.service
Wants=nen-api.service

[Service]
Type=exec
User=nen
Group=nen
WorkingDirectory=/srv/nen/web
Environment=NODE_ENV=production
Environment=NEN_API_ORIGIN=http://127.0.0.1:8000
ExecStart=/usr/local/bin/node /srv/nen/web/node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
Restart=on-failure
RestartSec=3
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/nen/web/.next

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 /etc/systemd/system/nen-api.service /etc/systemd/system/nen-web.service

systemd-analyze verify /etc/systemd/system/nen-api.service /etc/systemd/system/nen-web.service

# Importing the API creates the schema in the new empty database. No sample data.
cd /srv/nen/api
runuser -u nen -- env DATABASE_URL=sqlite:////var/lib/nen/pact.db PACT_DEBUG=false PACT_COOKIE_SECURE=false PYTHONDONTWRITEBYTECODE=1 \
  /srv/nen/api/.venv/bin/python -c 'from app.main import app; print("Fresh database initialized.")'

systemctl daemon-reload
systemctl enable --now nen-api.service nen-web.service

printf '\nChecking API...\n'
curl -fsS --retry 12 --retry-connrefused --retry-delay 1 http://127.0.0.1:8000/api/v1/health
printf '\nChecking website API proxy...\n'
curl -fsS --retry 12 --retry-connrefused --retry-delay 1 http://127.0.0.1:3000/api/v1/health
printf '\nChecking home page...\n'
curl -fsS -o /dev/null --retry 12 --retry-connrefused --retry-delay 1 http://127.0.0.1:3000/
printf '\n'
systemctl --no-pager --full status nen-api.service nen-web.service
