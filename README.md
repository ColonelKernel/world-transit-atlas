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

## Finish the last cities (one command, your own terminal)
34 cities still draw as stations only — mostly the German set (Berlin, Munich, Hamburg,
Cologne, Frankfurt…) plus Seoul, Athens, Copenhagen and a few more. Their line geometry lives
only in OpenStreetMap, which **neither the cloud session nor the linked‑desktop sandbox can
reach** (both share the same egress allow‑list). Your own terminal has open internet, so:

```bash
cd world-transit-atlas
./finish.sh            # pulls the remaining lines from OSM, rebuilds index.html (~2 min)
```

Reopen `index.html` and those cities draw their lines. (Send me the refreshed
`data/networks/*.json` — or the rebuilt `index.html` — and I'll republish the hosted copy too.)

## Rebuild / refresh manually

```bash
python3 tools/tm_gen.py                          # rebuild index.html from data/*
python3 tools/fetch_networks_osm.py --only berlin,munich   # refetch specific cities from OSM
```
`finish.sh` just calls the fetcher with the current gap list. Both tools read/write the repo's
`data/` folder; run them from the repo root.

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
