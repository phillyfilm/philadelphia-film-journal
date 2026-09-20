"""The time rules, as executable documentation.

The calendar and the map reimplement these in JavaScript. If a case
here changes, change formatTime/parseTime in both index.html files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pfj_ingest.model import format_time, parse_time, sort_times, time_from_iso


def test_bare_hour_means_evening():
    # The whole point: cinemas don't screen at 7:30 in the morning.
    assert format_time("7:30") == "7:30pm"
    assert format_time("9:15") == "9:15pm"
    assert format_time("6") == "6:00pm"


def test_morning_must_be_explicit():
    assert format_time("10:30am") == "10:30am"
    assert format_time("11 AM") == "11:00am"
    assert format_time("10:30") == "10:30pm"


def test_twenty_four_hour_clock():
    assert format_time("19:30") == "7:30pm"
    assert format_time("13:00") == "1:00pm"
    assert format_time("23:59") == "11:59pm"


def test_noon_and_midnight():
    assert format_time("12") == "12:00pm"
    assert format_time("12:00pm") == "12:00pm"
    assert format_time("12:15am") == "12:15am"
    assert format_time("0:15") == "12:15am"


def test_punctuated_meridiem():
    assert format_time("7:30 p.m.") == "7:30pm"
    assert format_time("7:30P.M.") == "7:30pm"


def test_non_clock_values_pass_through():
    assert parse_time("Dusk") is None
    assert format_time("Dusk") == "Dusk"
    assert format_time("After the lecture") == "After the lecture"


def test_sorting_puts_labels_last():
    assert sort_times(["9:15", "Dusk", "2:00pm", "7:30"]) == [
        "2:00pm", "7:30pm", "9:15pm", "Dusk",
    ]


def test_iso_timestamps_are_unambiguous():
    # Machine sources always know; the pipeline writes the meridiem so
    # hand-typed rows stay the only ambiguous input in the system.
    assert time_from_iso("2026-09-21T19:30:00") == "7:30pm"
    assert time_from_iso("2026-09-21T10:30:00") == "10:30am"
    assert time_from_iso("2026-09-21T00:15:00") == "12:15am"


def test_nonsense_is_left_alone():
    assert format_time("25:00") == "25:00"
    assert format_time("7:75") == "7:75"
    assert format_time("") == ""
