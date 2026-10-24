#!/usr/bin/env bash
# Planned failure: stop the database, record what breaks and what the checks show, start it again, and time how
# long the app takes to recover. About three minutes of errors on the live site; run it at a quiet time.
#
# On the server: /srv/stepboard/ops/drill-database.sh, or for a branch's version, see ops/README.md.
# The database is started again however the script ends, even on Ctrl+C. Output goes through ops/redact.py.
set -uo pipefail
OPS="$(cd "$(dirname "$0")" && pwd)"
cd "${APP_DIR:-/srv/stepboard}"  # set APP_DIR, COMPOSE_FILES and BASE_URL to rehearse it on a local stack

SITE="${SITE:-159-89-228-242.sslip.io}"
BASE_URL="${BASE_URL:-https://$SITE}"
SERVER_IP="${SERVER_IP:-159.89.228.242}"
DOWN_FOR="${DOWN_FOR:-120}"  # seconds; the health check (every 30 s, 3 failures) needs up to about 100 to say unhealthy
compose() { docker compose ${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml} "$@"; }
redact() { "${PYTHON:-python3}" "$OPS/redact.py" --keep "$SERVER_IP"; }
section() { printf '\n===== %s =====\n' "$1"; }
status() { curl -s -o /dev/null --max-time 10 -w '%{http_code} (%{time_total}s)' "$BASE_URL$1"; }  # code and time taken
probe() {
  printf '%s  /api/health %s  /api/families %s  / %s  | backend: %s | db: %s\n' "$(date -u +%H:%M:%S)" \
    "$(status /api/health)" "$(status /api/families)" "$(status /)" \
    "$(compose ps --all --format '{{.Status}}' backend)" "$(compose ps --all --format '{{.Status}}' db)"
}

{
  # Whatever happens, the database comes back: on a normal end, an error, or Ctrl+C.
  trap 'section "Cleanup"; compose start db 2>&1' EXIT
  trap 'exit 130' INT TERM

  section "Drill: stop the database"
  echo "Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC'), deployed commit $(git log -1 --format='%h')"

  section "Before"
  probe

  section "Stopping the database"
  stopped_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  compose stop db 2>&1

  section "During: about every 5 seconds for ${DOWN_FOR}s (by the clock: each check can take seconds now)"
  until_time=$(( $(date +%s) + DOWN_FOR ))
  while [ "$(date +%s)" -lt "$until_time" ]; do probe; sleep 5; done

  section "What a visitor gets"
  for path in /api/health /api/families; do
    echo "--- GET $path"
    curl -s -i --max-time 10 "$BASE_URL$path" | sed -n '1p;/^[Cc]ontent-[Tt]ype/p;/^\r\{0,1\}$/,$p' | head -c 600
    echo
  done

  section "Containers, with the database stopped"
  compose ps --all --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'

  section "Backend logs since the stop: the errors, by kind"
  logs="$(compose logs --no-color --timestamps --since "$stopped_at" backend 2>&1)"
  # A 500's traceback is many lines; its first line (ERROR django.request) and last (the exception) say what failed.
  errors="$(grep -E 'ERROR |^[^ ]+ +[|] +[^ ]+ +[A-Za-z_.]+(Error|Exception): ' <<<"$logs" | sed -E 's/^[^|]*[|] +[^ ]+ +//; s/^[0-9-]+ [0-9:,]+ //')"
  if [ -n "$errors" ]; then sort <<<"$errors" | uniq -c | sort -rn | head -10; else echo "(none: no error was logged)"; fi

  section "Backend requests since the stop (health checks left out, then counted)"
  grep -E '"(GET|POST|PUT|PATCH|DELETE|HEAD) ' <<<"$logs" | grep -v 'GET /health HTTP' | tail -20
  echo "(health checks in that time: $(grep -c 'GET /health HTTP' <<<"$logs"), of which failed: $(grep 'GET /health HTTP' <<<"$logs" | grep -vc '" 200 '))"

  section "Starting the database"
  started=$(date +%s)
  compose start db 2>&1

  section "Recovery: every 3 seconds until the site answers and the backend is healthy again (at most 3 minutes)"
  site_ok=""
  give_up=$(( $(date +%s) + 180 ))
  while [ "$(date +%s)" -lt "$give_up" ]; do
    line="$(probe)"; echo "$line"
    if [ -z "$site_ok" ] && [[ "$line" == *"/api/families 200 "* ]]; then site_ok=$(( $(date +%s) - started )); fi
    if [[ "$line" == *"/api/families 200 "* && "$line" == *"(healthy)"* ]]; then break; fi
    sleep 3
  done
  echo "Site answering again after: ${site_ok:-?}s; backend healthy again after: $(( $(date +%s) - started ))s"

  section "Backend logs since the restart"
  compose logs --no-color --timestamps --since "$(date -u -d "@$started" +%Y-%m-%dT%H:%M:%SZ)" backend 2>&1 | grep -v 'GET /health HTTP/1.1" 200' | tail -20

  section "After"
  compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
} 2>&1 | redact
