"""Adapter tests run against fixtures through the real fetch() path."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pfj_ingest.adapters import ics, jsonld, manual

FIXTURES = Path(__file__).parent / "fixtures"


def test_manual_csv_expands_a_date_range():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
        f.write("venueId,title,date,times,format\n")
        f.write("V011,Paris Texas,2026-09-21..2026-09-23,2:00pm;7:30,35mm\n")
        path = f.name

    events = manual.pull({"id": "manual", "path": path})
    assert len(events) == 3
    assert [e.date for e in events] == ["2026-09-21", "2026-09-22", "2026-09-23"]
    assert events[0].times == ["2:00pm", "7:30pm"]


def test_ics_feed_converts_utc_to_local():
    feed = FIXTURES / "woodmere.ics"
    events = ics.pull({"id": "woodmere", "venueId": "V008", "url": f"file://{feed}"})
    assert len(events) == 2
    assert events[0].title == "Tuesday Nights at the Movies: The Third Man"
    # 23:00Z on the 22nd is 7pm on the 22nd in Philadelphia.
    assert events[0].date == "2026-09-22"
    assert events[0].times == ["7:00pm"]


def test_jsonld_finds_nested_events():
    page = FIXTURES / "newtown.html"
    events = jsonld.pull({"id": "newtown", "venueId": "V016", "url": f"file://{page}"})
    titles = sorted(e.title for e in events)
    assert titles == ["Rear Window", "Silent Film Night"]
