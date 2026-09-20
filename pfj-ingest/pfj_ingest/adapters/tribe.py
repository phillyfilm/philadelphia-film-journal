"""WordPress + The Events Calendar (the "tribe" REST API).

An enormous share of small arts venues run this plugin, and it exposes
/wp-json/tribe/events/v1/events without authentication. PhilaMOCA is
the known user here. Check the URL in a browser first: if it returns
JSON, this is the whole integration.
"""

from __future__ import annotations

from ..http import FetchError, fetch_json
from ..model import Event, time_from_iso


def pull(source: dict) -> list[Event]:
    url = source["url"]
    joiner = "&" if "?" in url else "?"
    payload = fetch_json(f"{url}{joiner}per_page=50")
    if not isinstance(payload, dict):
        raise FetchError(f"{source['id']}: expected an object from the tribe API")

    events: list[Event] = []
    for record in payload.get("events", []):
        title = (record.get("title") or "").strip()
        start = record.get("start_date") or ""
        if not title or not start:
            continue
        day = start[:10]
        clock = time_from_iso(start.replace(" ", "T")) if len(start) > 10 else None
        events.append(
            Event(
                venueId=source["venueId"],
                title=title,
                date=day,
                times=[clock] if clock else [],
                note=(record.get("excerpt") or "").strip()[:200],
                url=record.get("website") or record.get("url") or source.get("ticketUrl", ""),
                source=source["id"],
            )
        )
    return events
