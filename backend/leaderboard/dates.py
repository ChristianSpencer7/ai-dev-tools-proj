from datetime import date

from django.utils import timezone


def today_eastern() -> date:
    """Today's date in Eastern time (settings.TIME_ZONE). A day ends at midnight Eastern."""
    return timezone.localdate()
