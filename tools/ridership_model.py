#!/usr/bin/env python3
"""
What predicts urban rail ridership -- and what turned out to be bookkeeping.

This script exists because of a question: "may want to verify the data is of
the same type and comparable by unit." At the time there was a finished-looking
result -- density raises trips per capita, p=.0001 -- and the question stopped
it being published. It was right to.

THE LADDER IS THE FINDING. Each rung below removes one defect from the rung
above, and the coefficients move enough that reporting only the last one would
hide the work that makes it trustworthy. In order, what each rung fixes:

  A  the original specification, iid standard errors
  B  + country-clustered SEs. 54 clusters, unbalanced (China 30, US 24), and
     gasoline price is a pure country-level regressor -- a Moulton problem.
     This alone moves density from p=.0002 to p=.07.
  C  + counting-convention dummies, now that the convention is known
  D  + region fixed effects, with EUROPE as the deliberate base. Dropping the
     first level alphabetically makes Africa (n=3) the omitted category and
     inflates every region SE against it.
  E  drop Asia. A convention effect that only exists inside one region is not
     a convention effect.
  F  + log(stations) and mode. Network extent was never controlled for and the
     station counts were sitting in data/networks/*.json all along.

SPECIFIED ON log(annual_riders), NOT log(trips_per_capita). The two are the
same regression -- trips_per_capita = riders / population, so the ratio form
just imposes a coefficient of exactly 1 on log_pop. Writing it this way keeps
the population coefficient free and forces the honest statement: ridership
scales SUBLINEARLY with city size. The ratio form makes the identical number
look like a discovered per-capita penalty.

THREE THINGS THIS SCRIPT WILL NOT DO.

  It does not interpret log_stations. Network extent is determined jointly with
  ridership; it earns its place as a comparability control and its coefficient
  is not a result.

  It does not report a convention effect as an effect. Convention is nearly
  nested within region -- most countries use exactly one -- so the two cannot
  be told apart here. That is itself the answer to the original question.

  It does not use causal language. Nothing here is identified. "Systems with X
  report higher ridership", never "X increases ridership".

    python3 tools/ridership_model.py
"""

from __future__ import annotations

import csv
import math
import os
import sys
from collections import Counter, defaultdict
from math import erf, sqrt

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "research", "ridership_verified.csv")

BASE_REGION = "Europe"   # deliberate, not alphabetical
BASE_FAMILY = "journey"  # the omitted convention category


def num(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def load():
    with open(DATA, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        riders, pop = num(r["annual_riders"]), num(r["urban_pop"])
        gas = num(r.get("gasoline_price_usd_l"))
        stations, year = num(r["n_stations"]), num(r["annual_year"])
        area = num(r["urban_area_km2"])
        fam = r["convention_family"]
        if not riders or not pop or not stations or riders <= 0:
            continue
        out.append({
            "slug": r["slug"], "country": r["country"], "region": r["region"],
            "mode": r["mode"], "family": fam or "unknown",
            "y": math.log(riders),
            "log_pop": math.log(pop),
            "log_stations": math.log(stations),
            "log_area": math.log(area) if area and area > 0 else None,
            "vintage": year,
            "tpc": num(r["trips_per_capita"]),
            "usable": r.get("usable_for_ratio") == "true",
            "scope": r.get("mode_scope") or "unknown",
        })
    return out


def attach_covariates(rows):
    """gas price and opening year live in covariates.csv, not the verified table."""
    with open(os.path.join(ROOT, "data", "research", "covariates.csv"),
              newline="", encoding="utf-8") as fh:
        cov = {r["slug"]: r for r in csv.DictReader(fh)}
    keep = []
    for r in rows:
        c = cov.get(r["slug"], {})
        gas, opening = num(c.get("gasoline_price_usd_l")), num(c.get("opening_year"))
        if gas is None or opening is None or 2026 - opening <= 0:
            continue
        r["gas"] = gas
        r["log_age"] = math.log(2026 - opening)
        keep.append(r)
    return keep


def ols(rows, terms, labels, title, cluster="country", show_fe=False):
    """OLS with cluster-robust SEs, and a rank assertion that pinv would skip.

    np.linalg.pinv returns a minimum-norm solution on a rank-deficient design
    with no error and a perfectly normal-looking R2 -- an intercept plus every
    region dummy does exactly that. Asserting rank is the difference between a
    wrong answer and a stack trace.
    """
    cols = []
    for t in terms:
        if isinstance(t, tuple):
            key, level = t
            cols.append(np.array([1.0 if r[key] == level else 0.0 for r in rows]))
        else:
            cols.append(np.array([r[t] for r in rows]))
    X = np.column_stack([np.ones(len(rows))] + cols)
    y = np.array([r["y"] for r in rows])

    n, k = X.shape
    rank = np.linalg.matrix_rank(X)
    assert rank == k, f"{title}: design is rank deficient (k={k}, rank={rank})"

    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    XtXi = np.linalg.pinv(X.T @ X)

    groups = defaultdict(list)
    for i, r in enumerate(rows):
        groups[r[cluster]].append(i)
    meat = np.zeros((k, k))
    for idx in groups.values():
        u = (X[idx].T @ resid[idx]).reshape(-1, 1)
        meat += u @ u.T
    G = len(groups)
    df = n - rank
    se = np.sqrt(np.diag(XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / df)))

    ss = resid @ resid
    r2 = 1 - ss / ((y - y.mean()) @ (y - y.mean()))
    adj = 1 - (1 - r2) * (n - 1) / df

    print(f"\n{title}")
    print(f"   n={n}  adj R2={adj:.3f}  clusters={G}  df={df}")
    for lab, b, s in zip(["(const)"] + labels, beta, se):
        t = b / s
        p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
        stars = "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else ""
        if lab.startswith("reg_") and not show_fe and not stars:
            continue
        print(f"     {lab:18} {b:+7.3f}  se {s:.3f}  p={p:.4f} {stars}")
    return dict(zip(["(const)"] + labels, beta))


def geomean(xs):
    xs = [x for x in xs if x and x > 0]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float("nan")


def descriptive(rows):
    """The table that makes the regression unnecessary.

    Cell counts in every cell, no exceptions. A reader who sees Asia's journey
    cell holding 9 systems next to Europe's holding 47 does not need a
    coefficient to know the convention dummy is not identified.
    """
    print("\n" + "=" * 74)
    print("REGION x CONVENTION: geometric mean trips per capita (n in brackets)")
    print("=" * 74)
    fams = ["journey", "entries", "boarding", "estimated", "unknown"]
    regions = sorted({r["region"] for r in rows})
    print(f"{'region':30}" + "".join(f"{f[:9]:>13}" for f in fams))
    for reg in regions:
        line = f"{reg[:29]:30}"
        for f in fams:
            cell = [r["tpc"] for r in rows if r["region"] == reg and r["family"] == f]
            line += f"{(f'{geomean(cell):.0f} [{len(cell)}]' if cell else '- [0]'):>13}"
        print(line)
    line = f"{'ALL':30}"
    for f in fams:
        cell = [r["tpc"] for r in rows if r["family"] == f]
        line += f"{(f'{geomean(cell):.0f} [{len(cell)}]' if cell else '- [0]'):>13}"
    print(line)

    j = geomean([r["tpc"] for r in rows if r["family"] == "journey"])
    e = geomean([r["tpc"] for r in rows if r["family"] == "entries"])
    b = geomean([r["tpc"] for r in rows if r["family"] == "boarding"])
    print(f"\n  raw entries/journey ratio  {e/j:.2f}x")
    print(f"  raw boarding/journey ratio {b/j:.2f}x")
    print("  Theory says boardings >= entries >= journeys. Report these next to any")
    print("  adjusted estimate: when adjustment moves a descriptive quantity a long")
    print("  way, the adjustment is the thing that needs explaining.")

    print("\n  convention is nearly nested within country:")
    by_country = defaultdict(set)
    for r in rows:
        if r["family"] not in ("unknown", "estimated"):
            by_country[r["country"]].add(r["family"])
        single = sum(1 for v in by_country.values() if len(v) == 1)
    mixed_systems = sum(1 for r in rows if len(by_country.get(r["country"], ())) > 1)
    print(f"    {single} of {len(by_country)} countries use exactly one convention;")
    print(f"    only {mixed_systems} of {len(rows)} systems sit in a mixed-convention country.")


def main():
    rows = attach_covariates(load())
    print(f"loaded {len(rows)} systems with ridership, population, stations, "
          f"gas price and opening year")
    print("families:", dict(Counter(r["family"] for r in rows)))

    descriptive(rows)

    base = ["log_pop", "log_age", "gas"]
    base_lab = ["log_pop", "log_age", "gas_price"]
    fam_levels = [f for f in ("boarding", "entries", "estimated")
                  if any(r["family"] == f for r in rows)]
    FAM = [("family", f) for f in fam_levels]
    FAM_LAB = [f"is_{f}" for f in fam_levels]

    print("\n" + "=" * 74)
    print("THE LADDER")
    print("=" * 74)

    ols(rows, base, base_lab, "A. baseline, country-clustered")
    ols(rows, base + FAM, base_lab + FAM_LAB,
        "B. + counting convention (journey = reference)")

    regions = sorted({r["region"] for r in rows if r["region"] != BASE_REGION})
    REG = [("region", x) for x in regions]
    REG_LAB = [f"reg_{x[:12]}" for x in regions]

    ols(rows, base + REG, base_lab + REG_LAB,
        f"C. + region fixed effects ({BASE_REGION} = base)")
    ols(rows, base + REG + FAM, base_lab + REG_LAB + FAM_LAB,
        "D. + region FE and convention together")

    no_asia = [r for r in rows if r["region"] != "Asia"]
    regions2 = sorted({r["region"] for r in no_asia if r["region"] != BASE_REGION})
    fam2 = [f for f in fam_levels if any(r["family"] == f for r in no_asia)]
    ols(no_asia,
        base + [("region", x) for x in regions2] + [("family", f) for f in fam2],
        base_lab + [f"reg_{x[:12]}" for x in regions2] + [f"is_{f}" for f in fam2],
        "E. same, Asia excluded  <- does any convention effect survive?")

    modes = sorted({r["mode"] for r in rows})[1:]
    MODE = [("mode", m) for m in modes]
    MODE_LAB = [f"mode_{m[:10]}" for m in modes]
    ols(rows, base + ["log_stations"] + REG + FAM + MODE,
        base_lab + ["log_stations"] + REG_LAB + FAM_LAB + MODE_LAB,
        "F. + network extent and mode  <- the specification to defend")

    usable = [r for r in rows if r["usable"]]
    if len(usable) > 40:
        regions3 = sorted({r["region"] for r in usable if r["region"] != BASE_REGION})
        fam3 = [f for f in fam_levels if sum(1 for r in usable if r["family"] == f) > 2]
        modes3 = sorted({r["mode"] for r in usable})[1:]
        ols(usable,
            base + ["log_stations"] + [("region", x) for x in regions3]
            + [("family", f) for f in fam3] + [("mode", m) for m in modes3],
            base_lab + ["log_stations"] + [f"reg_{x[:12]}" for x in regions3]
            + [f"is_{f}" for f in fam3] + [f"mode_{m[:10]}" for m in modes3],
            "G. spec F on the comparable subset only (usable_for_ratio)")

    # Axis 2 entered as dummies on the full sample. If the scope of the
    # numerator is doing work that spec F attributed to mode or convention,
    # it shows up here: metro_only is the base, so each coefficient is the
    # log-ridership gap from counting a metro alone.
    SCOPE_BASE = "metro_only"
    scopes = sorted({r["scope"] for r in rows
                     if r["scope"] != SCOPE_BASE and sum(1 for x in rows if x["scope"] == r["scope"]) > 2})
    if scopes:
        ols(rows, base + ["log_stations"] + REG + FAM + MODE + [("scope", sc) for sc in scopes],
            base_lab + ["log_stations"] + REG_LAB + FAM_LAB + MODE_LAB
            + [f"scope_{sc.replace('metro_plus_','+')[:14]}" for sc in scopes],
            f"H. + numerator mode scope (axis 2; {SCOPE_BASE} = base)")

    print("\n" + "=" * 74)
    print("LEAVE-ONE-REGION-OUT on the convention dummies (spec D)")
    print("=" * 74)
    for drop in [None] + sorted({r["region"] for r in rows}):
        sub = [r for r in rows if drop is None or r["region"] != drop]
        if len(sub) < 60:
            continue
        # Dropping the base region itself leaves the remaining dummies
        # collinear with the intercept. Re-base on the largest survivor rather
        # than skipping the row -- the assertion in ols() is what surfaced this.
        present = sorted({r["region"] for r in sub})
        local_base = BASE_REGION if BASE_REGION in present else Counter(
            r["region"] for r in sub).most_common(1)[0][0]
        regs = [x for x in present if x != local_base]
        fams = [f for f in fam_levels if sum(1 for r in sub if r["family"] == f) > 2]
        if not fams:
            continue
        terms = base + [("region", x) for x in regs] + [("family", f) for f in fams]
        labs = base_lab + [f"reg_{x[:12]}" for x in regs] + [f"is_{f}" for f in fams]
        try:
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                b = ols(sub, terms, labs, "x")
        except AssertionError as e:
            print(f"  drop {str(drop):16} skipped ({e})")
            continue
        bits = "  ".join(f"is_{f}={b.get(f'is_{f}', float('nan')):+.3f}" for f in fams)
        note = "" if local_base == BASE_REGION else f"  (base={local_base})"
        print(f"  {'FULL' if drop is None else 'drop ' + drop:24} n={len(sub):3}  {bits}{note}")

    print("\n" + "=" * 74)
    print("Read the ladder, not the last rung.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
