#!/usr/bin/env python3
"""
fetch_ridership.py — standardized ridership loader for the World Transit Atlas.

Run this on any machine with open internet (your Mac, a server, Colab). It pulls
the live time-series from each documented open-data API, normalizes every source
into ONE tidy long table (see data/ridership/SCHEMA.md), and appends the
researched annual baselines for systems that only publish yearly.

    python3 tools/fetch_ridership.py            # pulls everything
    python3 tools/fetch_ridership.py --only new-york,chicago
    python3 tools/fetch_ridership.py --write    # actually overwrite ridership_long.csv

Why a loader instead of a static dump: the cloud sandbox this was built in cannot
reach open-data portals, but your machine can. This script IS the data pipe — it
also documents exactly how each number was obtained, so the dataset is reproducible.

Add a system by dropping one entry in SOCRATA or CUSTOM below.

--------------------------------------------------------------------------------
A NOTE ON THE GUARDS, because this script used to lie about what it produced.

Three of its inputs are not in the repository:

    data/ridership/ntd_map.json         slug -> NTD agency id, drives 6,782 rows
    data/ridership/annual_baseline.json the researched annual figures
    merged_sorted.json                  slug -> city/country/region

The first two were read behind bare `os.path.exists` guards, so a run with both
missing produced a *much* smaller table and said nothing about it — and then
overwrote the good one. The third was read with no guard at all, so from the repo
root this script did not run: it raised FileNotFoundError on line 1 of main().

Now: missing inputs are collected, named, and reported with the row count they
cost, and the script REFUSES TO WRITE unless every required input is present or
--force is passed. It also defaults to a dry run. A loader that silently emits a
degraded dataset is worse than one that does not run, because the degraded
dataset looks exactly like the real one.

The slug -> city/country/region lookup now comes from data/research/covariates.csv,
which is in the repository and covers all 201 systems, instead of the absent
merged_sorted.json.
--------------------------------------------------------------------------------
"""
import csv, json, sys, calendar, urllib.request, urllib.parse, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DAT  = os.path.join(ROOT, "data", "ridership")
COV  = os.path.join(ROOT, "data", "research", "covariates.csv")

# --- Socrata daily datasets -> server-side monthly aggregation (compact, exact) ---
# system_id : (domain, dataset_id, date_field, value_field, measure_def)
SOCRATA = {
    "new-york": ("data.ny.gov", "vxuj-8kew", "date", "subways_total_estimated_ridership", "station_entries"),
    "chicago":  ("data.cityofchicago.org", "5neh-572f", "date", "rides", "station_entries"),
    # extend, e.g.:
    # "boston": ("...socrata domain...", "...id...", "...date...", "...value...", "unlinked_trips"),
}

# --- US National Transit Database: rail-only monthly UPT since 2002, by NTD id ---
# One dataset (8bui-9xvu) covers every US agency. ntd_map.json maps our slugs -> ntd_id.
NTD_RESOURCE = ("data.transportation.gov", "8bui-9xvu")
NTD_RAIL_MODES = ("HR", "LR", "MG", "YR", "CC")  # metro, light rail, monorail/AGT, hybrid, cable


def fetch_ntd_rail_monthly(ntd_id):
    modes = ",".join(f"'{m}'" for m in NTD_RAIL_MODES)
    q = (f"$select=date_trunc_ym(date) AS ym, sum(upt) AS riders"
         f"&$where=ntd_id='{ntd_id}' AND mode in({modes})&$group=ym&$order=ym&$limit=100000")
    url = f"https://{NTD_RESOURCE[0]}/resource/{NTD_RESOURCE[1]}.json?" + urllib.parse.quote(q, safe="=&$():,'")
    with urllib.request.urlopen(url, timeout=90) as r:
        rows = json.load(r)
    out = []
    for row in rows:
        try: out.append((row["ym"][:7], float(row["riders"])))
        except (TypeError, ValueError, KeyError): continue
    return out


def days_in_month(y, m): return calendar.monthrange(y, m)[1]


def fetch_socrata_monthly(domain, dsid, datef, valf):
    q = (f"$select=date_trunc_ym({datef}) AS ym, sum({valf}) AS riders"
         f"&$group=ym&$order=ym&$limit=100000")
    url = f"https://{domain}/resource/{dsid}.json?" + urllib.parse.quote(q, safe="=&$():,")
    with urllib.request.urlopen(url, timeout=90) as r:
        rows = json.load(r)
    out = []
    for row in rows:
        ym = row["ym"][:7]
        try: v = float(row["riders"])
        except (TypeError, ValueError): continue
        out.append((ym, v))
    return out


def load_meta():
    """slug -> city/country/region, from the covariates table that is actually here."""
    if not os.path.exists(COV):
        return None
    with open(COV, newline="", encoding="utf-8") as fh:
        return {r["slug"]: r for r in csv.DictReader(fh)}


def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    write = "--write" in sys.argv
    force = "--force" in sys.argv

    out = os.path.join(DAT, "ridership_long.csv")
    ntd_path = os.path.join(DAT, "ntd_map.json")
    ann_path = os.path.join(DAT, "annual_baseline.json")

    # Every missing input is named with the damage it does, before anything runs.
    missing = []
    meta = load_meta()
    if meta is None:
        missing.append((COV, "slug -> city/country/region; every row loses its labels"))
        meta = {}
    if not os.path.exists(ntd_path):
        missing.append((ntd_path, "US NTD slug -> agency id; costs ~6,782 monthly rows (~84% of the table)"))
    if not os.path.exists(ann_path):
        missing.append((ann_path, "researched annual baselines; costs the annual figures for ~165 systems"))

    if missing:
        print("MISSING INPUTS — this run would produce a degraded table:\n")
        for path, damage in missing:
            print(f"  {os.path.relpath(path, ROOT)}")
            print(f"      {damage}")
        print()
        if write and not force:
            existing = ""
            if os.path.exists(out):
                with open(out, newline="", encoding="utf-8") as fh:
                    existing = f" (currently {sum(1 for _ in fh) - 1} rows)"
            print(f"REFUSING to overwrite {os.path.relpath(out, ROOT)}{existing}.")
            print("Restore the inputs above, or pass --force if you truly mean to shrink it.")
            return 1

    tidy = []

    def row(slug, ym, gran, val, mdef, sid):
        m = meta.get(slug, {})
        y, mo = int(ym[:4]), int(ym[5:7]) if len(ym) >= 7 else 1
        de = round(val / days_in_month(y, mo), 1) if gran == "monthly" else round(val / (366 if calendar.isleap(y) else 365), 1)
        ps = f"{ym}-01" if gran == "monthly" else f"{y}-01-01"
        tidy.append([slug, m.get("city"), m.get("country"), m.get("region"), "ridership",
                     ps, gran, val, "passengers", mdef, de, "true", sid])

    for slug, (dom, dsid, datef, valf, mdef) in SOCRATA.items():
        if only and slug not in only: continue
        try:
            series = fetch_socrata_monthly(dom, dsid, datef, valf)
            for ym, v in series: row(slug, ym, "monthly", v, mdef, f"{slug}-daily")
            print(f"  {slug} (daily src): {len(series)} months  [{series[0][0]}..{series[-1][0]}]")
        except Exception as e:
            print(f"  {slug}: FAILED {e}")

    # US systems: uniform rail-only monthly from NTD
    if os.path.exists(ntd_path):
        for slug, ntd_id in json.load(open(ntd_path)).items():
            if only and slug not in only: continue
            try:
                series = fetch_ntd_rail_monthly(ntd_id)
                for ym, v in series: row(slug, ym, "monthly", v, "unlinked_trips (rail modes, NTD)", f"{slug}-ntd")
                print(f"  {slug} (NTD {ntd_id}): {len(series)} months  [{series[0][0]}..{series[-1][0]}]")
            except Exception as e:
                print(f"  {slug} (NTD): FAILED {e}")

    # annual baselines from the sourced index
    if os.path.exists(ann_path):
        for a in json.load(open(ann_path)):
            if only and a["slug"] not in only: continue
            if a.get("value") and a.get("year"):
                row(a["slug"], str(a["year"]), "annual", a["value"], a.get("measure_def") or "", f"{a['slug']}-annual")

    print(f"\nassembled {len(tidy)} rows")
    if not write:
        print(f"(dry run — re-run with --write to overwrite {os.path.relpath(out, ROOT)})")
        return 0

    os.makedirs(DAT, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system_id","city","country","region","metric","period_start","granularity",
                    "value","unit","measure_def","daily_equiv","is_estimate","source_id"])
        w.writerows(tidy)
    print(f"wrote {os.path.relpath(out, ROOT)}  ({len(tidy)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
