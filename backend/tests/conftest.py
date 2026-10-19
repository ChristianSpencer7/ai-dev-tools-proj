import pytest


@pytest.fixture(autouse=True)
def no_real_discord(settings, monkeypatch):
    """Tests never post to a real Discord channel, even with DISCORD_WEBHOOK_URL in .env.

    The webhook is cleared, and any request that still slips through fails the test. Tests that need
    Discord use the fake_discord fixture in test_digests.py instead.
    """
    settings.DISCORD_WEBHOOK_URL = None

    def refuse(*args, **kwargs):
        raise AssertionError("A test tried to reach Discord for real")

    monkeypatch.setattr("leaderboard.discord.httpx.post", refuse)
