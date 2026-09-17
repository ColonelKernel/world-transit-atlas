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
import json, csv, os, sys, time, math, urllib.request, urllib.parse, urllib.error

DATA_DIR = os.environ.get("TRANSIT_DATA_DIR", ".")
OUT_DIR  = os.path.join(DATA_DIR, "networks")
RADIUS_M = 45000          # search radius around each city centre (metres)
SLEEP_S  = 4              # politeness pause between cities
ENDPOINTS = [             # rotated on failure; all are public Overpass mirrors
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
UA = "WorldTransitAtlas/1.0 (personal research; contact: you@example.com)"

# our mode string -> OSM route relation types + station selectors
MODE_ROUTES = {
    "metro":      ["subway"],
    "lrt":        ["light_rail"],
    "tram":       ["tram"],
    "metro+tram": ["subway", "tram"],
    "metro+lrt":  ["subway", "light_rail"],
}
PALETTE = ["#e6194b","#3cb44b","#4363d8","#f58231","#911eb4","#46f0f0","#f032e6",
           "#bcf60c","#fabebe","#008080","#e6beff","#9a6324","#800000","#808000",
           "#000075","#a9a9a9","#ffe119","#00a1de","#ff6319","#6cbe45"]

# ---- HTTP ------------------------------------------------------------------
def overpass(query, tries=4):
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
def fetch_lines(lat, lon, route_types):
    rt = "|".join(route_types)
    q = (f'[out:json][timeout:180];'
         f'relation["route"~"^({rt})$"](around:{RADIUS_M},{lat},{lon});'
         f'out tags geom;')
    els = overpass(q).get("elements", [])
    lines, ci = [], 0
    for rel in els:
        if rel.get("type") != "relation":
            continue
        tags = rel.get("tags", {})
        ref = tags.get("ref") or tags.get("name") or f"L{len(lines)+1}"
        color = tags.get("colour") or tags.get("color")
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
    return list(merged.values())

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
            lines = fetch_lines(s["lat"], s["lon"], rts)
            time.sleep(1.5)
            stations = fetch_stations(s["lat"], s["lon"], rts)
            if not stations and not lines:
                print("      no OSM data found — skipped"); fail += 1
            else:
                obj = {"slug": s["slug"], "city": s["city"], "stations": stations, "lines": lines}
                json.dump(obj, open(os.path.join(OUT_DIR, s["slug"] + ".json"), "w"),
                          ensure_ascii=False, separators=(",", ":"))
                print(f"      {len(stations)} stations, {len(lines)} lines  ✓"); ok += 1
        except Exception as e:
            print(f"      FAILED: {e}"); fail += 1
        time.sleep(SLEEP_S)
    print(f"\ndone: {ok} written, {fail} empty/failed. Files in {OUT_DIR}/")
    print("Drop them in the map's networks/ folder (or Drive) — each <slug>.json is auto-loaded.")

if __name__ == "__main__":
    main()
