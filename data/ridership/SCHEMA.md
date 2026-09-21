# Transit Ridership Dataset — Canonical Schema & Standardization Rules

Goal: one tidy, **standardized** long-format table covering all 201 systems, largest first,
so a dashboard and a sonification can treat every system on common footing despite the fact
that agencies publish wildly different things.

## The core tidy table — `ridership_long.csv`

One row = one (system, metric, period).

| column | type | notes |
|---|---|---|
| `system_id` | string | our slug, joins to the map/link index (e.g. `shanghai`) |
| `city` | string | |
| `country` | string | |
| `region` | string | our 7-region scheme |
| `metric` | enum | `ridership` \| `service_trips` \| `service_car_km` \| `punctuality_pct` \| `revenue` |
| `period_start` | date (ISO 8601) | first day of the period |
| `granularity` | enum | `daily` \| `monthly` \| `annual` |
| `value` | number | raw value **in the source's own definition/unit** |
| `unit` | enum | `passengers` \| `trips` \| `car_km` \| `percent` \| `local_currency` |
| `measure_def` | enum | how ridership is counted — see below. Blank for non-ridership metrics. |
| `daily_equiv` | number | **derived, standardized**: value expressed as average passengers/day for the period (see rules). Enables cross-system + cross-granularity comparison and sonification. |
| `source_id` | string | FK to `sources` table |
| `is_estimate` | bool | true if `daily_equiv` was derived rather than reported |

## The `sources` table — `sources.csv`

| column | notes |
|---|---|
| `source_id` | short key |
| `system_id` | |
| `publisher` | agency / portal / aggregator name |
| `url` | direct link (dataset/API/report) |
| `access` | `open_csv` \| `api` \| `xlsx` \| `pdf` \| `webpage` \| `aggregator` |
| `granularity` | best granularity this source offers |
| `metric` | what it covers |
| `measure_def` | ridership counting basis |
| `coverage_start` / `coverage_end` | period the source spans |
| `tier` | `official` \| `national_db` \| `community/aggregator` |
| `retrieved` | date we captured it |
| `notes` | caveats, definition quirks, license |

## `measure_def` — the standardization crux for ridership

Agencies do NOT count the same thing. We record the source's basis explicitly so the dashboard
can compare like-with-like and flag mismatches:

- `station_entries` — taps/entries at faregates (most Asian metros, TfL "entries & exits"/2)
- `unlinked_trips` — boardings incl. transfers (US NTD "UPT")
- `linked_journeys` — one trip end-to-end regardless of transfers (many EU operators)
- `passenger_journeys` — operator's headline "journeys" figure
- `estimated` — modeled/derived

We do NOT silently convert between these. Cross-def comparisons in the dashboard get a visible
"definition differs" marker. Where an operator publishes a transfer/linking factor we note it.

## `mode_scope` — what modes the numerator covers (axis 2)

A counting convention says *how* a rider is counted; `mode_scope` says *who gets
counted at all*. Folding an S-Bahn or a bus network into the figure does not add
noise to trips-per-capita, it adds scale — Prague's headline 1,104,935,520 is the
whole integrated network and is ~2.9x the metro's ~379M.

| value | the numerator covers |
|---|---|
| `metro_only` | one or more heavy-rail metro operators, nothing else |
| `tram_or_lrt_only` | the system is itself a tram / light-rail network |
| `metro_plus_urban_rail` | metro + tram / LRT / monorail / people-mover, still all urban |
| `metro_plus_regional_rail` | adds S-Bahn / RER / commuter / mainline rail |
| `multimodal_agency` | includes bus, i.e. the operator's whole network |
| `unknown` | not established from the citation on file |

Derived in `tools/mode_scope.py` from the scope qualifier `system_rank.system`
pairs with each figure ("Metro de Paris (+ RER, tram)", "U-Bahn + S-Bahn
Hamburg"). That is the dataset author's annotation, not a re-reading of each
agency's report, so every derived value is stamped `system_field` and a value
checked against the publisher is stamped `override:<source>`. The two-tier
scheme is the same one `measure_def` already uses.

`data/ridership/mode_scope_overrides.csv` holds the reviewed rows, each with its
quote and URL. **A reviewed row may widen a scope the system string understates**
— Vienna's "U-Bahn + Strassenbahn Wien" is in fact all of Wiener Linien
including bus — **and may reduce it to `unknown`** when the cited source does not
support the stored value, which is what happened to Berlin and Munich.

Comparable numerators are urban rail and nothing else
(`metro_only`, `tram_or_lrt_only`, `metro_plus_urban_rail`); `usable_for_ratio`
requires it.

## `daily_equiv` derivation rules (standardized, reversible, labeled)

- daily source → `daily_equiv = value` (is_estimate=false)
- monthly source → `daily_equiv = value / days_in_month(period)` (is_estimate=true)
- annual source → `daily_equiv = value / days_in_year(period)` (is_estimate=true)

`daily_equiv` is a comparability aid, NOT a claim of true daily detail. The raw `value` +
`granularity` are always kept so nothing is lost and every number is traceable to its source.

## Priority / ordering

Systems processed **largest first** by latest annual ridership (`system_rank.csv`). Ranking is
itself the first standardized metric we collect (annual ridership, with year + measure_def).

## Non-negotiables

- Never fabricate a number or a URL. Missing = blank + a note.
- Every value traces to exactly one `source_id`.
- Timezone: period_start is the local calendar date the agency assigns.
- Revenue kept in local currency + a separate note; no FX conversion in the base table.
