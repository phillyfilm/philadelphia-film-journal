"""schema.org JSON-LD scraped from a venue's public pages.

The last resort, for sites with no feed and no API. Many theme-built
sites embed <script type="application/ld+json"> blocks describing each
Event; where they do, this is far more stable than parsing HTML.

Always "review" trust: what the markup calls an Event may be a private
rental or a concert, so these land in the review queue rather than
publishing straight through.
"""

from __future__ import annotations

import json
import re

from ..http import fetch
from ..model import Event, time_from_iso

_BLOCK = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _walk(node, out: list[dict]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk(item, out)
    elif isinstance(node, dict):
        kind = node.get("@type", "")
        kinds = kind if isinstance(kind, list) else [kind]
        if any("event" in str(k).lower() for k in kinds):
            out.append(node)
        for value in node.values():
            if isinstance(value, (list, dict)):
                _walk(value, out)


def pull(source: dict) -> list[Event]:
    body = fetch(source["url"])
    found: list[dict] = []
    for block in _BLOCK.findall(body):
        try:
            _walk(json.loads(block), found)
        except json.JSONDecodeError:
            continue

    events: list[Event] = []
    for record in found:
        title = (record.get("name") or "").strip()
        start = record.get("startDate") or ""
        if not title or not start:
            continue
        day = start[:10]
        clock = time_from_iso(start) if len(start) > 10 else None
        events.append(
            Event(
                venueId=source["venueId"],
                title=title,
                date=day,
                times=[clock] if clock else [],
                url=record.get("url") or source.get("ticketUrl", ""),
                source=source["id"],
            )
        )
    return events
