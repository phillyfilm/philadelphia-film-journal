"""Shared data model for the Philadelphia Film Journal pipeline.

Two things live here: the Event and Venue records that every adapter
produces, and the time-handling rules that the calendar and map
reimplement in JavaScript. If you change a rule here, change it in
both index.html files too -- tests/test_time.py documents the contract
but cannot enforce it across languages.

The time rules, in full:

  * A bare hour with no meridiem means afternoon or evening. Cinemas
    almost never show a film at 7:30 in the morning, so "7:30" is
    19:30. This is the single most useful assumption in the project.
  * A morning showing in hand-typed data must say so: "10:30am".
  * Anything 13 or greater is read as a 24-hour clock and converted.
  * "12" is noon; "12:15am" is a quarter past midnight.
  * Values that are not clock times at all -- "Dusk", "Sunset",
    "After the lecture" -- pass through untouched and sort last.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# 7:30, 7:30pm, 7:30 p.m., 19:30, 7pm, 7 PM
_CLOCK = re.compile(
    r"^\s*(\d{1,2})\s*(?::\s*(\d{2}))?\s*(?:([ap])\.?\s*m?\.?)?\s*$",
    re.IGNORECASE,
)


def parse_time(value: Any) -> Optional[int]:
    """Return minutes since midnight, or None if this is not a clock time."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    match = _CLOCK.match(text)
    if not match:
        # Bare "1930" is ambiguous enough that we refuse it rather than guess.
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()

    if minute > 59:
        return None

    if meridiem == "a":
        if hour == 12:
            hour = 0
        elif hour > 12:
            return None
    elif meridiem == "p":
        if hour < 12:
            hour += 12
        elif hour > 12:
            return None
    else:
        # No meridiem given.
        if hour > 23:
            return None
        if hour == 0:
            pass          # midnight, stated as 0:15
        elif hour == 12:
            pass          # noon
        elif hour > 12:
            pass          # 24-hour clock, already correct
        else:
            hour += 12    # the cinema assumption

    return hour * 60 + minute


def format_time(value: Any) -> str:
    """Render a time for display: 7:30pm, 10:30am, or the original string."""
    minutes = parse_time(value)
    if minutes is None:
        return str(value).strip()

    hour, minute = divmod(minutes, 60)
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d}{suffix}"


def normalize_time(value: Any) -> str:
    """Canonical storage form. Unparseable values keep their own text."""
    return format_time(value)


def sort_times(values: list[Any]) -> list[str]:
    """Chronological, with non-clock values alphabetical at the end."""
    def key(v: Any) -> tuple[int, int, str]:
        minutes = parse_time(v)
        if minutes is None:
            return (1, 0, str(v).lower())
        return (0, minutes, "")

    return [normalize_time(v) for v in sorted(values, key=key)]


def time_from_iso(stamp: str) -> str:
    """Take an ISO timestamp from a real API and emit an unambiguous time.

    Machine sources always know whether they mean morning or evening, so
    the pipeline writes the meridiem explicitly. Hand-typed rows in
    manual.csv are the only place ambiguity can enter the system.
    """
    from datetime import datetime

    text = stamp.strip().replace("Z", "+00:00")
    moment = datetime.fromisoformat(text)
    hour, minute = moment.hour, moment.minute
    suffix = "am" if hour < 12 else "pm"
    return f"{hour % 12 or 12}:{minute:02d}{suffix}"


@dataclass
class Venue:
    id: str
    name: str
    category: str = ""
    operator: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    county: str = ""
    tier: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    coordPrecision: str = "unknown"
    website: str = ""
    ticketUrl: str = ""
    profile: str = ""
    policy: str = "all"          # all | special-only | excluded
    inScope: bool = True
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Event:
    venueId: str
    title: str
    date: str                     # YYYY-MM-DD, Philadelphia local
    times: list[str] = field(default_factory=list)
    id: str = ""
    year: Optional[int] = None
    director: str = ""
    format: str = ""              # 35mm, 16mm, DCP, digital
    series: str = ""
    type: str = "screening"       # screening | special | community | talk
    note: str = ""
    featured: bool = False
    url: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        self.times = sort_times(self.times)
        if not self.id:
            self.id = self.make_id()

    def make_id(self) -> str:
        import hashlib

        seed = f"{self.venueId}|{self.date}|{self.title.lower()}"
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self)
