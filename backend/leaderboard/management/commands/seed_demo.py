from django.core.management.base import BaseCommand
from django.db import transaction

from leaderboard.dates import today_eastern
from leaderboard.models import Family
from leaderboard.seed import DEMO_INVITE_CODE, seed_demo_family


class Command(BaseCommand):
    help = "Create the Demo Family (invite code DEMO) with about 4 weeks of steps. Does nothing if it already exists."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the Demo Family and seed it again, so its history runs through today.",
        )

    def handle(self, *args, reset: bool, **options):
        with transaction.atomic():  # a reset never leaves the demo family deleted but not re-created
            if reset:
                deleted, _ = Family.objects.filter(invite_code=DEMO_INVITE_CODE).delete()
                if deleted:
                    self.stdout.write("Deleted the existing Demo Family.")
            family = seed_demo_family(today_eastern())

        if family is None:
            self.stdout.write("Demo Family already exists; nothing to do. Use --reset to seed it again.")
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {family.name} (invite code {family.invite_code}): {family.members.count()} members, "
                f"steps from {family.start_date} through {today_eastern()}."
            )
        )
