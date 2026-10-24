# Product Spec — Family Step Leaderboard

Design background and the 8-day schedule are in [docs/plan.md](docs/plan.md). The API contract is [openapi.yaml](openapi.yaml).

## Problem

A family wants a light, friendly competition around daily walking. Everyone uses different watches (or none), so the app needs one place to record daily step totals and show who's ahead this week and overall.

## Users

- **Family member:** joins their family, logs daily steps, checks the boards.
- **Peer reviewer:** has no watch and no family. Needs to see a working app right after `docker compose up`, with no outside accounts.

## Features

### Families and members
- Create a family with a name and a start date (default: today, Eastern). The family gets a 6-character invite code.
- Join a family with its invite code and a display name. Codes are not case-sensitive.
- Family and member names can't contain line breaks, tabs or other control characters; emoji and accents are fine.
- Only the person who creates a family is shown its invite code; listing or looking up families never shows it.
- The demo family's invite code is `DEMO`.

### Logging steps
- A member logs a day's total for any day up to today (Eastern). Totals are whole numbers from 0 to 100,000.
- Logging the same day again **replaces** the earlier total.
- `POST /steps` accepts one or many days in one request (up to 366), so later integrations (Apple Shortcut, Fitbit, Garmin) can send data without changing the API. Each entry records its source.

### Leaderboards
- **Weekly:** Monday 12:00 AM through Sunday 11:59 PM Eastern. Mid-week, it shows the week so far, compared with the same days last week.
- **All-time:** everything since the family's start date, compared with the totals at the end of the previous month.
- Ranked by total steps, most to fewest. Ties share a rank (1, 1, 3).
- Top three get 🥇🥈🥉; the rest are numbered.
- Each row shows rank movement (▲ / ▼ / —) and the step difference, or "new" if the member had no steps in the comparison period. The first period after a family starts shows no comparison.
- Callouts: best single day (earliest day wins a tie); most improved (weekly only, largest step gain, only if someone gained).
- Steps from before the family's start date never count.

### Messages (digests)
- **Weekly digest:** Mondays at 8:00 AM Eastern, final standings for the week that just ended.
- **Monthly digest:** the 1st at 8:00 AM Eastern, all-time totals through the last day of the previous month.
- Every digest is saved and shown on the Messages page, newest first.
- If `DISCORD_WEBHOOK_URL` is set, the digest is also posted to Discord. A failed post is recorded on the message and does not lose the digest.
- "Send digest now" builds a weekly or monthly digest on demand, counting through today.

### Demo data
- On first start, a seed script creates the Demo Family (Dad, Mom, Alex, Sam) with daily steps from 4 weeks before the current week through today (today is partial, so the weekly board is never empty). Running it again does nothing.

## Acceptance criteria

1. From a fresh clone, `docker compose up` starts the app at http://localhost:8080 with the demo boards already filled: medals, rank changes and callouts are visible.
2. A reviewer can join the demo family with code `DEMO`, log steps for today, and see the weekly board update.
3. Logging the same day twice keeps only the newer total.
4. Future days and totals outside 0–100,000 are rejected with a clear message.
5. "Send digest now" adds a message to the Messages page without any Discord setup.
6. With a webhook URL set, the same message also appears in the Discord channel.
7. The backend serves exactly the operations in `openapi.yaml` (checked by a test).

## Not in scope yet

Watch integrations, the Discord bot (`/join`, slash commands, private messages), sync alerts, the Thursday midweek post, and login. See the open questions in [docs/plan.md](docs/plan.md).
