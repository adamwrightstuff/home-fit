#!/usr/bin/env bash
# Add states to the private Overpass server WITHOUT touching the running one: builds a second database
# (/srv/overpass/db2, container "overpass2", port 12346) from the existing extracts plus the new states.
# When it finishes and answers queries, point the tunnel at 12346. Run ON the server, as root. See docs/PRIVATE_OVERPASS.md.
set -euo pipefail

WORK=/srv/overpass
OLD=(new-york new-jersey connecticut california washington texas illinois indiana pennsylvania delaware maryland)
NEW=(arizona nevada florida north-carolina georgia massachusetts colorado)
BASE=https://download.geofabrik.de/north-america/us

mkdir -p "$WORK/extracts" "$WORK/db2"
cd "$WORK/extracts"
for s in "${OLD[@]}" "${NEW[@]}"; do
  [ -s "$s-latest.osm.pbf" ] || curl -fL -O "$BASE/$s-latest.osm.pbf"
done

PBFS=()
for s in "${OLD[@]}" "${NEW[@]}"; do PBFS+=("$s-latest.osm.pbf"); done
osmium merge "${PBFS[@]}" -o "$WORK/homefit2.osm.pbf" --overwrite
osmium cat "$WORK/homefit2.osm.pbf" -o "$WORK/homefit2.osm.bz2" --overwrite

docker rm -f overpass2 2>/dev/null || true
docker run -d --name overpass2 \
  -e OVERPASS_MODE=init \
  -e OVERPASS_PLANET_URL=file:///import/homefit2.osm.bz2 \
  -e OVERPASS_META=no \
  -e OVERPASS_RULES_LOAD=10 \
  -e OVERPASS_ALLOW_DUPLICATE_QUERIES=yes \
  -v "$WORK/db2":/db \
  -v "$WORK":/import:ro \
  -p 127.0.0.1:12346:80 \
  wiktorn/overpass-api

echo "Import started. Watch: docker logs -f overpass2"
echo "When it says initialization complete and the container stops: docker start overpass2"
