#!/usr/bin/env bash
# A read-only health report of the production server, safe to paste into an AI tool or commit (ops/README.md).
#
# On the server: /srv/stepboard/ops/collect.sh, or for a branch's version, see ops/README.md.
# It never reads .env and never runs `docker compose config` (which prints the settings, secrets included).
# Everything goes through ops/redact.py: visitors' IP addresses and anything like a webhook URL are replaced.
set -uo pipefail
OPS="$(cd "$(dirname "$0")" && pwd)"  # this script's folder, for redact.py
cd /srv/stepboard  # the deployed app: its compose files and .env

SITE="${SITE:-159-89-228-242.sslip.io}"
SERVER_IP="${SERVER_IP:-159.89.228.242}"
compose() { docker compose -f docker-compose.yml -f docker-compose.prod.yml "$@"; }
redact() { python3 "$OPS/redact.py" --keep "$SERVER_IP"; }  # tested in ops/tests/test_redact.py
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
  # /api/family needs a family's code (openapi.yaml); the Demo Family's is public.
  for path in /api/health /api/family /; do
    curl -s -o /dev/null --max-time 10 -H 'X-Family-Code: DEMO' \
      -w "GET https://$SITE$path -> %{http_code} in %{time_total}s\n" "https://$SITE$path"
  done
  curl -s -o /dev/null --max-time 10 -w "GET http://$SITE/ -> %{http_code}, redirects to %{redirect_url}\n" "http://$SITE/"

  section "HTTPS certificate"
  echo | openssl s_client -connect localhost:443 -servername "$SITE" 2>/dev/null | openssl x509 -noout -subject -issuer -dates

  section "Django's deployment checks"
  compose exec -T backend python manage.py check --deploy 2>&1 | tail -5

  section "Scheduler: when the digests run next"
  compose logs --no-color scheduler 2>&1 | grep -E '(weekly|monthly) +[A-Z][a-z]{2} ' | tail -2

  for service in caddy backend scheduler frontend db; do
    section "Logs: $service (last 25 lines)"
    compose logs --no-color --timestamps --tail 25 "$service" 2>&1
  done
} 2>&1 | redact
