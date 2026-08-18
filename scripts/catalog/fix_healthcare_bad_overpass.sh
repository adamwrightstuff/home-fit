#!/usr/bin/env bash
# Fix 23 NYC catalog places where the healthcare Overpass query returned junk
# (hospital_count <= 3 or nearest_hospital_km > 5 in urban/suburban areas).
# Run on Railway where Overpass is accessible.
set -e

NAMES="Rockaway Beach,South Orange,Peekskill,Ozone Park,Mount Vernon,Stapleton,Fort Greene,Morristown,Mount Kisco,SoHo,Rye,Oceanside,Cedarhurst,Tottenville,Long Beach,Midtown East,Pleasantville,Gowanus,Bellmore,Ossining,Merrick,Madison,Great Kills"

CATALOG="data/nyc_metro_place_catalog_scores_merged.jsonl"

echo "=== Step 1: rescore healthcare_access for affected places ==="
PYTHONPATH=. python3 scripts/catalog/rescore_pillar_direct.py \
  --input "$CATALOG" \
  --pillar healthcare_access \
  --names "$NAMES" \
  --in-place

echo ""
echo "=== Step 2: recompute composites ==="
PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \
  --input "$CATALOG" \
  --in-place \
  --no-backup

echo ""
echo "Done. Commit and push the updated catalog."
