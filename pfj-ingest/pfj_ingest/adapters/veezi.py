"""Veezi -- Renew Theaters' three houses (Ambler, County, Hiway).

One API shape covering three of the region's best-programmed venues,
which makes this the adapter to get working first. Veezi issues a
per-site WebSessions token; ask Renew's operations contact for
"read-only WebSessions API access for a listings calendar."

Two calls: /v1/websession returns every scheduled session with a FilmId
and a local start time; /v1/film returns the film records. Join them on
FilmId. Veezi start times are already local to the cinema, so they go
through time_from_iso unchanged.
"""

from __future__ import annotations

import os
from collections import defaultdict

from ..http import FetchError, fetch_json
from ..model import Event, time_from_iso


def pull(source: dict) -> list[Event]:
    token = os.environ.get(source["tokenEnv"], "").strip()
    if not token:
        raise FetchError(
            f"{source['id']}: no token in ${source['tokenEnv']}. "
            "Add it as a repository secret and to the workflow env block."
        )
    headers = {"VeeziAccessToken": token, "Accept": "application/json"}

    sessions = fetch_json(source["sessionsUrl"], headers=headers)
    films = fetch_json(source["filmsUrl"], headers=headers)
    if not isinstance(sessions, list) or not isinstance(films, list):
        raise FetchError(f"{source['id']}: unexpected payload shape")

    catalogue = {str(f.get("Id")): f for f in films}

    # One row per film per day, with every showtime underneath.
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for session in sessions:
        start = session.get("FeatureStartTime") or session.get("PreShowStartTime")
        film_id = str(session.get("FilmId", ""))
        if not start or not film_id:
            continue
        day = start[:10]
        grouped[(film_id, day)].append(time_from_iso(start))

    events: list[Event] = []
    for (film_id, day), times in grouped.items():
        film = catalogue.get(film_id, {})
        title = (film.get("Title") or "").strip()
        if not title:
            continue
        year = str(film.get("OpeningDate") or "")[:4]
        events.append(
            Event(
                venueId=source["venueId"],
                title=title,
                date=day,
                times=times,
                year=int(year) if year.isdigit() else None,
                format=(film.get("Format") or "").strip(),
                url=source.get("ticketUrl", ""),
                source=source["id"],
            )
        )
    return events
