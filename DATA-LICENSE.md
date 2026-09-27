# Data licensing

**Short version: the data in this repository is not under one licence, and 162
of the 201 networks have no established licence at all. Do not redistribute
`data/` or `index.html` as a dataset until you have resolved that. The code is
MIT; see LICENSE.**

This file exists because `tools/provenance.py` made the question answerable.
Before it, the README named the sources in prose -- OpenStreetMap, citylines.co,
agency portals, some GitHub datasets -- with no way to tell which city came from
which. Share-alike obligations cannot be honoured for a record whose origin is
unknown, so a single repository-wide data licence would have been a guess.

## Network geometry — `data/networks/*.json`

`data/networks/provenance.csv` carries one row per system.

| basis | n | source | licence |
|---|---|---|---|
| `fetch_commit` | 39 | OpenStreetMap via Overpass | **ODbL-1.0** |
| `initial_import` | 162 | unknown (mixed) | **unknown** |

The 39 are the cities refetched in commits `ee05c18` (the Swiss three via
osm.ch) and `c0cc9ef` (the 34 gap cities). Their source, method, radius and
retrieval date are recorded, and they are ODbL: **© OpenStreetMap
contributors**, share-alike, attribution required.

The 162 arrived in the initial import as one undifferentiated drop. Two
independent lines of evidence say they are not simply this repo's own OSM
output:

- the introducing commit records no source for them, and
- the fetcher fills a station's `routes` from OSM's sparsely-tagged `route_ref`
  and so produces route strings on ~2% of stations, while the initial import
  carries them on ~69%. Whatever built that corpus had line-station relations
  this fetcher does not obtain.

That is consistent with the README's stated citylines.co (CC-BY-SA) and agency
mix. It is not proof of any particular source for any particular city, which is
exactly the point: **the honest record is `unknown`, and `unknown` blocks
redistribution.**

### Resolving it

Refetching a city from OpenStreetMap moves it to `fetch_commit`/ODbL with the
parameters recorded automatically:

```bash
python3 tools/fetch_networks_osm.py --only <slug>
python3 tools/provenance.py --write
```

Running that over all 201 would put the whole geometry corpus under a single
known licence. Until then, treat `data/networks/` as unredistributable.

## Ridership figures — `data/ridership/`, `data/research/`

Individual figures are facts reported by their publishers, cited per system in
`data/ridership/sources.csv` and `system_rank.annual_url`. Facts are generally
not copyrightable, but the compilations they come from may be, and terms vary by
publisher (US NTD is public domain; CAMET, TfL, municipal portals and agency
annual reports are not uniform). Cite the publisher, not this repository.

## Basemap — `data/world_rings.json`

Natural Earth, public domain.

## The generated page — `index.html`

`index.html` embeds all of the above. Its licence is therefore the intersection
of theirs, which today includes `unknown`. Hosting the page as published here is
what it was built for; redistributing it as a data product is not yet
licensable.
