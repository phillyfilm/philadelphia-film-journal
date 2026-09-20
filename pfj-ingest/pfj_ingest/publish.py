"""The run: pull every source, filter, merge, and write events.json.

Nothing publishes blind. Sources marked trust:"auto" go straight
through; sources marked trust:"review" land in data/review.json for you
to approve, because what a WordPress feed calls an Event might be a
private rental, a yoga class, or a concert.

Approving is one command: `pfj approve <id>` moves a listing into
data/approved.json, where it stays approved on every later run.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import scope
from .adapters import get as get_adapter
from .http import FetchError
from .model import Event, Venue
from .validate import check

PHILLY = timezone(timedelta(hours=-4))


def load_venues(path: Path) -> dict[str, Venue]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"]: Venue(**row) for row in payload["venues"]}


def _load_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return set()


def run(config_dir: Path, data_dir: Path, dry_run: bool = False) -> int:
    settings = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
    sources = json.loads((config_dir / "sources.json").read_text(encoding="utf-8"))

    venues_path = data_dir / Path(settings["venuesFile"]).name
    venues = load_venues(venues_path)
    titles = scope.TitleBook(data_dir / "titles.json")

    collected: list[Event] = []
    queued: list[Event] = []
    counts: dict[str, int] = {}
    failures: list[str] = []

    approved = _load_ids(data_dir / "approved.json")

    for source in sources:
        if not source.get("enabled", True):
            continue
        name = source["id"]
        try:
            pull = get_adapter(source["adapter"])
            events = pull(source)
        except (FetchError, KeyError) as exc:
            failures.append(f"{name}: {exc}")
            counts[name] = 0
            continue

        kept: list[Event] = []
        for event in events:
            event.title = titles.canonical(event.title)
            event.type = scope.classify(event)
            keep, _reason = scope.in_scope(event, venues.get(event.venueId))
            if not keep:
                continue
            if source.get("trust") == "review" and event.id not in approved:
                queued.append(event)
                continue
            kept.append(event)

        counts[name] = len(kept)
        collected.extend(kept)

    events = scope.merge_duplicates(collected)
    events.sort(key=lambda e: (e.date, e.title.lower()))

    report = check(counts, data_dir, record=not dry_run)
    for failure in failures:
        report.warnings.append(failure)

    print(report.render())

    if queued:
        (data_dir / "review.json").write_text(
            json.dumps([e.to_dict() for e in queued], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\n{len(queued)} listing(s) waiting in data/review.json")

    if dry_run:
        print("\nDry run: nothing written.")
        return 0 if report.ok else 1

    if not report.ok:
        print("\nRefusing to publish. Last good data left in place.")
        return 1

    payload = {
        "schema": 1,
        "generated": datetime.now(PHILLY).isoformat(timespec="seconds"),
        "events": [e.to_dict() for e in events],
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    for consumer in settings["consumers"]:
        target = (config_dir.parent / consumer["events"]).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        print(f"wrote {target}")

        venue_target = target.parent / "venues.json"
        venue_target.write_text(venues_path.read_text(encoding="utf-8"), encoding="utf-8")

    titles.save()
    return 0
