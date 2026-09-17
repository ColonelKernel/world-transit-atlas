#!/usr/bin/env bash
# Fill the remaining line-less cities from OpenStreetMap and rebuild the map.
# RUN THIS IN YOUR OWN TERMINAL (Terminal.app) — it needs open internet (Overpass).
set -e
cd "$(dirname "$0")"
echo "Fetching real line+station geometry for the remaining cities from OpenStreetMap..."
python3 tools/fetch_networks_osm.py --only "antwerp,athens,berlin,casablanca,cologne,copenhagen,dresden,dusseldorf,frankfurt,glasgow,hamburg,hanover,karlsruhe,kochi,kolkata,krakow,lagos,leipzig,lyon,marseille,melbourne,munich,newcastle,nuremberg,porto-alegre,rotterdam,santo-domingo,seoul,shiraz,tashkent,the-hague,thessaloniki,tunis,zagreb"
echo "Rebuilding index.html..."
python3 tools/tm_gen.py
echo "Done. Open index.html — the previously line-less cities now draw their lines."
