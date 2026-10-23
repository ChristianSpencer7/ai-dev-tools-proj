import pytest


TEST_FOLDERS = ("unit", "integration")


def pytest_collection_modifyitems(items):
    """Marks each test by its folder, so `pytest -m unit` and `pytest -m integration` work too.

    CI runs tests/unit and tests/integration separately, so a test anywhere else would never run there.
    """
    for item in items:
        folder = item.path.parent.name
        if folder not in TEST_FOLDERS:
            raise pytest.UsageError(f"{item.path.name}: put tests in tests/unit or tests/integration (see tests/README.md)")
        item.add_marker(folder)


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
