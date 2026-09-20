"""Hand-entered listings.

Everything you type in from an Instagram post, a mailing list, or a
phone call lives in data/manual.csv. It is always trusted -- a person
wrote it -- and it is the only place where ambiguous times can enter
the pipeline, which is why model.parse_time defaults a bare hour to the
evening.

Columns: venueId,title,year,director,format,series,type,date,times,
note,featured,url

`times` is semicolon-separated: "2:00pm;7:30".
`date` may be a single date or a start/end range with "..": 2026-09-21..2026-09-24
"""

from __future__ import annotations

import csv
from datetime import date as Date, timedelta
from pathlib import Path

from ..model import Event


def _dates(cell: str) -> list[str]:
    cell = (cell or "").strip()
    if not cell:
        return []
    if ".." not in cell:
        return [cell]
    start_text, end_text = [part.strip() for part in cell.split("..", 1)]
    start = Date.fromisoformat(start_text)
    end = Date.fromisoformat(end_text)
    out, cursor = [], start
    while cursor <= end:
        out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def pull(source: dict) -> list[Event]:
    path = Path(source["path"])
    if not path.exists():
        return []

    events: list[Event] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not (row.get("venueId") and row.get("title")):
                continue
            times = [t.strip() for t in (row.get("times") or "").split(";") if t.strip()]
            year = (row.get("year") or "").strip()
            for day in _dates(row.get("date") or row.get("start") or ""):
                events.append(
                    Event(
                        venueId=row["venueId"].strip(),
                        title=row["title"].strip(),
                        date=day,
                        times=times,
                        year=int(year) if year.isdigit() else None,
                        director=(row.get("director") or "").strip(),
                        format=(row.get("format") or "").strip(),
                        series=(row.get("series") or "").strip(),
                        type=(row.get("type") or "screening").strip(),
                        note=(row.get("note") or "").strip(),
                        featured=(row.get("featured") or "").strip().lower()
                        in ("yes", "true", "1", "y"),
                        url=(row.get("url") or "").strip(),
                        source="manual",
                    )
                )
    return events
