"""Generic iCalendar feeds.

Museums and universities usually publish one. Follow the site's
"subscribe" or "add to calendar" link; whatever URL that points at is
the feed. Woodmere and the Villanova series are the expected users.

Deliberately a small hand-rolled parser rather than a dependency: these
feeds are simple, and one fewer package is one fewer thing to pin.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ..http import fetch
from ..model import Event

_LOCAL = timezone(timedelta(hours=-4))   # America/New_York, DST-agnostic fallback


def _unfold(body: str) -> list[str]:
    lines: list[str] = []
    for raw in body.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_dt(value: str, params: str) -> tuple[str, str | None]:
    """Return (YYYY-MM-DD, "7:30pm" or None for all-day)."""
    value = value.strip()
    if "VALUE=DATE" in params.upper() or len(value) == 8:
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}", None

    text = value.rstrip("Z")
    moment = datetime.strptime(text[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        moment = moment.replace(tzinfo=timezone.utc).astimezone(_LOCAL)
    suffix = "am" if moment.hour < 12 else "pm"
    return moment.date().isoformat(), f"{moment.hour % 12 or 12}:{moment.minute:02d}{suffix}"


def pull(source: dict) -> list[Event]:
    body = fetch(source["url"])
    events: list[Event] = []
    current: dict[str, tuple[str, str]] = {}
    inside = False

    for line in _unfold(body):
        if line.startswith("BEGIN:VEVENT"):
            inside, current = True, {}
            continue
        if line.startswith("END:VEVENT"):
            inside = False
            summary = _unescape(current.get("SUMMARY", ("", ""))[1])
            start = current.get("DTSTART")
            if summary and start:
                day, clock = _parse_dt(start[1], start[0])
                events.append(
                    Event(
                        venueId=source["venueId"],
                        title=summary,
                        date=day,
                        times=[clock] if clock else [],
                        note=_unescape(current.get("DESCRIPTION", ("", ""))[1])[:200],
                        url=_unescape(current.get("URL", ("", ""))[1]) or source.get("ticketUrl", ""),
                        source=source["id"],
                    )
                )
            continue
        if not inside or ":" not in line:
            continue
        head, _, value = line.partition(":")
        name, _, params = head.partition(";")
        current[name.upper()] = (params, value)

    return events
