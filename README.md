# Metro Time Machine — World Transit Network Atlas

An interactive, sonified world map of **201 metro / light-rail / tram systems**. Move the
dial through the years and each city's ridership becomes a voice; zoom in (or pick a city and
"fly to its metro") and its real lines and stations surface in place on the map. Watch — and
hear — March 2020 arrive.

**Live/standalone:** `index.html` is completely self-contained (all geometry, ridership series,
and the world basemap are embedded; the only external request is Google Fonts). Open it in any
modern browser, or drop it on any static host.

## Host it on your site

It's one static file — nothing to build.

- **Any web host / your own site:** upload `index.html` (rename as you like, e.g. `transit.html`)
  anywhere under `zachscheffler.com` and link to it. That's it.
- **GitHub Pages:** push this repo to GitHub → Settings → Pages → deploy from `main` / root.
  `index.html` at the root is served directly; the included `.nojekyll` keeps Pages from
  touching it. Your site then lives at `https://<user>.github.io/<repo>/` (or a custom domain).
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

## Rebuild after editing data

```bash
cd tools && python3 tm_gen.py        # writes ../index.html from data/*
```
`tm_gen.py` expects to run from the repo (it reads `data/`). To add or refresh a city's geometry
from OpenStreetMap, run `tools/fetch_networks_osm.py` on a machine with open internet, drop the
resulting `data/networks/<slug>.json`, and regenerate.

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

Coverage note: of the 201 systems, most now carry full line + station geometry; a few remain
station-only (their line geometry wasn't available from a reachable open source at build time).
Geometry is real, not schematic — nothing was fabricated.

## Credit
Built with Claude (Cowork). Transit data © its respective sources as listed above.
