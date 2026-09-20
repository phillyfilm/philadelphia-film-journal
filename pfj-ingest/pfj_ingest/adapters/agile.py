"""Agile Ticketing -- PFS's three houses, BMFI, and the Colonial.

Agile runs ticketing for five of the region's highest-priority venues,
which makes this the most valuable adapter in the project. Access is
issued per organization: the venue's box office manager can enable API
access and give you an organization ID and a key. Ask for "read-only
access to our event and showing data for a listings calendar."

Agile nests showings inside events -- one event ("Paris, Texas")
carries many showings, each with a start time and its own buy link.
That maps cleanly onto the Journal, which wants one title with its
times underneath.

Confirm field names against a real payload with `pfj probe --source bmfi`
before launch; the mapping lives entirely in _showings().
"""

from __future__ import annotations

import os
from collections import defaultdict

from ..http import FetchError, fetch_json
from ..model import Event, time_from_iso


def _showings(event_record: dict) -> list[dict]:
    for key in ("Showings", "showings", "Sessions", "sessions", "Performances"):
        value = event_record.get(key)
        if isinstance(value, list):
            return value
    return []


def _start(showing: dict) -> str | None:
    for key in ("StartDate", "startDate", "Start", "start", "ShowingTime"):
        value = showing.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def pull(source: dict) -> list[Event]:
    token = os.environ.get(source["tokenEnv"], "").strip()
    if not token:
        raise FetchError(
            f"{source['id']}: no key in ${source['tokenEnv']}. "
            "Add it as a repository secret and to the workflow env block."
        )
    if "REPLACE" in source["url"]:
        raise FetchError(
            f"{source['id']}: config/sources.json still has a placeholder URL. "
            "Fill in the Agile host and organizationId the venue gives you."
        )

    headers = {source.get("tokenHeader", "x-api-key"): token, "Accept": "application/json"}
    payload = fetch_json(source["url"], headers=headers)

    records = payload if isinstance(payload, list) else payload.get("Items") or payload.get("events") or []
    events: list[Event] = []

    for record in records:
        title = (record.get("Name") or record.get("Title") or record.get("name") or "").strip()
        if not title:
            continue
        grouped: dict[str, list[str]] = defaultdict(list)
        links: dict[str, str] = {}
        for showing in _showings(record):
            start = _start(showing)
            if not start:
                continue
            day = start[:10]
            grouped[day].append(time_from_iso(start))
            link = showing.get("PurchaseUrl") or showing.get("Url") or ""
            if link and day not in links:
                links[day] = link

        for day, times in grouped.items():
            events.append(
                Event(
                    venueId=source["venueId"],
                    title=title,
                    date=day,
                    times=times,
                    note=(record.get("ShortDescription") or "").strip()[:200],
                    url=links.get(day) or record.get("Url") or source.get("ticketUrl", ""),
                    source=source["id"],
                )
            )
    return events
