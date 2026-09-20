# The Philadelphia Film Journal — tools

Three pieces that share one data file:

| Folder | What it is |
| --- | --- |
| `pfj-map/` | A week-at-a-time map of which venues are showing something. One dot per venue, clickable card with up to three listings. |
| `pfj-calendar/` | A month grid. Click a date and get that day's screenings grouped by film title, with venues and times under each title. |
| `pfj-ingest/` | The Python pipeline that pulls listings from venue ticketing systems and writes `events.json` into both front ends. |

Both front ends read `data/venues.json` and `data/events.json` from their
own folder. The pipeline writes both. Nothing else connects them, which
means either front end can be redesigned without touching the pipeline.

## First run

The two web pages need to be served over HTTP — opening `index.html`
straight off the disk fails, because browsers refuse `fetch()` on
`file://`. On GitHub Pages this is automatic. Locally:

```bash
cd pfj-map && python3 -m http.server 8000     # then open localhost:8000
```

The listings currently in `data/events.json` are **sample data**, invented
so the layout can be judged before any venue has issued a credential.
Both pages show a banner saying so. Replace them with the real thing:

```bash
cd pfj-ingest
pip install -r ../requirements.txt
python3 -m pfj_ingest run
```

## The pipeline

```bash
cd pfj-ingest

python3 -m pfj_ingest venues          # rebuild venues.json from the workbook
python3 -m pfj_ingest run             # pull everything enabled, publish
python3 -m pfj_ingest run --dry-run   # same, writing nothing
python3 -m pfj_ingest probe --source ambler   # what does one source return?
python3 -m pfj_ingest review          # listings waiting for approval
python3 -m pfj_ingest approve <id>    # approve one, permanently
python3 -m pfj_ingest geocode         # upgrade approximate coordinates
python3 -m pytest tests -q
```

### Sources

`config/sources.json` lists every source and which adapter reads it.
Everything except `manual` ships with `"enabled": false`, so the pipeline
runs cleanly before any credential exists.

| Adapter | Used by | What you need |
| --- | --- | --- |
| `veezi` | Ambler, County, Hiway | A read-only WebSessions token per site from Renew Theaters |
| `agile` | PFS (three houses), BMFI, Colonial | An organization ID and API key per venue from its box office |
| `tribe` | PhilaMOCA | Nothing — WordPress exposes it. Check the URL in a browser first |
| `ics` | Woodmere, Villanova | The URL behind the site's "subscribe" or "add to calendar" link |
| `jsonld` | Newtown, Lightbox | Nothing, but fragile; always lands in the review queue |
| `manual` | Anything hand-typed | `data/manual.csv` |

Veezi is the one to get working first: one API shape covering three of
the region's best-programmed theaters, which proves the whole pipeline
end to end.

Tokens are read from environment variables named in `sources.json`
(`VEEZI_TOKEN_AMBLER` and so on). In Actions they come from repository
secrets; locally, export them in your shell. They never go in a file.

### What the pipeline refuses to do

Sources marked `"trust": "review"` don't publish straight through. What
a WordPress feed calls an Event may be a private rental or a concert, so
those land in `data/review.json` until you approve them.

It also refuses to publish a run where a source that normally returns
listings suddenly returns none. A venue redesigning its website and the
adapter quietly returning nothing is the real failure mode here, and an
empty Tuesday at the Ambler is worse than no calendar at all. On refusal
the last good `events.json` stays put and the Actions run goes red.

## Time handling

One rule, implemented three times — `pfj_ingest/model.py`, and the
`parseTime`/`formatTime` pair in each `index.html`:

- A bare hour means afternoon or evening. `7:30` is 7:30pm, because
  cinemas do not screen at half past seven in the morning.
- A morning showing must say so: `10:30am`.
- Anything 13 or over is read as a 24-hour clock.
- `Dusk`, `Sunset`, `After the lecture` pass through and sort last.

`tests/test_time.py` is the contract. It can't reach the JavaScript, so
if you change a rule, change all three.

## Scope

`pfj_ingest/venues.py` holds two switches:

- `COUNTIES` — the five southeastern Pennsylvania counties. The v2
  workbook also carries Wilmington, Princeton and Lehigh Valley venues;
  adding `"New Castle"` here takes in Theatre N and the Wilmington
  Penn Cinema, and nothing else needs to change.
- `POLICY` — the resolved judgment calls. Ritz Five is a full yes;
  both Penn Cinemas are `special-only`, meaning their regular showtimes
  drop out and their one-off events stay.

18 of the 25 venues in the workbook currently publish.

## Coordinates

Eight venues have sourced coordinates in the workbook. Eleven are
backfilled from `APPROX_COORDS` in `venues.py`, accurate to about a
block, and flagged `coordPrecision: "approximate"`. Run
`python3 -m pfj_ingest geocode` on a machine with network access to
replace them with US Census Geocoder results, then paste the output back
into `APPROX_COORDS` so a workbook rebuild keeps them.

## Deployment

GitHub Pages serves both front ends from the repository root:

```
https://<username>.github.io/<repo>/pfj-map/
https://<username>.github.io/<repo>/pfj-calendar/
```

`.github/workflows/ingest.yml` runs the pipeline nightly, commits any
changed listings, and lets Pages redeploy. It also runs on demand from
the Actions tab, which is how to test it.
