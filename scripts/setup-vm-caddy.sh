#!/usr/bin/env bash
# First public installation for the existing Nen VM. Xray keeps TCP 443.
set -Eeuo pipefail

nen_ip=144.31.189.98
nen_port=8443

nen_config() {
  cat <<CONFIG
{
    admin 127.0.0.1:2019
    default_sni ${nen_ip}
    https_port ${nen_port}
    servers {
        protocols h1 h2
    }
}

https://${nen_ip}:${nen_port} {
    tls {
        issuer acme {
            dir https://acme-v02.api.letsencrypt.org/directory
            profile shortlived
            disable_tlsalpn_challenge
        }
    }
    request_body {
        max_size 60MiB
    }
    encode zstd gzip
CONFIG
  if [[ "$1" == app ]]; then
    printf '    reverse_proxy 127.0.0.1:3000\n'
  else
    printf '    respond "Nen HTTPS setup in progress" 503\n'
  fi
  printf '}\n'
}

if [[ "${1:-}" == --print-config ]]; then
  nen_config app
  exit 0
fi
if [[ $# != 0 ]]; then
  printf 'Usage: bash setup-vm-caddy.sh [--print-config]\n' >&2
  exit 1
fi

trap 'nen_status=$?; printf "Setup stopped at line %s (exit %s). Send this output and: journalctl -u caddy -u nen-api -n 80 --no-pager\n" "$LINENO" "$nen_status" >&2; exit "$nen_status"' ERR

if [[ "$(id -u)" != 0 || ! -d /run/systemd/system ]]; then
  printf 'Run this installer as root on the Ubuntu VM.\n' >&2
  exit 1
fi
for nen_command in apt-get dpkg curl ss systemctl runuser install python3; do
  command -v "$nen_command" >/dev/null
done
test -r /etc/nen/api.env
test -s /var/lib/nen/pact.db
systemctl is-active --quiet nen-api.service
systemctl is-active --quiet nen-web.service
grep -qx 'DATABASE_URL=sqlite:////var/lib/nen/pact.db' /etc/nen/api.env
grep -qx 'PACT_COOKIE_SECURE=false' /etc/nen/api.env
curl -fsS --max-time 10 http://127.0.0.1:3000/api/v1/health
printf '\n'

if command -v caddy >/dev/null; then
  printf 'Stopped: Caddy is already installed. Review its configuration before continuing.\n' >&2
  exit 1
fi
for nen_existing in /etc/caddy/Caddyfile /etc/apt/sources.list.d/caddy-stable.list /usr/share/keyrings/caddy-stable-archive-keyring.gpg; do
  if [[ -e "$nen_existing" || -L "$nen_existing" ]]; then
    printf 'Stopped: %s already exists. Existing configuration needs review.\n' "$nen_existing" >&2
    exit 1
  fi
done
nen_listeners="$(ss -H -ltn '( sport = :80 or sport = :8443 or sport = :2019 )')"
if [[ -n "$nen_listeners" ]]; then
  printf 'Stopped: port 80, 8443 or 2019 is already used:\n%s\n' "$nen_listeners" >&2
  exit 1
fi

nen_tmp="$(mktemp -d)"
nen_stamp="$(date -u +%Y%m%dT%H%M%S)-$$"

# Official stable Caddy APT repository; list other daemons without restarting them.
apt-get update
env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y ca-certificates curl gnupg debian-keyring debian-archive-keyring apt-transport-https
curl -fsSL --connect-timeout 15 --max-time 120 https://dl.cloudsmith.io/public/caddy/stable/gpg.key -o "$nen_tmp/caddy.key"
gpg --batch --dearmor -o "$nen_tmp/caddy.gpg" "$nen_tmp/caddy.key"
install -o root -g root -m 0644 "$nen_tmp/caddy.gpg" /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -fsSL --connect-timeout 15 --max-time 120 https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt -o "$nen_tmp/caddy.list"
install -o root -g root -m 0644 "$nen_tmp/caddy.list" /etc/apt/sources.list.d/caddy-stable.list
apt-get update
env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y caddy

# The package starts its default web page. Replace only this new Caddy instance.
systemctl stop caddy.service
nen_version="$(caddy version | awk '{print $1}')"
dpkg --compare-versions "${nen_version#v}" ge 2.11.7
cp -p /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.before-nen-${nen_stamp}"

# Only the challenge/maintenance page is public until TLS and cookies are ready.
nen_config bootstrap > "$nen_tmp/Caddyfile"
caddy fmt --overwrite "$nen_tmp/Caddyfile"
caddy validate --adapter caddyfile --config "$nen_tmp/Caddyfile"
install -o root -g caddy -m 0644 "$nen_tmp/Caddyfile" /etc/caddy/Caddyfile

if command -v ufw >/dev/null; then
  nen_ufw_status="$(LC_ALL=C ufw status)"
  if grep -q '^Status: active' <<< "$nen_ufw_status"; then
    ufw allow 80/tcp
    ufw allow 8443/tcp
  fi
fi
systemctl enable --now caddy.service

printf '\nWaiting up to 180 seconds for a trusted IP certificate. TCP 80 must be reachable from the Internet.\n'
nen_deadline=$((SECONDS + 180))
until curl --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 8 \
    --connect-to "${nen_ip}:${nen_port}:127.0.0.1:${nen_port}" \
    -o /dev/null "https://${nen_ip}:${nen_port}/" 2> "$nen_tmp/tls-error"; do
  if (( SECONDS >= nen_deadline )); then
    cat "$nen_tmp/tls-error" >&2
    journalctl -u caddy.service -n 60 --no-pager
    printf 'Certificate is not ready. Check inbound TCP 80 and 8443 in the hosting firewall. Xray and the API cookie setting are unchanged; Caddy is serving the maintenance page only.\n' >&2
    exit 1
  fi
  sleep 3
done

# Change the existing env file only after certificate validation has succeeded.
cp -p /etc/nen/api.env "/etc/nen/api.env.before-caddy-${nen_stamp}"
sed -i 's/^PACT_COOKIE_SECURE=false$/PACT_COOKIE_SECURE=true/' /etc/nen/api.env
chown root:nen /etc/nen/api.env
chmod 0640 /etc/nen/api.env
systemctl restart nen-api.service
curl -fsS --retry 12 --retry-connrefused --retry-delay 1 --max-time 10 http://127.0.0.1:8000/api/v1/health
printf '\n'

nen_config app > "$nen_tmp/Caddyfile"
caddy fmt --overwrite "$nen_tmp/Caddyfile"
caddy validate --adapter caddyfile --config "$nen_tmp/Caddyfile"
install -o root -g caddy -m 0644 "$nen_tmp/Caddyfile" /etc/caddy/Caddyfile
systemctl reload caddy.service

printf '\nChecking HTTPS API proxy...\n'
curl -fsS --noproxy '*' --connect-timeout 5 --max-time 20 \
  --connect-to "${nen_ip}:${nen_port}:127.0.0.1:${nen_port}" "https://${nen_ip}:${nen_port}/api/v1/health"
printf '\nChecking HTTPS home page...\n'
curl -fsS --noproxy '*' --connect-timeout 5 --max-time 20 -o /dev/null \
  --connect-to "${nen_ip}:${nen_port}:127.0.0.1:${nen_port}" "https://${nen_ip}:${nen_port}/"
printf '\nChecking Secure and HttpOnly session cookies...\n'
curl -fsS --noproxy '*' --connect-timeout 5 --max-time 20 -X POST \
  -D "$nen_tmp/logout.headers" -o /dev/null \
  --connect-to "${nen_ip}:${nen_port}:127.0.0.1:${nen_port}" "https://${nen_ip}:${nen_port}/api/v1/auth/logout"
python3 - "$nen_tmp/logout.headers" <<'PY'
from pathlib import Path
import sys
headers = Path(sys.argv[1]).read_text(encoding="iso-8859-1").lower().splitlines()
cookie = next(line for line in headers if line.startswith("set-cookie: nen_session="))
assert "; secure" in cookie and "; httponly" in cookie, "Session cookie flags are missing"
print("Secure and HttpOnly flags verified.")
PY

systemctl --no-pager --full status caddy.service nen-api.service nen-web.service
printf '\nServer checks passed. Open https://%s:%s/ from your computer to confirm external access.\n' "$nen_ip" "$nen_port"
