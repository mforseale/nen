#!/usr/bin/env bash
# One-time baseline adoption for the existing Ubuntu installation.
# App source, service units and Caddy are not replaced.
set -euo pipefail

if [[ "$(id -u)" != 0 ]]; then
  printf 'Run this script as root on the Ubuntu VM.\n' >&2
  exit 1
fi
for nen_command in git tar install mktemp runuser systemctl curl flock python3; do
  command -v "$nen_command" >/dev/null
done
test -d /run/systemd/system
test -x /srv/nen/api/.venv/bin/python
test -f /var/lib/nen/pact.db
test ! -L /var/lib/nen/pact.db
test -f /usr/local/lib/nen/sqlite_backup.py
test -d /var/backups/nen
test "$(systemctl show nen-api.service --property=User --value)" = nen
systemctl is-active --quiet nen-backup.timer
systemctl is-active --quiet nen-api.service
systemctl is-active --quiet nen-web.service
nen_api_pid="$(systemctl show nen-api.service --property=MainPID --value)"
python3 - "$nen_api_pid" <<'PY'
from pathlib import Path
import sys
pid = int(sys.argv[1])
if pid < 1:
    raise SystemExit('API must be running before baseline registration.')
environment = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
urls = [value for value in environment if value.startswith(b'DATABASE_URL=')]
if urls != [b'DATABASE_URL=sqlite:////var/lib/nen/pact.db']:
    raise SystemExit('The running API does not use the expected database; review configuration first.')
PY
curl -fsS --max-time 10 http://127.0.0.1:8000/api/v1/health
curl -fsS --max-time 10 http://127.0.0.1:3000/api/v1/health

install -d -o root -g root -m 0700 /run/nen-db-bootstrap
exec 9>/run/nen-db-bootstrap/lock
flock -n 9 || { printf 'Another baseline operation is running.\n' >&2; exit 1; }

nen_source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
nen_commit="$(git -C "$nen_source_root" rev-parse --verify HEAD)"
[[ "$nen_commit" =~ ^[0-9a-f]{40}$ ]]
umask 027
test ! -L /opt/nen-db-tools
install -d -o root -g nen -m 0750 /opt/nen-db-tools
nen_stage="$(mktemp -d "/opt/nen-db-tools/${nen_commit}-XXXXXXXX")"
git -C "$nen_source_root" archive "$nen_commit" api/app api/alembic api/alembic.ini api/requirements.txt |
  tar --extract --directory "$nen_stage" --no-same-owner --no-same-permissions
chown -R root:nen "$nen_stage"
chmod -R u=rwX,g=rX,o= "$nen_stage"
cd "$nen_stage/api"
nen_python=/srv/nen/api/.venv/bin/python
nen_run() {
  runuser -u nen -- env DATABASE_URL=sqlite:////var/lib/nen/pact.db \
    PYTHONPATH="$nen_stage/api" PYTHONDONTWRITEBYTECODE=1 "$nen_python" "$@"
}

printf '\nChecking the existing Python environment...\n'
nen_run - requirements.txt <<'PY'
from importlib.metadata import version
from pathlib import Path
import sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit('This bootstrap expects Python 3.10, matching the Ubuntu VM and CI.')
for line in Path(sys.argv[1]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    name, expected = line.split('==')
    name = name.split('[', 1)[0]
    actual = version(name)
    if actual != expected:
        raise SystemExit(f'{name}: installed {actual}, expected {expected}; live DB not changed.')
print('Core dependency versions match the checked source.')
PY
nen_run -m pip check

install -d -o nen -g nen -m 0700 /var/backups/nen/rehearsals
nen_work_dir="$(mktemp -d /var/backups/nen/rehearsals/baseline-XXXXXXXX)"
chown nen:nen "$nen_work_dir"
chmod 0700 "$nen_work_dir"
printf '\nTesting restore and baseline adoption on a separate copy...\n'
nen_run -m app.db_admin rehearse-baseline --backup-dir /var/backups/nen --work-dir "$nen_work_dir"

# Do not restart a service that somebody stopped during the rehearsal.
systemctl is-active --quiet nen-api.service
nen_restart_needed=0
nen_cleanup() {
  nen_exit_code=$?
  trap - EXIT INT TERM HUP
  set +e
  if [[ "$nen_restart_needed" = 1 ]]; then
    printf '\nReturning the API service after the interrupted operation...\n' >&2
    if ! systemctl start nen-api.service; then
      printf 'API restart failed; inspect journalctl -u nen-api.service.\n' >&2
      nen_exit_code=1
    fi
  fi
  exit "$nen_exit_code"
}
trap nen_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

printf '\nStopping API briefly to register the live database baseline...\n'
nen_restart_needed=1
systemctl stop nen-api.service
# This mode refuses future revisions: only the already-existing baseline is adopted.
# migrate creates a fresh snapshot under the write lock before adding the version marker.
nen_run -m app.db_admin migrate --backup-dir /var/backups/nen --adopt-existing --baseline-only
nen_run -m app.db_admin check
systemctl start nen-api.service
nen_restart_needed=0

printf '\nChecking API and frontend proxy...\n'
curl -fsS --max-time 10 --retry 12 --retry-connrefused --retry-delay 1 http://127.0.0.1:8000/api/v1/health
curl -fsS --max-time 10 --retry 12 --retry-connrefused --retry-delay 1 http://127.0.0.1:3000/api/v1/health
printf '\nBaseline registration completed. Migration tools: %s\n' "$nen_stage/api"
systemctl --no-pager --full status nen-api.service
