"""Command line for the pipeline.

    pfj venues            rebuild venues.json from the workbook
    pfj run               pull every enabled source and publish
    pfj run --dry-run     same, but write nothing
    pfj probe --source X  fetch one source and print what came back
    pfj review            list what's waiting for approval
    pfj approve <id>      approve a queued listing, permanently
    pfj geocode           upgrade approximate coordinates (needs network)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"


def cmd_venues(args: argparse.Namespace) -> int:
    from .venues import build_venues, write_venues

    workbook = Path(args.workbook) if args.workbook else DATA / "PFJ_Venue_Database_v2.xlsx"
    if not workbook.exists():
        print(f"No workbook at {workbook}", file=sys.stderr)
        return 1

    venues = build_venues(workbook)
    write_venues(venues, DATA / "venues.json")

    published = [v for v in venues if v.inScope]
    approximate = [v for v in published if v.coordPrecision == "approximate"]
    missing = [v for v in published if v.coordPrecision == "missing"]

    print(f"{len(venues)} venues in the workbook, {len(published)} in scope")
    if approximate:
        print(f"{len(approximate)} with approximate coordinates: "
              + ", ".join(v.id for v in approximate))
    if missing:
        print(f"{len(missing)} with no coordinates at all: "
              + ", ".join(v.id for v in missing))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .publish import run

    return run(CONFIG, DATA, dry_run=args.dry_run)


def cmd_probe(args: argparse.Namespace) -> int:
    from .adapters import get as get_adapter

    sources = json.loads((CONFIG / "sources.json").read_text(encoding="utf-8"))
    match = next((s for s in sources if s["id"] == args.source), None)
    if match is None:
        print(f"No source called '{args.source}'. Known: "
              + ", ".join(s["id"] for s in sources), file=sys.stderr)
        return 1

    events = get_adapter(match["adapter"])(match)
    print(f"{len(events)} listing(s) from {args.source}\n")
    for event in events[:15]:
        times = ", ".join(event.times) or "no time given"
        print(f"  {event.date}  {event.title}  [{times}]")
    if len(events) > 15:
        print(f"  ... and {len(events) - 15} more")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    path = DATA / "review.json"
    if not path.exists():
        print("Nothing waiting.")
        return 0
    for event in json.loads(path.read_text(encoding="utf-8")):
        times = ", ".join(event["times"]) or "no time given"
        print(f"{event['id']}  {event['date']}  {event['venueId']}  "
              f"{event['title']}  [{times}]")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    path = DATA / "approved.json"
    approved = set(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else set()
    approved.update(args.ids)
    path.write_text(json.dumps(sorted(approved), indent=2) + "\n", encoding="utf-8")
    print(f"{len(args.ids)} approved; {len(approved)} total.")
    return 0


def cmd_geocode(args: argparse.Namespace) -> int:
    """Replace approximate coordinates with Census Geocoder results."""
    import urllib.parse

    from .http import fetch_json

    path = DATA / "venues.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = 0

    for venue in payload["venues"]:
        if venue["coordPrecision"] == "sourced" or not venue.get("address"):
            continue
        query = urllib.parse.urlencode({
            "street": venue["address"].split("(")[0].strip(),
            "city": venue["city"],
            "state": venue["state"],
            "benchmark": "Public_AR_Current",
            "format": "json",
        })
        url = ("https://geocoding.geo.census.gov/geocoder/locations/address?" + query)
        try:
            result = fetch_json(url)
            matches = result["result"]["addressMatches"]
            if not matches:
                print(f"  {venue['id']}: no match")
                continue
            coords = matches[0]["coordinates"]
            venue["lat"] = round(coords["y"], 6)
            venue["lon"] = round(coords["x"], 6)
            venue["coordPrecision"] = "geocoded"
            changed += 1
            print(f"  {venue['id']}: {venue['lat']}, {venue['lon']}")
        except Exception as exc:
            print(f"  {venue['id']}: {exc}")

    if changed:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"{changed} coordinate(s) upgraded. Copy the results into "
          "pfj_ingest/venues.py APPROX_COORDS so a rebuild keeps them.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pfj", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("venues", help="rebuild venues.json from the workbook")
    p.add_argument("--workbook")
    p.set_defaults(func=cmd_venues)

    p = sub.add_parser("run", help="pull every enabled source and publish")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("probe", help="fetch one source and show what came back")
    p.add_argument("--source", required=True)
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("review", help="list listings waiting for approval")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("approve", help="approve queued listings by id")
    p.add_argument("ids", nargs="+")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("geocode", help="upgrade approximate coordinates")
    p.set_defaults(func=cmd_geocode)

    args = parser.parse_args(argv)
    return args.func(args)
