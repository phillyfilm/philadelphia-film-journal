import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pfj_ingest.model import Event, Venue
from pfj_ingest.scope import TitleBook, classify, in_scope, merge_duplicates


def venue(**kw):
    base = dict(id="V011", name="Ambler Theater", county="Montgomery",
                policy="all", inScope=True)
    base.update(kw)
    return Venue(**base)


def event(**kw):
    base = dict(venueId="V011", title="Paris, Texas", date="2026-09-21", times=["7:30"])
    base.update(kw)
    return Event(**base)


def test_out_of_county_venues_do_not_publish():
    keep, reason = in_scope(event(), venue(inScope=False, county="New Castle"))
    assert not keep and "scope" in reason


def test_special_only_venues_drop_regular_showtimes():
    penn = venue(id="V018", name="Penn Cinema", policy="special-only")
    keep, _ = in_scope(event(venueId="V018", title="Wicked: For Good"), penn)
    assert not keep

    keep, _ = in_scope(
        event(venueId="V018", title="The Shining", note="35mm, with a Q&A"), penn
    )
    assert keep


def test_community_screenings_are_tagged_not_dropped():
    assert classify(event(title="Movies on the Block: Clueless")) == "community"


def test_format_marks_a_special():
    assert classify(event(format="35mm")) == "special"


def test_title_canonicalization_collapses_venue_spellings():
    book = TitleBook()
    forms = [
        "PARIS, TEXAS (1984)",
        "Paris, Texas [35mm]",
        "Paris, Texas - 40th Anniversary",
        "Paris, Texas",
    ]
    assert len({TitleBook.key(f) for f in forms}) == 1
    assert book.canonical("PARIS, TEXAS (1984)").lower().startswith("paris")


def test_leading_articles_do_not_split_a_title():
    assert TitleBook.key("The Shining") == TitleBook.key("Shining, The".replace(", The", ""))


def test_two_showings_become_one_listing():
    merged = merge_duplicates([
        event(times=["2:00pm"]),
        event(times=["7:30"]),
    ])
    assert len(merged) == 1
    assert merged[0].times == ["2:00pm", "7:30pm"]
