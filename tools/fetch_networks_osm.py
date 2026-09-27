#!/usr/bin/env python3
# =============================================================================
# fetch_networks_osm.py  —  grow the Metro Time Machine's network coverage
# -----------------------------------------------------------------------------
# Pulls real metro / light-rail / tram LINE + STATION geometry from OpenStreetMap
# (via the Overpass API) for every Atlas system, and writes networks/<slug>.json
# in the exact schema the map and transit_atlas.R already read:
#
#   {"slug","city",
#    "stations":[{"name","lon","lat","routes"}],
#    "lines":[{"route","color","paths":[[[lon,lat],...], ...]}]}
#
# WHY THIS SCRIPT EXISTS: the environment the Atlas was built in can't reach
# Overpass (robots.txt / proxy blocks). Your own machine or a Colab notebook can.
# Run it there; drop the resulting files into the `networks/` folder; the map
# (any <slug>.json is picked up automatically) and the R loader both just work.
#
#   pip install requests            # optional; falls back to urllib
#   python3 fetch_networks_osm.py                 # fills only systems w/o a file
#   python3 fetch_networks_osm.py --only paris,berlin,osaka
#   python3 fetch_networks_osm.py --all           # refetch everything
#   TRANSIT_DATA_DIR="/path/to/Transit Network Maps" python3 fetch_networks_osm.py
#
# Inputs (under TRANSIT_DATA_DIR, default "."): research/coords.json (slug,lat,lon)
# and research/covariates.csv (slug,city,mode). Output: <DATA_DIR>/networks/.
# =============================================================================
import json, csv, os, sys, time, math, re, urllib.request, urllib.parse, urllib.error

DATA_DIR = os.environ.get("TRANSIT_DATA_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT_DIR  = os.path.join(DATA_DIR, "networks")
RADIUS_M = 45000          # search radius around each city centre (metres)
SLEEP_S  = 4              # politeness pause between cities
ENDPOINTS = [             # rotated on failure; all are public Overpass mirrors
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]
UA = "WorldTransitAtlas/1.0 (personal research; +https://github.com/ColonelKernel/world-transit-atlas)"

# our mode string -> OSM route relation types + station selectors
MODE_ROUTES = {
    "metro":      ["subway"],
    "lrt":        ["light_rail"],
    "tram":       ["tram"],
    "metro+tram": ["subway", "tram"],
    "metro+lrt":  ["subway", "light_rail"],
}
# OSM's `colour` tag permits CSS colour keywords as well as hex. Canvas renders
# both, but a mixed schema means every consumer has to handle two formats, so
# the keywords are canonicalised here. CSS `green` is #008000, not #00FF00.
NAMED_COLOURS = {
    "red": "#FF0000", "blue": "#0000FF", "green": "#008000", "black": "#000000",
    "white": "#FFFFFF", "yellow": "#FFFF00", "orange": "#FFA500", "purple": "#800080",
    "brown": "#A52A2A", "grey": "#808080", "gray": "#808080", "pink": "#FFC0CB",
    "cyan": "#00FFFF", "aqua": "#00FFFF", "magenta": "#FF00FF", "fuchsia": "#FF00FF",
    "silver": "#C0C0C0", "maroon": "#800000", "navy": "#000080", "olive": "#808000",
    "teal": "#008080", "lime": "#00FF00",
}

PALETTE = ["#e6194b","#3cb44b","#4363d8","#f58231","#911eb4","#46f0f0","#f032e6",
           "#bcf60c","#fabebe","#008080","#e6beff","#9a6324","#800000","#808000",
           "#000075","#a9a9a9","#ffe119","#00a1de","#ff6319","#6cbe45"]

# ---- HTTP ------------------------------------------------------------------
def overpass(query, tries=8):
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for i in range(tries):
        ep = ENDPOINTS[i % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(ep, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            wait = 5 * (i + 1)
            sys.stderr.write(f"    overpass {ep.split('/')[2]} failed ({e}); retry in {wait}s\n")
            time.sleep(wait)
    raise RuntimeError(f"all Overpass endpoints failed: {last}")

# ---- fetch one city --------------------------------------------------------
# depot tracks, sidings and disused/heritage alignments are not passenger lines
SKIP_REF = re.compile(r"former|disused|abandoned|proposed|planned|under construction|siding|depot|not in use", re.I)

def fetch_lines(lat, lon, route_types, want_stops=False):
    """-> lines, or (lines, stops_by_route) when want_stops.

    A route relation lists its stops as node members with role stop/platform and
    carries their coordinates under `out geom`. Reading them is what lets a
    station know which lines call there: the alternative, OSM's `route_ref` tag
    on the station node, is populated on roughly 2% of stations, so a fetch that
    relies on it strips the hover card bare.
    """
    rt = "|".join(route_types)
    q = (f'[out:json][timeout:180];'
         f'relation["route"~"^({rt})$"](around:{RADIUS_M},{lat},{lon});'
         f'out geom;')
    els = overpass(q).get("elements", [])
    lines, ci = [], 0
    stops_by_route = {}
    for rel in els:
        if rel.get("type") != "relation":
            continue
        tags = rel.get("tags", {})
        ref = tags.get("ref") or tags.get("name") or f"L{len(lines)+1}"
        if SKIP_REF.search(str(ref)) or tags.get("disused") or tags.get("proposed"):
            continue
        color = tags.get("colour") or tags.get("color")
        if color and color.strip().lower() in NAMED_COLOURS:
            color = NAMED_COLOURS[color.strip().lower()]
        if color and not color.startswith("#") and len(color) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in color):
            color = "#" + color
        if not color:
            color = PALETTE[ci % len(PALETTE)]; ci += 1
        paths = []
        for m in rel.get("members", []):
            if m.get("type") == "way" and m.get("geometry"):
                pts = [[round(p["lon"], 5), round(p["lat"], 5)] for p in m["geometry"]]
                if len(pts) >= 2:
                    paths.append(pts)
            elif m.get("type") == "node" and m.get("role", "") in ("stop", "platform",
                                                                   "stop_entry_only",
                                                                   "stop_exit_only") \
                    and "lat" in m and "lon" in m:
                stops_by_route.setdefault(str(ref), []).append((m["lon"], m["lat"]))
        if paths:
            lines.append({"route": str(ref), "color": color, "paths": paths})
    # merge lines that share ref (branches) into one entry
    merged = {}
    for ln in lines:
        k = ln["route"]
        if k in merged:
            merged[k]["paths"].extend(ln["paths"])
        else:
            merged[k] = ln
    if want_stops:
        return list(merged.values()), stops_by_route
    return list(merged.values())


# A station node and the route's stop node are the same platform recorded twice
# and sit tens of metres apart; adjacent metro stations are several hundred
# apart. 200 m separates those two cases.
STOP_MATCH_M = 200


def assign_routes(stations, stops_by_route):
    """Fill each station's `routes` from route-relation membership.

    Only ever adds: a route string already present from route_ref is kept and
    merged with what membership proves, so a refetch cannot lose metadata the
    previous source had.
    """
    if not stations or not stops_by_route:
        return stations
    found = {i: set() for i in range(len(stations))}
    for route, stops in stops_by_route.items():
        for slon, slat in stops:
            k = 111320.0 * math.cos(math.radians(slat))
            best, bi = STOP_MATCH_M, None
            for i, st in enumerate(stations):
                d = math.hypot((st["lon"] - slon) * k, (st["lat"] - slat) * 111320.0)
                if d < best:
                    best, bi = d, i
            if bi is not None:
                found[bi].add(route)
    for i, st in enumerate(stations):
        existing = {r.strip() for r in str(st.get("routes") or "").replace(",", ";").split(";") if r.strip()}
        merged_routes = existing | found[i]
        if merged_routes:
            st["routes"] = ";".join(sorted(merged_routes))
    return stations

def fetch_stations(lat, lon, route_types):
    sel = []
    for t in route_types:
        if t == "tram":
            sel.append('node["railway"="tram_stop"](around:%d,%s,%s);' % (RADIUS_M, lat, lon))
        else:
            sel.append('node["railway"="station"]["station"="%s"](around:%d,%s,%s);' % (t, RADIUS_M, lat, lon))
            sel.append('node["railway"="station"]["%s"="yes"](around:%d,%s,%s);' % (t, RADIUS_M, lat, lon))
    q = f'[out:json][timeout:180];({"".join(sel)});out;'
    els = overpass(q).get("elements", [])
    seen, stations = set(), []
    for n in els:
        if "lat" not in n or "lon" not in n:
            continue
        tags = n.get("tags", {})
        name = tags.get("name") or tags.get("name:en") or ""
        key = (name, round(n["lat"], 3), round(n["lon"], 3))   # dedupe interchange copies
        if key in seen:
            continue
        seen.add(key)
        routes = tags.get("route_ref") or tags.get("line") or ""
        stations.append({"name": name, "lon": round(n["lon"], 5),
                         "lat": round(n["lat"], 5), "routes": routes})
    return stations

# ---- provenance -------------------------------------------------------------
# data/networks/provenance.csv is the geometry counterpart to the ridership
# provenance tables. Writing the row here, at fetch time, is what stops the
# record drifting from the data: a city refetched tomorrow carries tomorrow's
# source, licence and parameters without anyone remembering to update a table.
PROV = os.path.join(DATA_DIR, "networks", "provenance.csv")
PROV_FIELDS = ["slug", "city", "source", "license", "attribution", "method",
               "retrieved", "commit", "basis", "n_stations", "n_lines",
               "frac_stations_with_routes"]


def record_provenance(slug, city, stations, lines, route_types):
    import csv as _csv, datetime as _dt
    rows, seen = [], False
    if os.path.exists(PROV):
        with open(PROV, newline="", encoding="utf-8") as fh:
            rows = list(_csv.DictReader(fh))
    with_routes = sum(1 for s in stations if s.get("routes"))
    row = {
        "slug": slug,
        "city": city,
        "source": "OpenStreetMap (Overpass API)",
        "license": "ODbL-1.0",
        "attribution": "(c) OpenStreetMap contributors",
        "method": f"tools/fetch_networks_osm.py, out geom, {RADIUS_M//1000} km radius, "
                  f"route={'/'.join(route_types)}",
        "retrieved": _dt.date.today().isoformat(),
        "commit": "",                 # filled by tools/provenance.py once committed
        "basis": "fetch_run",
        "n_stations": len(stations),
        "n_lines": len(lines),
        "frac_stations_with_routes": round(with_routes / len(stations), 3) if stations else "",
    }
    for i, r in enumerate(rows):
        if r.get("slug") == slug:
            rows[i] = row; seen = True; break
    if not seen:
        rows.append(row)
    rows.sort(key=lambda r: r.get("slug", ""))
    with open(PROV, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=PROV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in PROV_FIELDS})


# ---- driver ----------------------------------------------------------------
def load_systems():
    coords = {c["slug"]: c for c in json.load(open(os.path.join(DATA_DIR, "research", "coords.json")))}
    modes, cities = {}, {}
    with open(os.path.join(DATA_DIR, "research", "covariates.csv")) as f:
        for r in csv.DictReader(f):
            modes[r["slug"]] = r.get("mode", "metro"); cities[r["slug"]] = r.get("city", r["slug"])
    out = []
    for slug, c in coords.items():
        out.append({"slug": slug, "city": cities.get(slug, slug),
                    "lat": c["lat"], "lon": c["lon"], "mode": modes.get(slug, "metro")})
    return out

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    only = None; do_all = "--all" in sys.argv
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    systems = load_systems()
    todo = []
    for s in systems:
        if only and s["slug"] not in only: continue
        path = os.path.join(OUT_DIR, s["slug"] + ".json")
        if os.path.exists(path) and not do_all and not only:
            continue     # gap-fill mode: keep what's already there
        todo.append(s)
    print(f"{len(todo)} systems to fetch (of {len(systems)}); radius {RADIUS_M/1000:.0f} km\n")
    ok = fail = 0
    for i, s in enumerate(todo, 1):
        rts = MODE_ROUTES.get(s["mode"], ["subway", "light_rail"])
        print(f"[{i}/{len(todo)}] {s['slug']:22} ({s['city']}, {'/'.join(rts)}) ...", flush=True)
        try:
            # A busy Overpass mirror answers one of the two queries and returns
            # an empty element list for the other, which looks like a city with
            # no lines (or no stations) rather than like a failure. Observed on
            # consecutive Munich runs, once each way. A half-answer must never
            # be written: it would overwrite good geometry with a gap, and the
            # routes derived from relation membership need BOTH halves anyway.
            lines, stops_by_route, stations = [], {}, []
            for attempt in range(3):
                if not lines:
                    lines, stops_by_route = fetch_lines(s["lat"], s["lon"], rts, want_stops=True)
                    time.sleep(1.5)
                if not stations:
                    stations = fetch_stations(s["lat"], s["lon"], rts)
                # A busy mirror can also answer THIN rather than empty: Kuala
                # Lumpur once came back as 1 station for 2 lines. The route
                # relations already told us roughly how many stops exist, so a
                # station list under a tenth of that is a truncated answer.
                # (0.1 is loose on purpose: an interchange is counted once per
                # route it serves, so stop nodes overcount stations ~3-4x.)
                declared = sum(len(v) for v in stops_by_route.values())
                if stations and declared and len(stations) < 0.1 * declared:
                    print(f"      thin ({len(stations)} stations for {declared} declared stops)"
                          f" — treating as partial", flush=True)
                    stations = []
                if lines and stations:
                    break
                if attempt < 2:
                    print(f"      partial ({len(stations)} stations, {len(lines)} lines)"
                          f" — retrying the empty half", flush=True)
                    time.sleep(6)
            stations = assign_routes(stations, stops_by_route)
            if not stations or not lines:
                print(f"      incomplete after retries "
                      f"({len(stations)} stations, {len(lines)} lines) — not written")
                fail += 1
            else:
                obj = {"slug": s["slug"], "city": s["city"], "stations": stations, "lines": lines}
                json.dump(obj, open(os.path.join(OUT_DIR, s["slug"] + ".json"), "w"),
                          ensure_ascii=False, separators=(",", ":"))
                record_provenance(s["slug"], s["city"], stations, lines, rts)
                print(f"      {len(stations)} stations, {len(lines)} lines  ✓"); ok += 1
        except Exception as e:
            print(f"      FAILED: {e}"); fail += 1
        time.sleep(SLEEP_S)
    print(f"\ndone: {ok} written, {fail} empty/failed. Files in {OUT_DIR}/")
    print("Drop them in the map's networks/ folder (or Drive) — each <slug>.json is auto-loaded.")

if __name__ == "__main__":
    main()
