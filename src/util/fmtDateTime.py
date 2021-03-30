from datetime import datetime, timedelta, timezone
from typing import NamedTuple

CLOCKS = [
    "🕛",
    "🕧",
    "🕐",
    "🕜",
    "🕑",
    "🕝",
    "🕒",
    "🕞",
    "🕓",
    "🕟",
    "🕔",
    "🕠",
    "🕕",
    "🕡",
    "🕖",
    "🕢",
    "🕗",
    "🕣",
    "🕘",
    "🕤",
    "🕙",
    "🕥",
    "🕚",
    "🕦",
    "🕛",
]


class FmtDateTime(NamedTuple):
    meridies: str
    shortDate: str
    date: str
    time: str
    dayOfWeek: str
    clockEmoji: str
    dateObj: datetime

    @classmethod
    def now(cls) -> "FmtDateTime":

        # Production and development environment are in different time zones, so we convert all times from UTC manually
        now = datetime.now(timezone.utc) + timedelta(hours=8)

        idx = round(2 * (now.hour + now.minute / 60) % 24)

        return FmtDateTime(
            meridies="AM" if now.hour < 12 else "PM",
            shortDate=now.strftime("%d/%m/%y"),
            date=now.strftime("%d/%m/%Y"),
            time=now.strftime("%H:%M"),
            dayOfWeek=now.strftime("%A"),
            clockEmoji=CLOCKS[idx],
            dateObj=now,
        )
