"""Write sample listings so the calendar and map have something to draw.

Everything this produces is invented. It exists only so you can look at
the two front ends and judge layout and typography before any venue has
issued an API credential. The payload carries "sample": true, which
both front ends read and turn into a banner, so nothing here can be
mistaken for a real screening if it goes up by accident.

Delete the sample data the moment the first real source is enabled:

    python3 -m pfj_ingest run        # overwrites both events.json files

Usage:  python3 tools/make_seed.py [weeks]
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONSUMERS = [
    ROOT.parent / "pfj-calendar" / "data" / "events.json",
    ROOT.parent / "pfj-map" / "data" / "events.json",
]

REPERTORY = [
    ("Paris, Texas", 1984, "Wim Wenders", "35mm"),
    ("Killer of Sheep", 1978, "Charles Burnett", "35mm"),
    ("Daughters of the Dust", 1991, "Julie Dash", ""),
    ("The Third Man", 1949, "Carol Reed", ""),
    ("Chungking Express", 1994, "Wong Kar-wai", ""),
    ("Cléo from 5 to 7", 1962, "Agnès Varda", ""),
    ("Stop Making Sense", 1984, "Jonathan Demme", "4K"),
    ("Sorcerer", 1977, "William Friedkin", "35mm"),
    ("Night of the Living Dead", 1968, "George A. Romero", "16mm"),
    ("In the Mood for Love", 2000, "Wong Kar-wai", ""),
    ("The Battle of Algiers", 1966, "Gillo Pontecorvo", ""),
    ("Losing Ground", 1982, "Kathleen Collins", ""),
]

FIRST_RUN = [
    ("A Quiet Harvest", 2026, "Nia Okonkwo", ""),
    ("The Undercurrent", 2026, "Tomás Reyes", ""),
    ("Winter Light Again", 2026, "Ingrid Solberg", ""),
    ("Fair Weather Friends", 2026, "Marcus Bell", ""),
]

TIMES_EVENING = [["7:30"], ["7:00"], ["6:30"], ["8:00"]]
TIMES_FULL = [["2:00pm", "5:15", "8:00"], ["1:30pm", "4:45", "7:30"], ["4:00", "7:15"]]


def load_venues() -> list[dict]:
    payload = json.loads((DATA / "venues.json").read_text(encoding="utf-8"))
    return [v for v in payload["venues"] if v["inScope"] and v["policy"] == "all"]


def build(weeks: int) -> list[dict]:
    random.seed(1984)                       # stable output across runs
    venues = load_venues()
    start = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=7)
    events: list[dict] = []

    for offset in range(weeks * 7):
        day = start + timedelta(days=offset)
        for venue in venues:
            # Bigger houses run daily; small rooms a couple of nights a week.
            daily = "Cinema" in venue["category"]
            if not daily and random.random() > 0.28:
                continue
            if daily and random.random() > 0.92:
                continue

            catalogue = FIRST_RUN if daily and random.random() < 0.55 else REPERTORY
            title, year, director, fmt = random.choice(catalogue)
            times = random.choice(TIMES_FULL if daily else TIMES_EVENING)

            events.append({
                "id": f"sample-{len(events):04d}",
                "venueId": venue["id"],
                "title": title,
                "year": year,
                "director": director,
                "format": fmt,
                "series": "",
                "type": "special" if fmt else "screening",
                "date": day.isoformat(),
                "times": times,
                "note": "Sample listing — not a real screening",
                "featured": bool(fmt) and random.random() < 0.3,
                "url": venue.get("ticketUrl") or venue.get("website", ""),
                "source": "sample",
            })

    # A couple of community screenings so the toggle has something to do.
    for offset in (5, 12):
        day = start + timedelta(days=offset)
        events.append({
            "id": f"sample-community-{offset}",
            "venueId": venues[0]["id"],
            "title": "Movies on the Block: Clueless",
            "year": 1995, "director": "Amy Heckerling", "format": "",
            "series": "Movies on the Block", "type": "community",
            "date": day.isoformat(), "times": ["Dusk"],
            "note": "Sample listing — not a real screening",
            "featured": False, "url": "", "source": "sample",
        })

    events.sort(key=lambda e: (e["date"], e["title"].lower()))
    return events


def main() -> int:
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    payload = {
        "schema": 1,
        "sample": True,
        "generated": datetime.now(timezone(timedelta(hours=-4))).isoformat(timespec="seconds"),
        "events": build(weeks),
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    venues = (DATA / "venues.json").read_text(encoding="utf-8")

    for target in CONSUMERS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        (target.parent / "venues.json").write_text(venues, encoding="utf-8")
        print(f"wrote {target}")

    print(f"{len(payload['events'])} sample listings across {weeks} weeks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
