#!/usr/bin/env bash
# Build a private Overpass server for the 14 states HomeFit scores. Run ON the rented server, as root.
# Untested end to end: check each step's output the first time. See docs/PRIVATE_OVERPASS.md.
set -euo pipefail

WORK=/srv/overpass
STATES=(new-york new-jersey connecticut california washington texas illinois indiana pennsylvania delaware maryland colorado arizona nevada)
BASE=https://download.geofabrik.de/north-america/us

apt-get update
apt-get install -y docker.io osmium-tool curl

mkdir -p "$WORK/extracts" "$WORK/db"
cd "$WORK/extracts"
for s in "${STATES[@]}"; do
  [ -s "$s-latest.osm.pbf" ] || curl -fL -O "$BASE/$s-latest.osm.pbf"
done

# state extracts overlap slightly at borders; merge de-duplicates by object ID
osmium merge ./*-latest.osm.pbf -o "$WORK/homefit.osm.pbf" --overwrite
# the Overpass image reads .osm.bz2
osmium cat "$WORK/homefit.osm.pbf" -o "$WORK/homefit.osm.bz2" --overwrite

# first run loads the data (a few hours), then the container stops; start it again to serve
docker rm -f overpass 2>/dev/null || true
docker run -d --name overpass \
  -e OVERPASS_MODE=init \
  -e OVERPASS_PLANET_URL=file:///import/homefit.osm.bz2 \
  -e OVERPASS_META=no \
  -e OVERPASS_RULES_LOAD=10 \
  -e OVERPASS_ALLOW_DUPLICATE_QUERIES=yes \
  -v "$WORK/db":/db \
  -v "$WORK":/import:ro \
  -p 127.0.0.1:12345:80 \
  wiktorn/overpass-api

echo "Import started. Watch with: docker logs -f overpass"
echo "When it says the import is done and the container has stopped, run: docker start overpass"
