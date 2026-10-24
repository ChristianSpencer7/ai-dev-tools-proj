#!/usr/bin/env bash
# A read-only health report of the production server, safe to paste into an AI tool or commit (ops/README.md).
#
# On the server, in /srv/stepboard:
#   ./ops/collect.sh                  # once this is on main
#   git fetch -q origin <branch> && git show FETCH_HEAD:ops/collect.sh | bash   # from a branch, changing nothing
#
# It never reads .env and never runs `docker compose config` (which prints the settings, secrets included).
# Visitors' IP addresses and anything shaped like a Discord webhook URL are replaced before anything is printed.
set -uo pipefail
cd /srv/stepboard 2>/dev/null || cd "$(dirname "$0")/.."

SITE="${SITE:-159-89-228-242.sslip.io}"
SERVER_IP="${SERVER_IP:-159.89.228.242}"
compose() { docker compose -f docker-compose.yml -f docker-compose.prod.yml "$@"; }

# Keeps private and loopback addresses (Docker's own network) and the server's public address, which is in the
# site's name anyway; any other IPv4 address, and every IPv6 address, becomes <ip>.
redact() {
  sed -E \
    -e 's#https://(canary\.|ptb\.)?discord(app)?\.com/api/webhooks/[^[:space:]"]+#<discord-webhook-url>#g' \
    -e 's#((password|secret|token)[=:][[:space:]]*)[^[:space:],"]+#\1<redacted>#Ig' \
    | python3 -c '
import ipaddress, re, sys
keep = {sys.argv[1]}
def swap(m):
    text = m.group(0)
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return text
    return text if text in keep or ip.is_private or ip.is_loopback or ip.is_unspecified else "<ip>"
pattern = re.compile(r"(?<![\w.:])(?:\d{1,3}(?:\.\d{1,3}){3}|[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7})(?![\w.:])")
for line in sys.stdin:
    sys.stdout.write(pattern.sub(swap, line))
' "$SERVER_IP"
}

section() { printf '\n===== %s =====\n' "$1"; }

{
  section "Report"
  echo "Taken: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "Deployed commit: $(git log -1 --format='%h %s (%cs)' 2>/dev/null)"
  echo "Host uptime: $(uptime -p 2>/dev/null || uptime)"

  section "Containers (docker compose ps)"
  compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}\t{{.Ports}}'

  section "Resource use (docker stats)"
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'

  section "Disk, memory and load"
  df -h / | sed -n '1,2p'
  free -h
  echo "Load average: $(cut -d' ' -f1-3 /proc/loadavg)"
  echo "Docker disk use:"
  docker system df

  section "Health, from inside the backend (database included)"
  compose exec -T backend python -c "import urllib.request as u; r = u.urlopen('http://localhost:8000/health', timeout=5); print(r.status, r.read().decode())" 2>&1

  section "The public site, through Caddy"
  for path in /api/health /api/families /; do
    curl -s -o /dev/null --max-time 10 -w "GET https://$SITE$path -> %{http_code} in %{time_total}s\n" "https://$SITE$path"
  done
  curl -s -o /dev/null --max-time 10 -w "GET http://$SITE/ -> %{http_code}, redirects to %{redirect_url}\n" "http://$SITE/"

  section "HTTPS certificate"
  echo | openssl s_client -connect localhost:443 -servername "$SITE" 2>/dev/null | openssl x509 -noout -subject -issuer -dates

  section "Django's deployment checks"
  compose exec -T backend python manage.py check --deploy 2>&1 | tail -5

  section "Scheduler: when the digests run next"
  compose logs --no-color scheduler 2>&1 | grep -A3 "Next runs" | tail -4

  for service in caddy backend scheduler frontend db; do
    section "Logs: $service (last 25 lines)"
    compose logs --no-color --timestamps --tail 25 "$service" 2>&1
  done
} 2>&1 | redact
