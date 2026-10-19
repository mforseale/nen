#!/usr/bin/env bash
# First installation of the fixed SSH gate. Does not deploy or restart the app.
set -euo pipefail
[[ "$(id -u)" = 0 ]]
[[ $# = 1 ]] || { printf 'Usage: bash setup-vm-cd.sh /root/nen-actions.pub\n' >&2; exit 1; }
for nen_command in python3 install systemctl systemd-analyze sudo visudo ssh-keygen useradd runuser; do
  command -v "$nen_command" >/dev/null
done
test -d /run/systemd/system
systemctl is-active --quiet nen-api.service
systemctl is-active --quiet nen-web.service
id nen >/dev/null
test -r /etc/ssh/ssh_host_ed25519_key.pub
test ! -e /srv/nen-deploy-state.json
test -d /srv/nen
test ! -L /srv/nen
test "$(readlink -f /srv/nen)" = /srv/nen
nen_source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
nen_public_key="$(python3 - "$1" <<'PY'
import base64
from pathlib import Path
import struct
import sys
parts = Path(sys.argv[1]).read_text().strip().split()
if len(parts) not in (2, 3) or parts[0] != 'ssh-ed25519':
    raise SystemExit('Supply one Ed25519 public key; never a private key.')
raw = base64.b64decode(parts[1], validate=True)
if len(raw) != 51 or raw[:4] != struct.pack('>I', 11) or raw[4:15] != b'ssh-ed25519' or raw[15:19] != struct.pack('>I', 32):
    raise SystemExit('Invalid Ed25519 public key.')
print(' '.join(parts[:2]) + ' nen-github-actions')
PY
)"

for nen_existing in /usr/local/lib/nen/cd /usr/local/sbin/nen-deploy /etc/sudoers.d/nen-deploy /etc/systemd/system/nen-deploy.service /var/lib/nen-cd /var/lib/nen-deploy; do
  if [[ -e "$nen_existing" || -L "$nen_existing" ]]; then
    printf 'Stopped: %s already exists; review the installed CD configuration.\n' "$nen_existing" >&2
    exit 1
  fi
done
if id nen-deploy >/dev/null 2>&1; then
  printf 'Stopped: nen-deploy account already exists.\n' >&2
  exit 1
fi

umask 027
# The application directories are protected only if their parent is protected
# too. The original installation made /srv/nen owned by the app user.
chown root:nen /srv/nen
chmod 0750 /srv/nen
useradd --system --user-group --home-dir /var/lib/nen-deploy --shell /bin/sh nen-deploy
install -d -o root -g root -m 0755 /var/lib/nen-deploy
install -d -o root -g nen-deploy -m 0750 /var/lib/nen-deploy/.ssh
printf 'restrict,command="/usr/bin/sudo -n /usr/local/sbin/nen-deploy" %s\n' "$nen_public_key" > /var/lib/nen-deploy/.ssh/authorized_keys
chown root:nen-deploy /var/lib/nen-deploy/.ssh/authorized_keys
chmod 0640 /var/lib/nen-deploy/.ssh/authorized_keys
install -d -o root -g root -m 0700 /var/lib/nen-cd
install -d -o root -g root -m 0755 /usr/local/lib/nen /usr/local/lib/nen/cd
for nen_file in deploy_vm.py runtime_bundle.py ssh_receive.py; do
  install -o root -g root -m 0644 "$nen_source_root/scripts/$nen_file" "/usr/local/lib/nen/cd/$nen_file"
done
install -o root -g root -m 0755 "$nen_source_root/scripts/ssh_receive.py" /usr/local/sbin/nen-deploy
printf 'nen-deploy ALL=(root) NOPASSWD: /usr/local/sbin/nen-deploy ""\n' > /etc/sudoers.d/nen-deploy
chmod 0440 /etc/sudoers.d/nen-deploy
visudo -cf /etc/sudoers.d/nen-deploy

cat > /etc/systemd/system/nen-deploy.service <<'UNIT'
[Unit]
Description=Nen verified package deployment
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I /usr/local/lib/nen/cd/ssh_receive.py apply
TimeoutStartSec=15min
TimeoutStopSec=2min
UMask=0077
StandardOutput=journal
StandardError=journal
UNIT
chmod 0644 /etc/systemd/system/nen-deploy.service
systemd-analyze verify /etc/systemd/system/nen-deploy.service
systemctl daemon-reload
printf '{"version":1,"action":"probe"}\n' | runuser -u nen-deploy -- sudo -n /usr/local/sbin/nen-deploy

printf '\nRestricted deployment account is installed. App services were not restarted.\n'
printf 'Copy the following public host-key line into NEN_DEPLOY_KNOWN_HOSTS:\n'
python3 - <<'PY'
from pathlib import Path
key = Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()
print('144.31.189.98 ' + ' '.join(key[:2]))
PY
