#!/usr/bin/env bash
# First installation of daily snapshots. Does not change the running app or DB schema.
set -euo pipefail

if [[ "$(id -u)" != 0 ]]; then
  printf 'Run this script as root on the Ubuntu VM.\n' >&2
  exit 1
fi
for nen_command in install systemctl systemd-analyze runuser python3; do
  command -v "$nen_command" >/dev/null
done
test -d /run/systemd/system
id nen >/dev/null
runuser -u nen -- test -r /var/lib/nen/pact.db
nen_source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$nen_source_root/api/app/sqlite_backup.py"

for nen_existing in /usr/local/lib/nen/sqlite_backup.py /etc/systemd/system/nen-backup.service /etc/systemd/system/nen-backup.timer; do
  if [[ -e "$nen_existing" || -L "$nen_existing" ]]; then
    printf 'Stopped: %s already exists; review the installed backup configuration.\n' "$nen_existing" >&2
    exit 1
  fi
done

install -d -o root -g root -m 0755 /usr/local/lib/nen
install -d -o nen -g nen -m 0700 /var/backups/nen
install -o root -g root -m 0644 "$nen_source_root/api/app/sqlite_backup.py" /usr/local/lib/nen/sqlite_backup.py

cat > /etc/systemd/system/nen-backup.service <<'UNIT'
[Unit]
Description=Nen verified SQLite backup
After=local-fs.target
ConditionPathExists=/var/lib/nen/pact.db

[Service]
Type=oneshot
User=nen
Group=nen
ExecStart=/usr/bin/python3 /usr/local/lib/nen/sqlite_backup.py backup --source /var/lib/nen/pact.db --directory /var/backups/nen --label daily --keep 14
TimeoutStartSec=5min
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
# SQLite may need its WAL/SHM locks even when the DB is opened read-only.
ReadWritePaths=/var/lib/nen /var/backups/nen
UNIT

cat > /etc/systemd/system/nen-backup.timer <<'UNIT'
[Unit]
Description=Daily Nen SQLite backup

[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=15min
Persistent=true
Unit=nen-backup.service

[Install]
WantedBy=timers.target
UNIT

chmod 0644 /etc/systemd/system/nen-backup.service /etc/systemd/system/nen-backup.timer
systemd-analyze verify /etc/systemd/system/nen-backup.service /etc/systemd/system/nen-backup.timer
systemctl daemon-reload
systemctl enable --now nen-backup.timer
systemctl start nen-backup.service
systemctl --no-pager status nen-backup.timer
journalctl -u nen-backup.service -n 10 --no-pager
