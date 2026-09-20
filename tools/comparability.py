#!/usr/bin/env python3
"""
Comparability audit for the covariate table.

`trips_per_capita` is a ratio, and both halves of it are defined differently
across the 201 systems. Before any cross-city comparison is defensible, three
questions have to be answered per system, and the table currently answers only
one and a half of them:

1. WHAT DOES THE NUMERATOR COUNT?  Unlinked trips (boardings — each leg of a
   journey counts separately, the US NTD standard) or linked journeys (one per
   origin-destination trip, common in Europe and Asia)?  A transfer-heavy
   network reports roughly 1.2-1.6x more under boardings for identical travel.
   Nothing in the table records which convention a figure follows. The `src`
   field says where a number came from ("official-direct-file", "community"),
   not what it measures.

   This is the serious one, because transfer rates rise with network size and
   age — precisely the variables anyone would want to regress ridership on. An
   unrecorded convention does not add noise, it adds slope.

2. WHAT IS THE DENOMINATOR'S BOUNDARY?  159 systems use Demographia's built-up
   urban area, which is a consistent definition. The other 42 use Wikipedia
   infoboxes, national censuses and one-off sources whose boundary may be the
   city proper (too small) or the metro region (too large). Either error moves
   trips-per-capita by more than most of the effects worth measuring.

3. WHEN WAS IT COUNTED?  18 systems carry pre-2020 ridership against 177 from
   2022 or later. Their median trips-per-capita is 84.3 against 61.4 — a 37%
   gap that is a COVID artifact, not a difference between cities.

This script grades every system against those three and writes the result, so
an analysis can restrict itself to a comparable subset and say how big that
subset is. It fixes nothing by itself. Making `metric` knowable means going
back to 177 agency sources, and that is the work this audit is arguing for.

    python3 tools/comparability.py            # summary to stdout
    python3 tools/comparability.py --write    # also writes data/research/comparability.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "research", "covariates.csv")
OUT = os.path.join(ROOT, "data", "research", "comparability.csv")

# Ridership vintages this recent are mutually comparable; anything from 2019 or
# earlier is on the far side of the pandemic and is not.
VINTAGE_FLOOR = 2022

# The only systems whose counting convention is known without further research.
# The US National Transit Database defines UPT as unlinked passenger trips, so
# every US system's figure is boardings. Everywhere else it is genuinely
# unrecorded — do not guess by region.
KNOWN_METRIC_COUNTRIES = {"United States": "unlinked_boardings"}


def year_of(raw: str) -> int | None:
    """First 4-digit year in a vintage cell.

    The column is object dtype because two rows carry 'FY2025-26' and
    '2025-26'. Silent coercion would have dropped them to NaN and quietly
    shrunk the sample.
    """
    m = re.search(r"(\d{4})", str(raw or ""))
    return int(m.group(1)) if m else None


def grade(row: dict) -> dict:
    vintage = year_of(row.get("annual_year"))
    pop_src = str(row.get("pop_source") or "")
    metric = KNOWN_METRIC_COUNTRIES.get(row.get("country", ""), "unknown")

    checks = {
        "metric_known": metric != "unknown",
        "denominator_consistent": "demographia" in pop_src.lower(),
        "vintage_comparable": vintage is not None and vintage >= VINTAGE_FLOOR,
    }
    return {
        "slug": row.get("slug", ""),
        "city": row.get("city", ""),
        "country": row.get("country", ""),
        "region": row.get("region", ""),
        "ridership_metric": metric,
        "ridership_vintage": vintage if vintage is not None else "",
        "population_basis": "demographia_built_up"
        if checks["denominator_consistent"]
        else "other",
        **{k: str(v).lower() for k, v in checks.items()},
        # A system is usable in a cross-city ratio only if the denominator and
        # the vintage both hold. The metric is reported separately because it
        # currently fails for 88% of the table and would leave nothing.
        "usable_for_ratio": str(
            checks["denominator_consistent"] and checks["vintage_comparable"]
        ).lower(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write comparability.csv")
    args = ap.parse_args()

    with open(SRC, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    graded = [grade(r) for r in rows]
    n = len(graded)

    def count(key: str) -> int:
        return sum(1 for g in graded if g[key] == "true")

    print(f"covariate rows: {n}\n")
    print("per-check coverage")
    for key, label in (
        ("metric_known", "numerator convention recorded"),
        ("denominator_consistent", "denominator = built-up urban area"),
        ("vintage_comparable", f"ridership counted {VINTAGE_FLOOR} or later"),
    ):
        c = count(key)
        print(f"  {label:38} {c:3}/{n}  ({100*c/n:.0f}%)")

    usable = count("usable_for_ratio")
    print(f"\n  denominator AND vintage both hold     {usable:3}/{n}  ({100*usable/n:.0f}%)")
    both_and_metric = sum(
        1 for g in graded if g["usable_for_ratio"] == "true" and g["metric_known"] == "true"
    )
    print(f"  ...and numerator convention known     {both_and_metric:3}/{n}  ({100*both_and_metric/n:.0f}%)")

    print("\nnumerator convention")
    for k, v in Counter(g["ridership_metric"] for g in graded).most_common():
        print(f"  {k:22} {v:3}")

    print("\nvintage spread")
    for k, v in sorted(Counter(g["ridership_vintage"] for g in graded).items(), key=lambda kv: str(kv[0])):
        print(f"  {str(k) or '(none)':22} {v:3}")

    if args.write:
        with open(OUT, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(graded[0]))
            w.writeheader()
            w.writerows(graded)
        print(f"\nwrote {os.path.relpath(OUT, ROOT)}")
    else:
        print("\n(re-run with --write to emit data/research/comparability.csv)")

    print(
        "\nBottom line: a cross-city trips-per-capita comparison is defensible for\n"
        f"{usable} of {n} systems on denominator and vintage, and for {both_and_metric} once the\n"
        "counting convention has to be known too. Any model fitted on all 201 is\n"
        "partly fitting the bookkeeping."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
