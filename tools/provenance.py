#!/usr/bin/env python3
"""
Geometry provenance: where each of the 201 network files actually came from.

The ridership layer records, per system, what a number counts, who published it,
when it was retrieved and how confident we are. The geometry layer -- the larger
half of the repo -- records `{slug, city, stations, lines}` and nothing else. So
the README can say the lines come from OpenStreetMap (ODbL), citylines.co
(CC-BY-SA), agency portals and a few GitHub datasets, and none of it can be
traced to a particular city. That is an attribution claim the data cannot
support, and it is why the repo has no LICENSE file: share-alike obligations
cannot be honoured for a corpus whose provenance is unknown per record.

This builds the record from evidence rather than assertion, and is regenerable:

  GIT EVIDENCE. Every file's introducing and modifying commits are known. Two
  commits refetched geometry from OpenStreetMap with recorded parameters
  (ee05c18, the Swiss three via osm.ch; c0cc9ef, the 34 gap cities via
  Overpass). Those cities have a source, a licence, a retrieval date and a
  method. The remaining 162 arrived in the initial import e9c9ac7 as one
  undifferentiated drop.

  STRUCTURAL EVIDENCE. The two groups were not produced by the same pipeline.
  The fetcher fills a station's `routes` from OSM's sparsely-tagged route_ref,
  so its output carries route strings on ~2% of stations; the initial import
  carries them on ~69%. Whatever produced the original corpus had line-station
  relations this fetcher does not get, which is consistent with the README's
  citylines/agency mix and inconsistent with it being this fetcher's output.

So 37 cities get a real source and licence, and 164 are recorded `unknown` with
the reason. Overstating the other 164 would make the ODbL notice a guess, which
is the one thing an attribution file may not be.

    python3 tools/provenance.py            # summary
    python3 tools/provenance.py --write    # (re)write data/networks/provenance.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NETWORKS = os.path.join(ROOT, "data", "networks")
OUT = os.path.join(NETWORKS, "provenance.csv")

# Commits that fetched geometry from a named source with known parameters.
# retrieved is the commit's author date.
FETCH_COMMITS = {
    "ee05c18": dict(
        source="OpenStreetMap (Overpass via osm.ch)",
        license="ODbL-1.0",
        attribution="(c) OpenStreetMap contributors",
        method="overpass relation[route] around city centre",
        retrieved="2026-09-17",
    ),
    "c0cc9ef": dict(
        source="OpenStreetMap (Overpass API)",
        license="ODbL-1.0",
        attribution="(c) OpenStreetMap contributors",
        method="tools/fetch_networks_osm.py, out geom, 45 km radius",
        retrieved="2026-09-17",
        # The same commit also EDITED two initial-import files -- it stripped a
        # depot track from each -- without fetching them. A file touched by a
        # fetch commit is not thereby fetched; these keep their unknown origin.
        exclude=("chennai", "kuala-lumpur"),
    ),
    # Later entries win for a city that appears in more than one, so a refetch
    # registered here carries its own retrieval date rather than the original's.
    "9ca0ff9": dict(
        source="OpenStreetMap (Overpass API)",
        license="ODbL-1.0",
        attribution="(c) OpenStreetMap contributors",
        method="tools/fetch_networks_osm.py, out geom, 45 km radius, routes from relation membership",
        retrieved="2026-09-26",
    ),
    "977c957": dict(
        source="OpenStreetMap (Overpass API)",
        license="ODbL-1.0",
        attribution="(c) OpenStreetMap contributors",
        method="tools/fetch_networks_osm.py, out geom, 45 km radius, routes from relation membership",
        retrieved="2026-09-26",
    ),
}

INITIAL_IMPORT = "e9c9ac7"

UNKNOWN = dict(
    source="unknown (initial import; mixed OSM / citylines.co / agency portals)",
    license="unknown",
    attribution="see README 'Data sources & attribution'",
    method="not recorded at import time",
    retrieved="",
)


def _files_in(rev: str) -> set[str]:
    out = subprocess.run(["git", "show", "--format=", "--name-only", rev],
                         capture_output=True, text=True, cwd=ROOT).stdout
    return {os.path.basename(l)[:-5] for l in out.splitlines()
            if l.startswith("data/networks/") and l.endswith(".json")}


def build() -> list[dict]:
    attributed: dict[str, tuple[str, dict]] = {}
    for rev, meta in FETCH_COMMITS.items():
        for slug in _files_in(rev) - set(meta.get("exclude", ())):
            attributed[slug] = (rev, meta)

    if not attributed:
        raise SystemExit(
            "No fetch commit resolved. In a shallow clone `git show` cannot see "
            f"{', '.join(FETCH_COMMITS)}, and every row would silently degrade to "
            "'unknown' -- which would look like a provenance regression rather "
            "than a missing history. Fetch full history (actions/checkout "
            "fetch-depth: 0) and re-run."
        )

    rows = []
    for path in sorted(glob.glob(os.path.join(NETWORKS, "*.json"))):
        slug = os.path.basename(path)[:-5]
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        stations = d.get("stations", [])
        # The pipeline fingerprint described in the module docstring, kept as a
        # column so the claim is checkable rather than a story in a comment.
        with_routes = sum(1 for s in stations if s.get("routes"))
        rev, meta = attributed.get(slug, (INITIAL_IMPORT, UNKNOWN))
        rows.append({
            "slug": slug,
            "city": d.get("city", ""),
            "source": meta["source"],
            "license": meta["license"],
            "attribution": meta["attribution"],
            "method": meta["method"],
            "retrieved": meta["retrieved"],
            "commit": rev,
            "basis": "fetch_commit" if slug in attributed else "initial_import",
            "n_stations": len(stations),
            "n_lines": len(d.get("lines", [])),
            "frac_stations_with_routes": round(with_routes / len(stations), 3) if stations else "",
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rows = build()
    known = [r for r in rows if r["license"] != "unknown"]
    print(f"{len(rows)} systems")
    print(f"  licence established : {len(known):3}  ({100*len(known)/len(rows):.0f}%)")
    print(f"  licence unknown     : {len(rows)-len(known):3}")
    print()
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    for src, n in sorted(by_source.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3}  {src}")

    def mean(rs):
        vals = [r["frac_stations_with_routes"] for r in rs if r["frac_stations_with_routes"] != ""]
        return sum(vals) / len(vals) if vals else 0.0

    print("\npipeline fingerprint (share of stations carrying a route string)")
    print(f"  fetch_commit   {mean([r for r in rows if r['basis']=='fetch_commit']):.3f}")
    print(f"  initial_import {mean([r for r in rows if r['basis']=='initial_import']):.3f}")
    print("  The gap is the evidence that the original corpus was not produced by")
    print("  tools/fetch_networks_osm.py, so its ODbL status cannot be assumed.")

    if args.write:
        with open(OUT, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {os.path.relpath(OUT, ROOT)}")
    else:
        print("\n(re-run with --write to emit provenance.csv)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
