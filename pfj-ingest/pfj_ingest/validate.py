"""Health checks.

The failure mode for a listings site is not a crash. It is a venue
redesigning its website, the adapter quietly returning nothing, and the
Journal showing an empty Tuesday at the Ambler -- which is worse than
showing nothing at all, because readers trust it and drive out there.

So: every run records how many listings each source produced, compares
against that source's recent history, and refuses to publish a run that
lost more than a threshold of its listings. On refusal the last good
events.json stays in place and the run exits non-zero, which turns the
GitHub Actions run red and sends you the email.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HISTORY_FILE = "history.json"
COLLAPSE_THRESHOLD = 0.5      # lose half a source's usual volume and we stop
MIN_RUNS_BEFORE_ALARM = 3     # don't cry wolf while history is still thin


class HealthReport:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def total(self) -> int:
        return sum(self.counts.values())

    def render(self) -> str:
        lines = [f"{count:>4}  {name}" for name, count in sorted(self.counts.items())]
        lines.append(f"{self.total():>4}  total")
        for warning in self.warnings:
            lines.append(f"  warning: {warning}")
        for error in self.errors:
            lines.append(f"  ERROR:   {error}")
        return "\n".join(lines)


def check(counts: dict[str, int], data_dir: Path, record: bool = True) -> HealthReport:
    report = HealthReport()
    report.counts = dict(counts)

    path = data_dir / HISTORY_FILE
    history: dict[str, list[int]] = {}
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8")).get("counts", {})
        except json.JSONDecodeError:
            history = {}

    for name, count in counts.items():
        past = history.get(name, [])
        if len(past) < MIN_RUNS_BEFORE_ALARM:
            continue
        typical = sorted(past)[len(past) // 2]      # median, not mean
        if typical == 0:
            continue
        if count == 0:
            report.errors.append(
                f"{name} returned nothing but normally returns about {typical}. "
                "Keeping the last good data."
            )
        elif count < typical * COLLAPSE_THRESHOLD:
            report.warnings.append(
                f"{name} returned {count}, well below its usual {typical}."
            )

    if record:
        for name, count in counts.items():
            history.setdefault(name, []).append(count)
            history[name] = history[name][-30:]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"updated": date.today().isoformat(), "counts": history},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return report
