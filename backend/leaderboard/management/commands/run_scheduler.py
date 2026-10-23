from django.core.management.base import BaseCommand

from leaderboard.scheduler import build_scheduler, next_runs


class Command(BaseCommand):
    help = (
        "Run the digest schedule until stopped: weekly digests on Mondays and monthly digests on the 1st, "
        "both at 8:00 AM Eastern. Each sends to every family, like send_digests."
    )

    def handle(self, *args, **options):
        scheduler = build_scheduler()
        self.stdout.write(self.style.SUCCESS("Digest scheduler started (Ctrl+C to stop). Next runs:"))
        for kind, when in next_runs().items():
            self.stdout.write(f"  {kind:8} {when:%a %b %d %Y, %I:%M %p %Z}")
        try:
            scheduler.start()  # blocks until stopped
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            if scheduler.running:
                scheduler.shutdown(wait=False)
        self.stdout.write("Digest scheduler stopped.")
