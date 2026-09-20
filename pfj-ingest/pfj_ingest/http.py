"""Polite HTTP for the ingest job.

Everything the pipeline pulls from the open web goes through fetch().
It identifies the bot, honours robots.txt, caches to disk so a re-run
during development doesn't hit anyone's server twice, and backs off on
failure. Venues are small nonprofits running WordPress on shared
hosting; hammering them is both rude and a good way to get blocked.

file:// URLs work too, which is how the tests feed fixtures through the
same code path as live sources.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path
from typing import Optional

USER_AGENT = (
    "PFJBot/1.0 (+https://github.com/PLACEHOLDER/philadelphia-film-journal; "
    "listings calendar for The Philadelphia Film Journal)"
)

CACHE_DIR = Path(os.environ.get("PFJ_CACHE", ".cache"))
CACHE_TTL = int(os.environ.get("PFJ_CACHE_TTL", 60 * 60 * 6))  # six hours
TIMEOUT = 30

_robots: dict[str, urllib.robotparser.RobotFileParser] = {}


class FetchError(RuntimeError):
    """A source could not be read. Callers treat this as 'skip, keep last good'."""


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.body"


def _robots_allows(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return True
    root = f"{parts.scheme}://{parts.netloc}"
    parser = _robots.get(root)
    if parser is None:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(f"{root}/robots.txt")
        try:
            parser.read()
        except Exception:
            # No robots.txt, or it is unreachable. Absence is permission.
            parser.allow_all = True
        _robots[root] = parser
    try:
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def fetch(
    url: str,
    headers: Optional[dict[str, str]] = None,
    use_cache: bool = True,
    attempts: int = 3,
) -> str:
    """Return the body of url as text, or raise FetchError."""
    if url.startswith("file://") or url.startswith("/"):
        path = url[7:] if url.startswith("file://") else url
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise FetchError(f"{url}: {exc}") from exc

    if not _robots_allows(url):
        raise FetchError(f"{url}: disallowed by robots.txt")

    cached = _cache_path(url)
    if use_cache and cached.exists():
        age = time.time() - cached.stat().st_mtime
        if age < CACHE_TTL:
            return cached.read_text(encoding="utf-8")

    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    request_headers.update(headers or {})

    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
            if use_cache:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cached.write_text(body, encoding="utf-8")
            return body
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (401, 403, 404):
                break          # retrying will not help
            time.sleep(2 ** attempt)
        except Exception as exc:
            last_error = exc
            time.sleep(2 ** attempt)

    # A stale cache entry beats an empty calendar.
    if use_cache and cached.exists():
        return cached.read_text(encoding="utf-8")
    raise FetchError(f"{url}: {last_error}")


def fetch_json(url: str, headers: Optional[dict[str, str]] = None) -> object:
    body = fetch(url, headers=headers)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{url}: response was not JSON ({exc})") from exc
