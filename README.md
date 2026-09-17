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
  data/research/*         coords + covariates (inputs for the fetch/regenerate tools)
```

## Coverage

All **201 systems carry both line and station geometry** — 1,303 lines and 22,641 stations.

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
  feeds (e.g. Chicago 'L'); agency reports.
- **Covariates:** World Bank indicators; national statistics.
- **Basemap:** Natural Earth (public domain).

Coverage note: all 201 systems carry full line + station geometry. Geometry is real, not
schematic — nothing was fabricated. Depot tracks, sidings and disused/heritage alignments are
filtered out, so the lines shown are passenger routes.

## Credit
Built with Claude (Cowork). Transit data © its respective sources as listed above.
