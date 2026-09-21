#!/usr/bin/env python3
"""
Axis 2 of the comparability audit: what MODES the ridership numerator covers.

comparability.py grades four axes and has only ever graded three. The second --
"NUMERATOR MODE SCOPE -- metro only, metro+tram, or the whole multimodal agency
including bus" -- was left as two blank columns with the comment "recorded
nowhere ... blank is honest; a guess is not". This module fills them without
turning the blank into a guess.

WHERE THE EVIDENCE COMES FROM. system_rank.csv pairs every annual_riders figure
with a `system` string that names what the figure covers, and 51 of the 201
carry an explicit scope qualifier: "Metro de Paris (+ RER, tram)", "U-Bahn +
S-Bahn Hamburg", "Melbourne trams (+ Metro Trains network)". That parenthetical
is an assertion about the numerator, written next to the number it describes,
and it is the only mode-scope evidence already in the repo.

WHAT THAT EVIDENCE IS AND IS NOT. It is the dataset author's annotation, not a
re-reading of each agency's report, so every value derived here is stamped
`system_field` rather than `verified`. That distinction is the whole point:
comparability.py already separates "system_rank" from "override:<source>" for
measure_def, and axis 2 uses the identical two-tier scheme. Where a figure has
actually been checked against the publisher, the reviewed row in
mode_scope_overrides.csv wins and carries its evidence and URL.

WHY IT MATTERS. Including an S-Bahn or a bus network in the numerator does not
add noise to trips_per_capita, it adds scale: Hamburg and Munich publish
U-Bahn+S-Bahn together, Vienna's headline covers all of Wiener Linien, and all
three sit at the top of the table. Grading axis 2 is what lets the ratio be
restricted to numerators that count the same kind of thing.
"""

from __future__ import annotations

import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OVERRIDES = os.path.join(ROOT, "data", "ridership", "mode_scope_overrides.csv")

# The enum. Ordered from narrowest numerator to widest.
ENUM = (
    "metro_only",                # one or more heavy-rail metro operators, nothing else
    "tram_or_lrt_only",          # the system IS a tram/light-rail network
    "metro_plus_urban_rail",     # metro + tram/LRT/monorail/people-mover, still all urban
    "metro_plus_regional_rail",  # adds S-Bahn / RER / commuter / mainline rail
    "multimodal_agency",         # includes bus, i.e. the operator's whole network
    "unknown",
)

# Numerators that count only urban rail, no mainline and no bus. These are the
# scopes that can sit in one cross-city ratio without the numerator changing
# meaning underneath it. metro_only and tram_or_lrt_only still describe
# different systems; that is what the stricter metro-only stratum is for.
URBAN_RAIL_SCOPES = ("metro_only", "tram_or_lrt_only", "metro_plus_urban_rail")


class UnclassifiedScope(ValueError):
    """Raised rather than defaulting to 'unknown'.

    comparability.py's UnmappableMeasure exists for the same reason: a silent
    fall-through is how an empty group became a plausible-looking regression.
    An unmatched system string is a gap in this table, not a fact about the
    city.
    """


# Mainline / commuter / regional rail folded into a metro figure. Matched as
# whole tokens because "Rail" alone is a metro brand name across China
# ("Chongqing Rail Transit" is a metro, not a commuter railway).
REGIONAL_RAIL = (
    r"S-Bahn",
    r"\bRER\b",
    r"\bCPTM\b",
    r"\bMarmaray\b",
    r"\bKTM\b",
    r"\bSRT\b",
    r"\bARL\b",
    r"Sydney Trains",
    r"Metro Trains",
    r"KRL Commuterline",
    r"\bMCD\b",
    r"\bREM\b",
    r"İZBAN|IZBAN",
    r"Overground",
    r"Elizabeth line",
    r"RandstadRail",
)

# Other urban rail added to a metro figure: trams, light rail, monorail,
# people-movers, funiculars, cable. All stay inside the city.
URBAN_RAIL_ADDED = (
    r"\btrams?\b",
    r"Straßenbahn|Strassenbahn",
    r"Light Rail|\bLRT\b",
    r"Monorail",
    r"Metromover",
    r"Metrocable|Tranvía",
    r"Ankaray",
    r"funicular|funiculaire|funiculars",
    r"premetro",
)

# Explicit whole-agency markers in the system string itself. Wider cases are
# caught by the reviewed overrides file, not guessed at here.
MULTIMODAL = (
    r"Busway",
    r"\bbus\b",
)


def _load_overrides() -> dict[str, dict]:
    if not os.path.exists(OVERRIDES):
        return {}
    with open(OVERRIDES, newline="", encoding="utf-8") as fh:
        return {r["slug"]: r for r in csv.DictReader(fh) if r.get("slug")}


def _any(patterns, text) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def classify(system: str, mode: str) -> str:
    """-> a value from ENUM, derived from the system string and the mode column.

    Order matters and runs widest-first: a figure that bundles an S-Bahn *and*
    a tram is a regional-rail-scope figure, so the regional test has to beat the
    tram test. "Metro de Paris (+ RER, tram)" matches both and is the reason.
    """
    text = (system or "").strip()
    m = (mode or "").strip().lower()

    if not text:
        return "unknown"
    if _any(MULTIMODAL, text):
        return "multimodal_agency"
    if _any(REGIONAL_RAIL, text):
        return "metro_plus_regional_rail"
    if _any(URBAN_RAIL_ADDED, text):
        # A tram network described only as a tram network is tram-only; the
        # same words next to a metro mean the metro figure has tram added.
        if m in ("tram", "lrt") and not re.search(r"metro|u-bahn|subway|\bMRT\b", text, re.I):
            return "tram_or_lrt_only"
        return "metro_plus_urban_rail"
    if m in ("tram", "lrt"):
        return "tram_or_lrt_only"
    if m.startswith("metro"):
        return "metro_only"
    raise UnclassifiedScope(
        f"{system!r} (mode={mode!r}) matches no rule in mode_scope.py. "
        f"Add a rule or a reviewed override -- do not let it default."
    )


def resolve(slug: str, system: str, mode: str) -> tuple[str, str, str, str]:
    """-> (scope, basis, evidence, url).

    A reviewed override beats the derived value, including when it widens the
    scope the system string understates.
    """
    ov = _load_overrides().get(slug)
    if ov and ov.get("mode_scope"):
        return (ov["mode_scope"], f"override:{ov.get('source','review')}",
                ov.get("evidence", ""), ov.get("url", ""))
    return classify(system, mode), "system_field", "", ""


def is_urban_rail(scope: str) -> bool:
    """True when the numerator counts urban rail only -- no mainline, no bus."""
    return scope in URBAN_RAIL_SCOPES


if __name__ == "__main__":
    import collections
    rank_path = os.path.join(ROOT, "data", "ridership", "system_rank.csv")
    with open(rank_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    counts = collections.Counter()
    for r in rows:
        scope, basis, _, _ = resolve(r["system_id"], r["system"], r["mode"])
        counts[(scope, basis)] += 1
    print(f"{len(rows)} systems\n")
    for (scope, basis), n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {scope:26} {basis:22} {n:3}")
