"""Scope rules and title canonicalization.

Scope is the thing that makes the Journal the Journal: it is a listing
of what the region's independent, repertory and institutional venues
are showing, not a showtimes aggregator. The rules can't be fully
computed, which is why anything uncertain lands in the review queue
rather than being silently dropped.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Iterable

from .model import Event, Venue

# Regular programming at these venues is out; a one-off event is in.
SPECIAL_MARKERS = re.compile(
    r"\b(q\s*&\s*a|qanda|introduc|presented by|premiere|benefit|fundrais|"
    r"anniversar|restor|35mm|16mm|70mm|sing-?along|double feature|marathon|"
    r"festival|retrospectiv|in person|live score|panel|lecture|discussion)\b",
    re.IGNORECASE,
)

COMMUNITY_MARKERS = re.compile(
    r"\b(movies? in the park|movie night|outdoor|lawn|pop-?up|under the stars|"
    r"family film night|movies on the block)\b",
    re.IGNORECASE,
)


def classify(event: Event) -> str:
    """Tag an event so the front ends can filter it."""
    haystack = " ".join(filter(None, [event.title, event.series, event.note]))
    if COMMUNITY_MARKERS.search(haystack):
        return "community"
    if event.format or SPECIAL_MARKERS.search(haystack):
        return "special"
    return event.type or "screening"


def in_scope(event: Event, venue: Venue | None) -> tuple[bool, str]:
    """Decide whether an event publishes. Returns (keep, reason)."""
    if venue is None:
        return False, "unknown venue"
    if not venue.inScope:
        return False, f"{venue.name} is outside the published scope"
    if venue.policy == "excluded":
        return False, f"{venue.name} is excluded by policy"
    if venue.policy == "special-only" and classify(event) not in ("special", "community"):
        return False, f"{venue.name} publishes special events only"
    return True, ""


class TitleBook:
    """Maps the many spellings of a film to one canonical title.

    This is where projects like this usually go wrong. The Ambler will
    call it "PARIS, TEXAS (1984)", the County "Paris Texas - 40th
    Anniversary", and a WordPress feed "Paris, Texas [35mm]". Three
    rows where there should be one title with three venues under it.
    """

    NOISE = re.compile(
        r"\s*[\(\[]\s*(19|20)\d{2}\s*[\)\]]|"
        r"\s*[-–—:]\s*\d+(st|nd|rd|th)\s+anniversary|"
        r"\s*[\(\[]\s*(35mm|16mm|70mm|dcp|digital|4k|restoration|remastered)[^)\]]*[\)\]]|"
        r"\s*[-–—]\s*(35mm|16mm|70mm|4k restoration)\s*$",
        re.IGNORECASE,
    )

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        if path and path.exists():
            self.aliases = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def key(title: str) -> str:
        text = TitleBook.NOISE.sub("", title or "")
        text = re.sub(r"[^\w\s]", " ", text.lower())
        text = re.sub(r"\s+", " ", text).strip()
        if text.startswith(("the ", "a ", "an ")):
            text = text.split(" ", 1)[1]
        return text

    def canonical(self, title: str) -> str:
        cleaned = self.NOISE.sub("", title or "").strip(" -–—:")
        key = self.key(cleaned)
        if key in self.aliases:
            return self.aliases[key]

        near = difflib.get_close_matches(key, self.aliases.keys(), n=1, cutoff=0.92)
        if near:
            return self.aliases[near[0]]

        return cleaned or (title or "").strip()

    def learn(self, key: str, canonical_title: str) -> None:
        self.aliases[key] = canonical_title

    def save(self) -> None:
        if not self.path:
            return
        self.path.write_text(
            json.dumps(self.aliases, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def merge_duplicates(events: Iterable[Event]) -> list[Event]:
    """One venue showing the same film twice on one day is one listing."""
    merged: dict[tuple[str, str, str], Event] = {}
    for event in events:
        key = (event.venueId, event.date, TitleBook.key(event.title))
        existing = merged.get(key)
        if existing is None:
            merged[key] = event
            continue
        from .model import sort_times

        existing.times = sort_times(list(dict.fromkeys(existing.times + event.times)))
        existing.featured = existing.featured or event.featured
        existing.note = existing.note or event.note
        existing.format = existing.format or event.format
        existing.url = existing.url or event.url
    return list(merged.values())
