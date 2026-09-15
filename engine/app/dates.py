from datetime import UTC, datetime
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


def diary_date(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(BERLIN).date().isoformat()
