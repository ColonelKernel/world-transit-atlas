#!/usr/bin/env bash
# Fill any city that is still missing line geometry from OpenStreetMap, then rebuild the map.
#
# The gap list is computed from data/networks/*.json rather than hardcoded, so this stays
# correct as coverage changes: a city is "incomplete" if its file is missing, has no lines,
# or has no stations.
set -euo pipefail
cd "$(dirname "$0")"

GAPS=$(python3 - <<'PY'
import json, glob, os
gaps = []
for f in sorted(glob.glob("data/networks/*.json")):
    slug = os.path.basename(f)[:-5]
    try:
        d = json.load(open(f))
    except Exception:
        gaps.append(slug); continue
    if not d.get("lines") or not d.get("stations"):
        gaps.append(slug)
print(",".join(gaps))
PY
)

if [ -z "$GAPS" ]; then
  echo "Every city already has line + station geometry — nothing to fetch."
  echo "Rebuilding index.html anyway..."
else
  echo "Incomplete cities: $(echo "$GAPS" | tr ',' '\n' | wc -l | tr -d ' ')"
  echo "$GAPS" | tr ',' '\n' | sed 's/^/  /'
  echo
  echo "Fetching real line+station geometry from OpenStreetMap..."
  python3 tools/fetch_networks_osm.py --only "$GAPS"
fi

echo "Rebuilding index.html..."
python3 tools/tm_gen.py
echo "Done. Open index.html."
