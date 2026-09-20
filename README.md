# Metro Time Machine — World Transit Network Atlas

An interactive, sonified world map of **201 metro / light-rail / tram systems**. Move the
dial through the years and each city's ridership becomes a voice in an immersive, panned
28‑voice world ensemble; zoom in (or pick a city and "fly to its metro") and its real lines
and stations surface in place on the map. Hover a station for its details — and, when the page
is served from your own domain, a live photo. Watch — and hear — March 2020 arrive.

> **Station photos:** hovering a station fetches a representative image live from the
> Wikimedia Commons / Wikipedia API (with graceful "no photo" fallback for stations it
> doesn't cover). This works when the page is hosted on a normal web server (your site);
> it stays text‑only inside sandboxes that block third‑party image hosts.

**Live:** <https://colonelkernel.github.io/world-transit-atlas/>

**Standalone:** `index.html` is completely self-contained (all geometry, ridership series,
and the world basemap are embedded; the only external request is Google Fonts). Open it in any
modern browser, or drop it on any static host.

## Host it on your site

It's one static file — nothing to build.

- **Any web host / your own site:** upload `index.html` (rename as you like, e.g. `transit.html`)
  anywhere under `zachscheffler.com` and link to it. That's it.
- **GitHub Pages:** already enabled on this repo — `main` / root, served at
  <https://colonelkernel.github.io/world-transit-atlas/>. `index.html` at the root is served
  directly; the included `.nojekyll` keeps Pages from touching it. Pushing to `main`
  redeploys. For a fork: Settings → Pages → deploy from `main` / root.
- **Netlify / Vercel / Cloudflare Pages:** point at the repo, no build command, publish
  directory = root.

## Repo layout

```
index.html              the map — standalone, all data embedded (open this)
tools/tm_gen.py         regenerator: globs data/networks/*.json + data/*.json → rebuilds index.html
tools/fetch_networks_osm.py   pulls/refreshes network geometry from OpenStreetMap (run locally)
transit_atlas.R         R access layer for every dataset (analysis)
data/
  timemachine_data.json   the 201 systems: location, region, mode, ridership series, attributes
  world_rings.json        Natural Earth land outlines (basemap)
  networks/<slug>.json    per-city line + station geometry
  ridership/              what every ridership figure actually counts (see below)
    SCHEMA.md               the canonical schema + the measure_def enum
    system_rank.csv         measure_def, annual_url, confidence per system
    sources.csv             full citation rows: publisher, URL, access, caveats
    ridership_long.csv      tidy panel, per-row measure_def and source_id
    measure_def_overrides.csv  reviewed corrections, each with its evidence
  research/
    covariates.csv          population, density, GDP/cap, motorization, trips/cap
    ridership_verified.csv  the joined, graded dataset (built, not hand-edited)
    comparability.csv       the grade table
    coords.json             lat/lon for all 201
```

## Coverage

All **201 systems carry both line and station geometry** — 1,298 lines and 22,641 stations,
counted from `data/networks/*.json` rather than from memory. (This line said 1,303 until the
count was actually re-run.)

Getting the last 34 cities took two fixes rather than a different network:

- `fetch_lines()` asked Overpass for `out tags geom;`. `tags` is an output *mode* that
  suppresses relation member lists, so the fetcher received no members and wrote zero lines
  for every city it touched, regardless of connectivity. It now asks for `out geom;`.
- The coarse mode map sent `lrt` cities to `route=light_rail` only. German *Stadtbahn*
  networks (Cologne, Düsseldorf, Hanover) and the Tyne & Wear Metro are tagged `tram` or
  `light_rail` inconsistently in OSM, so those queries came back empty. They are fetched
  across several route types now.

To top up coverage later (after an OSM improvement, or for a newly opened line):

```bash
./finish.sh    # refetches any city missing lines or stations, then rebuilds index.html
```

`finish.sh` derives its own gap list from `data/networks/*.json`, so it stays correct as
coverage changes — it does nothing but rebuild once everything is complete.

### A note on the fetch radius
The fetcher sweeps a 45 km radius around each city centre, so in dense conurbations a city
picks up its neighbours' routes: Cologne includes Bonn's 6x and Düsseldorf's 70x lines, and
Düsseldorf spans much of the Rhine-Ruhr. The geometry is real, just drawn from a wider
catchment than the city name implies. Lower `RADIUS_M` in `tools/fetch_networks_osm.py` and
refetch if you want strictly municipal networks.

## Rebuild / refresh manually

```bash
python3 tools/tm_gen.py                          # rebuild index.html from data/*
python3 tools/fetch_networks_osm.py --only berlin,munich   # refetch specific cities from OSM
```
Both tools read/write the repo's `data/` folder; run them from the repo root.

`data/networks/*.json` keeps full-fidelity OSM geometry (899k vertices). Raw OSM ways carry a
vertex every few metres — far finer than the map can draw — so `tm_gen.py` simplifies paths
on the way into the page (Ramer-Douglas-Peucker, ~17 m tolerance, below one screen pixel at
the deepest city zoom). That trims 76% of the vertices and keeps `index.html` at ~6.5 MB
instead of ~20 MB. Adjust `_TOL` in `tools/tm_gen.py` to trade size against precision.

## Data sources & attribution

Please keep this attribution when hosting publicly.

- **Network geometry (lines + stations):** [OpenStreetMap](https://www.openstreetmap.org/copyright)
  contributors (© OpenStreetMap, ODbL) via the Overpass API; [citylines.co](https://www.citylines.co)
  (CC-BY-SA); public agency open-data portals and ArcGIS Hubs (e.g. US National Transit Map / BTS,
  Sound Transit, RTD, DART, TfL-adjacent open data, İBB Istanbul, Buenos Aires Data, DataGrandLyon,
  and others); and a handful of open GitHub datasets (China via `luxueyan/generate-china-subways-geojson`,
  Taipei `leoluyi/taipei_mrt`, Bengaluru `geohacker/namma-metro`, and others).
- **Ridership series:** US National Transit Database (BTS/FTA) monthly rail UPT; municipal open-data
  feeds (e.g. Chicago 'L'); agency reports; China Association of Metros (CAMET) annual statistics.
- **Covariates:** World Bank indicators; national statistics.
- **Basemap:** Natural Earth (public domain).

Coverage note: all 201 systems carry full line + station geometry. Geometry is real, not
schematic — nothing was fabricated. Depot tracks, sidings and disused/heritage alignments are
filtered out, so the lines shown are passenger routes.

## What the ridership numbers count

Agencies do not count the same thing, and a figure means nothing until you know
which thing. `data/ridership/SCHEMA.md` defines the enum and the rule that goes
with it — **we do not silently convert between these**:

| `measure_def` | what it counts | n |
|---|---|---|
| `passenger_journeys` | the operator's headline "journeys" figure | 87 |
| `unlinked_trips` | boardings, including transfers (US NTD "UPT", Chinese 客运量) | 55 |
| `station_entries` | taps/entries at faregates (TfL gateline, Chinese 进站量) | 26 |
| `estimated` | modelled or derived, usually from a daily average | 17 |
| `linked_journeys` | one trip end to end regardless of transfers | 2 |
| *(unknown)* | the value matches no source we could locate | 9 |

A transfer-heavy network reports roughly 1.2–1.6x more under boardings than
under journeys for identical travel, so mixing these silently is not noise —
it is slope.

```bash
python3 tools/comparability.py --write   # grade all four comparability axes, rebuild the dataset
python3 tools/verify_camet.py            # re-derive the Chinese conventions from CAMET 表3
python3 tools/ridership_model.py         # the model, and what did not survive it
```

`verify_camet.py` is worth reading even if you do not run it. CAMET publishes
客运量 and 进站量 side by side, and for every single-line city the two columns
are bit-identical — no transfers, so a boarding and a station entry are the
same event. Where there is more than one line the gap between them *is* the
transfer volume, nationally 1.666x. That identity is what proves 客运量 is
boardings, and it is why 26 Chinese systems were relabelled.

**Four axes, not one.** The counting convention is only the first. The
denominator basis (built-up urban area vs metro region vs city proper) and the
vintage (these figures run 2013–2026, straddling COVID) are graded too. The
fourth — what *modes* the numerator covers, metro only vs metro+tram vs a whole
multimodal agency including bus — is recorded nowhere, and is the likeliest
explanation for the extreme values in the table.

## Credit
Built with Claude (Cowork). Transit data © its respective sources as listed above.
