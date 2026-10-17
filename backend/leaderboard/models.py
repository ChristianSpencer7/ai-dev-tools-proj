"""Tables for families, members, daily step totals and digest messages.

Choice values match the enums in openapi.yaml.
"""

from django.db import models


class Family(models.Model):
    name = models.CharField(max_length=80)
    start_date = models.DateField(help_text="First day that counts toward the leaderboards (Eastern).")
    invite_code = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "families"

    def __str__(self) -> str:
        return self.name


class Member(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="members")
    name = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]  # like GET /families/{id}/members

    def __str__(self) -> str:
        return f"{self.name} ({self.family})"


class StepEntry(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual"
        IMPORT = "import"
        SEED = "seed"
        SHORTCUT = "shortcut"
        FITBIT = "fitbit"
        GARMIN = "garmin"

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="steps")
    day = models.DateField(help_text="Calendar day in Eastern time.")
    steps = models.PositiveIntegerField()
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "step entries"
        ordering = ["-day"]  # newest first, like GET /members/{id}/steps
        constraints = [
            # One total per member per day: logging the day again replaces it (update_or_create).
            models.UniqueConstraint(fields=["member", "day"], name="one_entry_per_member_day"),
            # PositiveIntegerField already blocks negatives; this caps the top of the 0–100,000 range.
            models.CheckConstraint(condition=models.Q(steps__lte=100_000), name="steps_at_most_100000"),
        ]

    def __str__(self) -> str:
        return f"{self.member.name}, {self.day}: {self.steps:,}"


class Message(models.Model):
    class Kind(models.TextChoices):
        WEEKLY = "weekly"
        MONTHLY = "monthly"

    class DiscordStatus(models.TextChoices):
        NOT_CONFIGURED = "not_configured"
        SENT = "sent"
        FAILED = "failed"

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="messages")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    text = models.TextField()
    discord_status = models.CharField(max_length=16, choices=DiscordStatus.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]  # newest first, like GET /families/{id}/messages

    def __str__(self) -> str:
        when = f", {self.created_at:%Y-%m-%d}" if self.created_at else ""  # unset until saved
        return f"{self.get_kind_display()} digest for {self.family}{when}"
