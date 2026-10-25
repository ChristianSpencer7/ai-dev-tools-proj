#!/usr/bin/env bash
# Planned failure: a digest whose Discord post fails. Checks two rules from AGENTS.md on the running deployment:
# a failed post must never lose a digest, and the webhook URL must never be logged.
#
# On the server: /srv/stepboard/ops/drill-webhook.sh, or for a branch's version, see ops/README.md.
# Nothing the app runs is changed: each case is a one-off container (docker compose run) given a broken webhook
# on the command line, so .env and the running backend keep their own setting. The digests go to a temporary
# "Webhook drill" family, deleted at the end however the drill ends: the Demo Family's digests are never posted
# (openapi.yaml), so they can't test a failed post, and a real family shouldn't get drill digests.
set -uo pipefail
OPS="$(cd "$(dirname "$0")" && pwd)"
cd "${APP_DIR:-/srv/stepboard}"  # set APP_DIR, COMPOSE_FILES and BASE_URL to rehearse it on a local stack

SITE="${SITE:-159-89-228-242.sslip.io}"
BASE_URL="${BASE_URL:-https://$SITE}"
SERVER_IP="${SERVER_IP:-159.89.228.242}"
AS_OF="${AS_OF:-$(date -u +%F)}"
DRILL_FAMILY="Webhook drill"
MARK="stepboard-drill"  # in both broken URLs below; it must not appear in any log
REJECTED="https://discord.com/api/webhooks/0/$MARK-not-a-real-token"  # Discord answers, and refuses it
UNREACHABLE="https://$MARK.invalid/api/webhooks/0/$MARK-token"         # .invalid never resolves: no request leaves
compose() { docker compose ${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml} "$@"; }
redact() { "${PYTHON:-python3}" "$OPS/redact.py" --keep "$SERVER_IP"; }
section() { printf '\n===== %s =====\n' "$1"; }

# Python in a throwaway backend container, optionally with a webhook set: django_shell [webhook] code
django_shell() {
  local webhook="$1"; shift
  compose run --rm --no-deps -T ${webhook:+-e DISCORD_WEBHOOK_URL="$webhook"} backend \
    python manage.py shell -v 0 -c "$1" 2>&1
}

delete_drill_family() {
  django_shell "" "
from leaderboard.models import Family
deleted = Family.objects.filter(name='$DRILL_FAMILY').delete()[0]
print('removed the drill family' if deleted else 'nothing to remove')
"
}

send_drill_digest() {  # webhook, kind. Prints "saved message <id> discord_status <status>".
  django_shell "$1" "
from datetime import date
from leaderboard.digests import send_digest
from leaderboard.models import Family
message = send_digest(Family.objects.get(pk=$drill_id), '$2', date.fromisoformat('$AS_OF'))
print('saved message', message.id, 'discord_status', message.discord_status)
"
}

# All output goes through redact.py; the drill runs in this shell, so its cleanup trap fires however it ends.
exec > >(redact) 2>&1
redact_pid=$!
trap '' PIPE
trap 'section "Cleanup"; delete_drill_family; exec >&- 2>&-; wait "$redact_pid" 2>/dev/null' EXIT
trap 'exit 130' INT TERM HUP

section "Drill: a Discord post that fails"
echo "Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC'), deployed commit $(git log -1 --format='%h'), digests as of $AS_OF"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

section "The running backend's own webhook setting (only whether one is set), before"
compose exec -T backend python manage.py shell -v 0 -c "from django.conf import settings; print('set' if settings.DISCORD_WEBHOOK_URL else 'not set')"

section "A temporary family for the drill's digests"
delete_drill_family  # in case an earlier run was cut off before its cleanup
# Its code is kept in a variable and never printed: a family's code is its password.
read -r drill_id drill_code < <(django_shell "" "
from leaderboard.invites import unique_invite_code
from leaderboard.models import Family
family = Family.objects.create(name='$DRILL_FAMILY', start_date='$AS_OF', invite_code=unique_invite_code())
print(family.id, family.invite_code)
" | tail -1)
if [[ ! "${drill_id:-}" =~ ^[0-9]+$ || -z "${drill_code:-}" ]]; then
  echo "Couldn't create the drill family; stopping. Is the backend running? (dc ps)"
  exit 1
fi
echo "Created \"$DRILL_FAMILY\", id $drill_id"

section "1. Discord refuses the webhook (a real Discord address with a made-up token)"
out1="$(send_drill_digest "$REJECTED" weekly)"; echo "$out1"

section "2. The webhook's host can't be reached (an .invalid address; nothing is sent)"
out2="$(send_drill_digest "$UNREACHABLE" monthly)"; echo "$out2"

section "The two digests, as the app shows them (GET /api/families/$drill_id/messages, with the family's code)"
curl -s --max-time 10 -H "X-Family-Code: $drill_code" "$BASE_URL/api/families/$drill_id/messages" | "${PYTHON:-python3}" -c '
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
