from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from leaderboard.dates import today_eastern
from leaderboard.digests import send_scheduled_digests
from leaderboard.models import Message


class Command(BaseCommand):
    help = (
        "Send a weekly or monthly digest to every family, counting through yesterday (Eastern). "
        "Families that already have it are skipped, so it is safe to run again."
    )

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=Message.Kind.values, help="weekly, or monthly (all-time totals)")
        parser.add_argument(
            "--as-of",
            type=date.fromisoformat,
            help="Last day to count, YYYY-MM-DD (default: yesterday). For reruns and testing.",
        )
        parser.add_argument(
            "--include-demo",
            action="store_true",
            help="Also make the Demo Family's digest. It's saved for the Messages page but never posted to Discord.",
        )

    def handle(self, *args, kind: str, as_of: date | None, include_demo: bool, **options):
        as_of = as_of or today_eastern() - timedelta(days=1)
        run = send_scheduled_digests(kind, as_of, include_demo=include_demo)

        sent = len(run.sent)
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} {kind} digest{'s' if sent != 1 else ''} (as of {as_of})."))
        for message in run.sent:
            self.stdout.write(f"  {message.family.name}: {message.discord_status.replace('_', ' ')}")
        if run.skipped:
            self.stdout.write("Skipped: " + ", ".join(f"{family.name} ({reason})" for family, reason in run.skipped) + ".")
        if run.failed:
            for family, error in run.failed:
                self.stderr.write(f"Failed: {family.name} ({error}); see the log for details.")
            raise CommandError(f"{len(run.failed)} of {sent + len(run.failed)} digests failed")
