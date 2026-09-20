#!/usr/bin/env python3
"""
Comparability audit and verified-dataset builder.

`trips_per_capita` is a ratio, and both halves of it are defined differently
across the 201 systems. An earlier version of this script graded that problem
and ended by saying the fix meant going back to 177 agency sources. It was
wrong on the arithmetic and wrong on the diagnosis, and both errors are worth
recording because they are the reason this file exists.

WRONG ON THE ARITHMETIC. The counting convention was already recorded for 185
systems in data/ridership/system_rank.csv and for the other 11 in
data/ridership/ridership_long.csv -- the provenance layer existed and had simply
not been brought into the repo. The true gap was never 177 conventions; it was
11 dangling source_id values that resolve to no row in sources.csv.

WRONG ON THE DIAGNOSIS. The convention is one of FOUR axes a cross-city ratio
depends on, and grading only the first is how a plausible-looking regression
got built on bookkeeping:

  1. NUMERATOR CONVENTION -- boardings, station entries, or linked journeys.
     A transfer-heavy network reports ~1.2-1.6x more under boardings for
     identical travel. Now recorded for every system that has a figure.
  2. NUMERATOR MODE SCOPE -- metro only, metro+tram, or the whole multimodal
     agency including bus. Recorded NOWHERE, and it is the likeliest
     explanation for the extreme values (Prague at 488 trips/capita is tagged
     metro+tram, but DPP's headline figure covers the whole agency).
  3. DENOMINATOR BASIS -- built-up urban area, metro region, or city proper.
     The previous version tested `"demographia" in pop_source`, a vendor-name
     substring standing in for a concept, which misfiled 15 systems that use
     the identical concept under a national name (INSEE unite urbaine,
     Statistics Sweden tatort, Statistics Finland taajama, and so on).
  4. VINTAGE -- the figures run 2013 to 2026, straddling COVID.

This script grades all four, applies the reviewed corrections in
data/ridership/measure_def_overrides.csv, and writes both the grade table and
the full verified dataset. It still fixes nothing by itself; it makes what is
and is not known machine-readable, which is the part that was missing.

    python3 tools/comparability.py            # summary to stdout
    python3 tools/comparability.py --write    # also write both CSVs
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COV = os.path.join(ROOT, "data", "research", "covariates.csv")
RANK = os.path.join(ROOT, "data", "ridership", "system_rank.csv")
LONG = os.path.join(ROOT, "data", "ridership", "ridership_long.csv")
SOURCES = os.path.join(ROOT, "data", "ridership", "sources.csv")
OVERRIDES = os.path.join(ROOT, "data", "ridership", "measure_def_overrides.csv")
NETWORKS = os.path.join(ROOT, "data", "networks")
OUT_GRADES = os.path.join(ROOT, "data", "research", "comparability.csv")
OUT_VERIFIED = os.path.join(ROOT, "data", "research", "ridership_verified.csv")

# Ridership vintages this recent are mutually comparable; anything from 2019 or
# earlier is on the far side of the pandemic and is not.
VINTAGE_FLOOR = 2022

# ---------------------------------------------------------------------------
# 1. The counting convention.
# ---------------------------------------------------------------------------

# The enum defined in data/ridership/SCHEMA.md. Nothing outside this set is a
# valid value.
ENUM = (
    "station_entries",     # taps/entries at faregates
    "unlinked_trips",      # boardings including transfers (US NTD "UPT")
    "linked_journeys",     # one trip end-to-end regardless of transfers
    "passenger_journeys",  # the operator's headline "journeys" figure
    "estimated",           # modeled or derived
)

# ridership_long.csv carries 20 distinct measure_def strings, most of them prose
# wrapped around an enum value. Two rules here are NOT substring matching and
# are the reason this is a reviewed table rather than a clever regex:
#
#   "estimated station_entries -- DERIVED by ..."  contains `station_entries`
#   but IS `estimated`. A first-match substring test gets this backwards on 180
#   rows, so `estimated` is checked as a PREFIX before anything else.
#
#   "boardings (rail lines)" contains no enum value at all. `boardings` is an
#   alias for `unlinked_trips` and has to be declared as one.
ALIASES = {"boardings": "unlinked_trips"}


class UnmappableMeasure(ValueError):
    """Raised rather than falling through to 'unknown'.

    A silent fall-through is the failure mode that produced an empty group and
    a plausible-looking regression earlier in this work. An unrecognized string
    is a bug in this table, not a property of the world.
    """


def normalize_measure(raw: str) -> tuple[str, str]:
    """-> (enum value, the original string kept verbatim as a note)."""
    note = (raw or "").strip()
    if not note:
        return "", ""
    low = note.lower()
    if low.startswith("estimated"):
        return "estimated", note
    for value in ENUM:
        if value in low:
            return value, note
    for alias, value in ALIASES.items():
        if low.startswith(alias):
            return value, note
    raise UnmappableMeasure(
        f"{note!r} matches no value in SCHEMA.md's measure_def enum. "
        f"Add it to ENUM or ALIASES -- do not let it default."
    )


# Which conventions are interchangeable with which. `estimated` is its own
# family because it says how the number was produced, not what it counts.
FAMILY = {
    "unlinked_trips": "boarding",
    "station_entries": "entries",
    "linked_journeys": "journey",
    "passenger_journeys": "journey",
    "estimated": "estimated",
}

# ---------------------------------------------------------------------------
# 2. The denominator basis.
# ---------------------------------------------------------------------------

# Classified by CONCEPT, not by vendor name. Demographia is itself assembled
# from national built-up-area definitions, so a national definition of the same
# concept is equally comparable -- which the old substring test denied for 15
# systems. Checked most-specific first: "metropolitan area" must beat
# "agglomeration" where both appear.
CITY_PROPER = (
    "city-proper", "city proper", "municipality total", "urban district",
    "special municipality", "stadtkreis", "partial sum",
)
METRO_REGION = (
    "metropolitan area", "metro area", "census metropolitan", "functional urban",
    "employment area", "regiao metropolitana", "região metropolitana",
    "region (", "haaglanden", "metropolitan-area",
)
BUILT_UP = (
    "demographia",       # the vendor, 159 systems
    "built-up", "built up",
    "unite urbaine", "unité urbaine",   # France, INSEE
    "tatort", "tätort",                 # Sweden
    "taajama",                          # Finland
    "tettsted",                         # Norway
    "byomrade", "byområde",             # Denmark
    "naselje",                          # Croatia
    "poleodomiko",                      # Greece
    "agglomeration",                    # Switzerland, FSO
)


def classify_denominator(pop_source: str) -> str:
    text = (pop_source or "").lower()
    for k in CITY_PROPER:
        if k in text:
            return "city_proper"
    for k in METRO_REGION:
        if k in text:
            return "metro_region"
    for k in BUILT_UP:
        if k in text:
            return "built_up_urban_area"
    return "unclassified"


# ---------------------------------------------------------------------------
# 3. The vintage.
# ---------------------------------------------------------------------------

# Two systems carry a fiscal year. India's runs 1 April to 31 March, so
# FY2025-26 is majority-2025 and is recorded as 2025. Written out because
# int(raw[:4]) would get the same answer for the wrong reason and would break
# on any country whose fiscal year opens in a different month.
FISCAL_YEAR_STARTS_IN_APRIL = ("India",)


def normalize_vintage(raw: str, country: str) -> tuple[int | None, str]:
    """-> (calendar year the figure mostly covers, basis)."""
    text = str(raw or "").strip()
    if not text:
        return None, ""
    m = re.search(r"(\d{4})", text)
    if not m:
        return None, ""
    year = int(m.group(1))
    spans_two_years = bool(re.search(r"\d{4}\s*-\s*\d{2,4}", text))
    if spans_two_years and country in FISCAL_YEAR_STARTS_IN_APRIL:
        return year, "fiscal_year_apr_mar"
    if spans_two_years:
        return year, "spans_two_years"
    return year, "calendar_year"


# ---------------------------------------------------------------------------


def load_rows() -> list[dict]:
    with open(COV, newline="", encoding="utf-8") as fh:
        cov = list(csv.DictReader(fh))
    with open(RANK, newline="", encoding="utf-8") as fh:
        rank = {r["system_id"]: r for r in csv.DictReader(fh)}
    with open(OVERRIDES, newline="", encoding="utf-8") as fh:
        over = {r["slug"]: r for r in csv.DictReader(fh)}

    # ridership_long carries a measure_def for the 11 systems system_rank left
    # blank -- they were added to covariates after the provenance table was
    # built, not left unsourced on purpose.
    fallback: dict[str, dict] = {}
    with open(LONG, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            fallback.setdefault(r["system_id"], r)

    stations = {}
    for path in glob.glob(os.path.join(NETWORKS, "*.json")):
        with open(path, encoding="utf-8") as fh:
            stations[os.path.basename(path)[:-5]] = len(json.load(fh).get("stations", []))

    out = []
    for r in cov:
        slug = r["slug"]
        rk = rank.get(slug, {})
        ov = over.get(slug)

        measure, note = normalize_measure(rk.get("measure_def", ""))
        basis_of_measure = "system_rank"
        if not measure:
            measure, note = normalize_measure(fallback.get(slug, {}).get("measure_def", ""))
            basis_of_measure = "ridership_long" if measure else ""

        confidence = rk.get("confidence", "")
        url = rk.get("annual_url", "")
        source_id = fallback.get(slug, {}).get("source_id", "")
        value_status = ""
        evidence = ""

        if ov:
            # A reviewed correction wins over the ported table, including when
            # it clears a value back to unknown.
            measure = ov["measure_def"]
            note = note or ""
            confidence = ov["confidence"]
            value_status = ov["value_status"]
            evidence = ov["evidence"]
            url = ov["url"] or url
            basis_of_measure = f"override:{ov['source']}"

        vintage, vintage_basis = normalize_vintage(r.get("annual_year"), r.get("country", ""))
        riders = (r.get("annual_riders") or "").strip()

        out.append({
            "slug": slug,
            "city": r.get("city", ""),
            "country": r.get("country", ""),
            "region": r.get("region", ""),
            "mode": r.get("mode", ""),
            "n_stations": stations.get(slug, ""),
            "annual_riders": riders,
            "annual_year_raw": r.get("annual_year", ""),
            "annual_year": vintage if vintage is not None else "",
            "vintage_basis": vintage_basis,
            "measure_def": measure,
            "measure_note": note,
            "measure_source": basis_of_measure,
            "convention_family": FAMILY.get(measure, ""),
            "metric_confidence": confidence,
            "value_status": value_status,
            "evidence": evidence,
            "annual_url": url,
            "source_id": source_id,
            "urban_pop": r.get("urban_pop", ""),
            "urban_area_km2": r.get("urban_area_km2", ""),
            "pop_source": r.get("pop_source", ""),
            "population_basis": classify_denominator(r.get("pop_source", "")),
            "trips_per_capita": r.get("trips_per_capita", ""),
            "mode_scope": "",          # axis 2: recorded nowhere yet
            "mode_scope_checked": "",  # blank is honest; a guess is not
        })
    return out


def grade(rows: list[dict]) -> list[dict]:
    for r in rows:
        has = bool(r["annual_riders"])
        vintage = r["annual_year"]
        r["has_ridership"] = str(has).lower()
        r["metric_known"] = str(bool(r["measure_def"])).lower()
        r["citation_resolves"] = str(bool(r["annual_url"])).lower()
        r["denominator_consistent"] = str(r["population_basis"] == "built_up_urban_area").lower()
        r["vintage_comparable"] = str(
            vintage != "" and int(vintage) >= VINTAGE_FLOOR
        ).lower()
        r["usable_for_ratio"] = str(
            has
            and r["denominator_consistent"] == "true"
            and r["vintage_comparable"] == "true"
            and r["metric_known"] == "true"
        ).lower()
    return rows


def check_referential_integrity(rows: list[dict]) -> list[str]:
    """SCHEMA.md: 'Every value traces to exactly one source_id.' Nothing enforced it."""
    with open(SOURCES, newline="", encoding="utf-8") as fh:
        known = {r["source_id"] for r in csv.DictReader(fh)}
    return sorted(
        r["source_id"] for r in rows
        if r["source_id"] and r["source_id"] not in known
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write both CSVs")
    args = ap.parse_args()

    rows = grade(load_rows())
    n = len(rows)
    have = [r for r in rows if r["has_ridership"] == "true"]
    h = len(have)

    def count(key, among=have):
        return sum(1 for r in among if r[key] == "true")

    print(f"{n} systems; {h} carry an annual ridership figure\n")

    print("counting convention (axis 1)")
    for k, v in Counter(r["measure_def"] or "(unknown)" for r in have).most_common():
        print(f"  {k:22} {v:3}")
    print("\nconvention family")
    for k, v in Counter(r["convention_family"] or "(unknown)" for r in have).most_common():
        print(f"  {k:22} {v:3}")

    print("\ndenominator basis (axis 3)")
    for k, v in Counter(r["population_basis"] for r in rows).most_common():
        print(f"  {k:22} {v:3}")

    print("\nvintage basis (axis 4)")
    for k, v in Counter(r["vintage_basis"] or "(none)" for r in rows).most_common():
        print(f"  {k:22} {v:3}")

    print("\nper-check coverage, over the systems that have a figure")
    for key, label in (
        ("metric_known", "counting convention recorded"),
        ("citation_resolves", "a citation URL is recorded"),
        ("denominator_consistent", "denominator = built-up urban area"),
        ("vintage_comparable", f"ridership counted {VINTAGE_FLOOR} or later"),
    ):
        c = count(key)
        print(f"  {label:38} {c:3}/{h}  ({100*c/h:.0f}%)")
    usable = count("usable_for_ratio")
    print(f"\n  all three hold                         {usable:3}/{h}  ({100*usable/h:.0f}%)")
    one_family = sum(1 for r in have
                     if r["usable_for_ratio"] == "true" and r["convention_family"] == "journey")
    print(f"  ...and restricted to one family        {one_family:3}/{h}  ({100*one_family/h:.0f}%)")

    print("\nvalue status, where a source was re-checked")
    for k, v in Counter(r["value_status"] for r in have if r["value_status"]).most_common():
        print(f"  {k:22} {v:3}")

    cited = count("citation_resolves")
    # SCHEMA.md's non-negotiable is "Every value traces to exactly one source_id",
    # and almost nothing does: sources.csv is a rich citation table for 48
    # systems, while source_id is generated as "<slug>-annual"/"<slug>-ntd" for
    # all 201. The IDs are a naming convention wearing a foreign key's clothes.
    # The citations mostly do exist -- in system_rank.annual_url -- so this is a
    # schema defect, not 189 uncited numbers. Reported rather than papered over.
    dangling = check_referential_integrity(rows)
    print(f"\nschema integrity: {len(dangling)} of {n} source_id values resolve to no row in")
    print(f"  sources.csv, which covers {len(set(r['system_id'] for r in csv.DictReader(open(SOURCES, newline='', encoding='utf-8'))))} systems. "
          f"SCHEMA.md requires every value to trace to")
    print("  exactly one source_id; the generated ids do not. The citations themselves")
    print(f"  mostly exist in system_rank.annual_url ({cited}/{h}). Examples of ids that")
    print("  resolve to nothing: " + ", ".join(dangling[:6]) + ", ...")

    if args.write:
        with open(OUT_VERIFIED, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        keep = ("slug", "city", "country", "region", "measure_def", "convention_family",
                "annual_year", "population_basis", "metric_known", "citation_resolves",
                "denominator_consistent", "vintage_comparable", "usable_for_ratio")
        with open(OUT_GRADES, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(keep))
            w.writeheader()
            w.writerows({k: r[k] for k in keep} for r in rows)
        print(f"\nwrote {os.path.relpath(OUT_VERIFIED, ROOT)}")
        print(f"wrote {os.path.relpath(OUT_GRADES, ROOT)}")
    else:
        print("\n(re-run with --write to emit both CSVs)")

    print(
        f"\nBottom line: the counting convention is now recorded for "
        f"{count('metric_known')} of {h} systems that have a figure, against 24 under the\n"
        f"previous audit. A cross-city ratio is defensible for {usable} of them on all\n"
        f"three checkable axes, and for {one_family} once a single convention family is\n"
        f"required. The fourth axis -- what modes the numerator covers -- is still\n"
        f"recorded nowhere, and no amount of the first three substitutes for it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
