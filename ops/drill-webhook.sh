#!/usr/bin/env bash
# Planned failure: a digest whose Discord post fails. Checks two rules from AGENTS.md on the running deployment:
# a failed post must never lose a digest, and the webhook URL must never be logged.
#
# On the server: /srv/stepboard/ops/drill-webhook.sh, or for a branch's version, see ops/README.md.
# Nothing the app runs is changed: each case is a one-off container (docker compose run) given a broken webhook
# on the command line, so .env and the running backend keep their own setting. Only the Demo Family gets the two
# drill digests (the scheduler skips it, so real digests are unaffected); they stay on its Messages page.
set -uo pipefail
OPS="$(cd "$(dirname "$0")" && pwd)"
cd "${APP_DIR:-/srv/stepboard}"  # set APP_DIR, COMPOSE_FILES and BASE_URL to rehearse it on a local stack

SITE="${SITE:-159-89-228-242.sslip.io}"
BASE_URL="${BASE_URL:-https://$SITE}"
SERVER_IP="${SERVER_IP:-159.89.228.242}"
AS_OF="${AS_OF:-$(date -u +%F)}"
MARK="stepboard-drill"  # in both broken URLs below; it must not appear in any log
REJECTED="https://discord.com/api/webhooks/0/$MARK-not-a-real-token"  # Discord answers, and refuses it
UNREACHABLE="https://$MARK.invalid/api/webhooks/0/$MARK-token"         # .invalid never resolves: no request leaves
compose() { docker compose ${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml} "$@"; }
redact() { "${PYTHON:-python3}" "$OPS/redact.py" --keep "$SERVER_IP"; }
section() { printf '\n===== %s =====\n' "$1"; }

# One Demo Family digest, sent from a throwaway backend container with this webhook. Prints "id status".
send_demo_digest() {  # webhook, kind
  compose run --rm --no-deps -T -e DISCORD_WEBHOOK_URL="$1" backend python manage.py shell -v 0 -c "
from datetime import date
from leaderboard.digests import send_digest
from leaderboard.models import Family
from leaderboard.seed import DEMO_INVITE_CODE
message = send_digest(Family.objects.get(invite_code=DEMO_INVITE_CODE), '$2', date.fromisoformat('$AS_OF'))
print('saved message', message.id, 'discord_status', message.discord_status)
" 2>&1
}

{
  section "Drill: a Discord post that fails"
  echo "Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC'), deployed commit $(git log -1 --format='%h'), digests as of $AS_OF"
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  section "The running backend's own webhook setting (only whether one is set), before"
  compose exec -T backend python manage.py shell -v 0 -c "from django.conf import settings; print('set' if settings.DISCORD_WEBHOOK_URL else 'not set')"

  section "1. Discord refuses the webhook (a real Discord address with a made-up token)"
  out1="$(send_demo_digest "$REJECTED" weekly)"; echo "$out1"

  section "2. The webhook's host can't be reached (an .invalid address; nothing is sent)"
  out2="$(send_demo_digest "$UNREACHABLE" monthly)"; echo "$out2"

  section "The two digests, as the app shows them (GET /api/families/1/messages)"
  curl -s --max-time 10 "$BASE_URL/api/families/1/messages" | "${PYTHON:-python3}" -c '
import json, sys
wanted = set(sys.argv[1:])
for m in json.load(sys.stdin):
    if str(m["id"]) in wanted:
        print("id {id}  {kind:<8} discord_status={discord_status:<14} created {created_at}  text: {first}".format(first=m["text"].splitlines()[0], **m))
' $(grep -oE 'saved message [0-9]+' <<<"$out1 $out2" | awk '{print $3}')

  section "What was logged about the failures"
  grep -h 'Discord webhook post failed' <<<"$out1
$out2" | sed -E 's/^[0-9-]+ [0-9:,]+ //'

  section "Was either webhook URL logged? (counted before any redaction)"
  logs="$(compose logs --no-color --since "$started_at" 2>&1)"
  echo "In the drill's own output: $(grep -c "$MARK" <<<"$out1
$out2") lines"
  echo "In every service's logs since the drill started: $(grep -c "$MARK" <<<"$logs") lines"

  section "The running backend's own webhook setting, after (unchanged)"
  compose exec -T backend python manage.py shell -v 0 -c "from django.conf import settings; print('set' if settings.DISCORD_WEBHOOK_URL else 'not set')"
} 2>&1 | redact
