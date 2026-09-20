"""Turn the venue workbook into venues.json.

The workbook is the source of truth for who exists; this module is the
source of truth for who gets published. Two things happen here that the
spreadsheet can't express:

  * Scope. The resolved rule is the five southeastern Pennsylvania
    counties. The v2 workbook also carries Delaware, New Jersey and
    Lehigh Valley venues marked "Fringe" or sitting in New Castle
    County, so COUNTIES below is the switch that decides how wide the
    Journal casts. Widen it and everything downstream follows.

  * Policy. Judgment-call venues aren't a yes or a no. The Ritz Five is
    a full yes despite being Landmark-owned; the two Penn Cinemas are
    "special events only," which means their regular showtimes are
    dropped and their one-off events kept.

Coordinates: the workbook has sourced lat/long for eight venues. The
rest are backfilled from APPROX_COORDS below and marked
coordPrecision="approximate" so the map can treat them accordingly.
Run `pfj geocode` on a machine with network access to replace them with
Census Geocoder results; that writes back into this file's overrides.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .model import Venue

# The resolved five-county scope. Add "New Castle" to take in Wilmington,
# or "Mercer" for Princeton; nothing else needs to change.
COUNTIES = {"Philadelphia", "Bucks", "Chester", "Delaware", "Montgomery"}

# Judgment calls, resolved. Anything not listed inherits the Include? column.
POLICY: dict[str, str] = {
    "V004": "all",            # Landmark Ritz Five -- arthouse programming, in
    "V018": "special-only",   # Penn Cinema Huntingdon Valley
    "V021": "special-only",   # Penn Cinema Riverfront
}

# Hand-entered stand-ins for venues the workbook has no coordinates for.
# Accurate to roughly a block. Replace via `pfj geocode`.
APPROX_COORDS: dict[str, tuple[float, float]] = {
    "V005": (39.9265, -75.1600),   # Lightbox / Bok Building, 1901 S 9th St
    "V006": (39.9605, -75.1585),   # PhilaMOCA, 531 N 12th St
    "V007": (39.9640, -75.2020),   # Scribe Video Center, 3908 Lancaster Ave
    "V008": (40.0760, -75.2090),   # Woodmere, 9201 Germantown Ave
    "V009": (39.9440, -75.1655),   # VIA, 320 S Broad St
    "V012": (40.3100, -75.1290),   # County Theater, Doylestown
    "V013": (40.0935, -75.1250),   # Hiway Theater, Jenkintown
    "V016": (40.2295, -74.9370),   # Newtown Theatre
    "V017": (40.0085, -75.2610),   # Reel Cinemas Narberth
    "V018": (40.1290, -75.0450),   # Penn Cinema Huntingdon Valley
    "V019": (40.0370, -75.3420),   # Villanova, Connelly Center
}

COLUMNS = {
    "id": "ID",
    "name": "Name",
    "include": "Include?",
    "category": "Category",
    "operator": "Operator / Owner",
    "address": "Street Address",
    "city": "City",
    "state": "State",
    "zip": "ZIP",
    "county": "County",
    "tier": "Region Tier",
    "lat": "Latitude",
    "lon": "Longitude",
    "website": "Website",
    "ticket": "Calendar / Ticketing Source",
    "profile": "Programming Profile",
    "notes": "Notes & Flags",
}


def _clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text in ("-", "—", "None", "TBD") else text


def _shorten(text: str, limit: int = 240) -> str:
    text = _clean(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def load_workbook_rows(path: Path) -> list[dict]:
    from openpyxl import load_workbook

    book = load_workbook(path, read_only=True, data_only=True)
    sheet = book["Venues"]
    rows = [r for r in sheet.iter_rows(values_only=True) if r and r[0]]
    header = list(rows[0])
    index = {name: header.index(name) for name in header if name}

    out = []
    for row in rows[1:]:
        record = {}
        for key, column in COLUMNS.items():
            position = index.get(column)
            record[key] = row[position] if position is not None else None
        out.append(record)
    return out


def build_venues(path: Path, counties: Optional[set[str]] = None) -> list[Venue]:
    counties = counties or COUNTIES
    venues: list[Venue] = []

    for row in load_workbook_rows(path):
        vid = _clean(row["id"])
        if not vid:
            continue

        county = _clean(row["county"])
        include_cell = _clean(row["include"]).lower()

        policy = POLICY.get(vid)
        if policy is None:
            if include_cell.startswith("yes"):
                policy = "all"
            elif include_cell.startswith("judgment"):
                policy = "excluded"   # unresolved calls stay out until decided
            else:
                policy = "excluded"   # "Fringe", "No", blank

        in_scope = county in counties and policy != "excluded"

        lat = row["lat"]
        lon = row["lon"]
        precision = "sourced"
        if lat is None or lon is None:
            fallback = APPROX_COORDS.get(vid)
            if fallback:
                lat, lon = fallback
                precision = "approximate"
            else:
                lat = lon = None
                precision = "missing"

        venues.append(
            Venue(
                id=vid,
                name=_clean(row["name"]),
                category=_clean(row["category"]),
                operator=_clean(row["operator"]),
                address=_clean(row["address"]),
                city=_clean(row["city"]),
                state=_clean(row["state"]),
                zip=_clean(row["zip"]),
                county=county,
                tier=_clean(row["tier"]),
                lat=float(lat) if lat is not None else None,
                lon=float(lon) if lon is not None else None,
                coordPrecision=precision,
                website=_clean(row["website"]).split(" ")[0],
                ticketUrl=_clean(row["ticket"]).split(" ")[0],
                profile=_shorten(row["profile"]),
                policy=policy,
                inScope=in_scope,
                notes=_shorten(row["notes"], 400),
            )
        )

    return venues


def write_venues(venues: list[Venue], destination: Path) -> None:
    payload = {
        "schema": 1,
        "counties": sorted(COUNTIES),
        "venues": [v.to_dict() for v in venues],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
