#!/usr/bin/env bash
# Re-fetch pillar scores from production API into the canonical merged JSONLs, then refresh
# composite indices (longevity / status / happiness) in place — no timestamped .bak files.
#
# Requires:
#   export HOMEFIT_API_BASE="https://your-service.up.railway.app"
#   export HOMEFIT_PROXY_SECRET="..."
# Optional: HOMEFIT_REFRESH_PILLARS (default: neighborhood_amenities)
# Optional: .env at repo root (loaded by Python scripts)
#
# Usage:
#   cd /path/to/home-fit && ./scripts/refresh_merged_catalog_from_prod.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${HOMEFIT_API_BASE:-}" || -z "${HOMEFIT_PROXY_SECRET:-}" ]]; then
  echo "Set HOMEFIT_API_BASE and HOMEFIT_PROXY_SECRET first." >&2
  exit 1
fi

PILLARS="${HOMEFIT_REFRESH_PILLARS:-neighborhood_amenities}"

export PYTHONPATH="$ROOT"

echo "== NYC: rescore ($PILLARS), all rows, catalog coordinates =="
python3 scripts/rescore_catalog_pillar.py \
  --input data/nyc_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup \
  --pillars "$PILLARS" \
  --use-catalog-coordinates \
  --delay 2

echo "== LA: rescore ($PILLARS), all rows, catalog coordinates =="
python3 scripts/rescore_catalog_pillar.py \
  --input data/la_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup \
  --pillars "$PILLARS" \
  --use-catalog-coordinates \
  --delay 2

echo "== NYC: recompute composites in place =="
python3 scripts/recompute_catalog_composites.py \
  --input data/nyc_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup

echo "== LA: recompute composites in place =="
python3 scripts/recompute_catalog_composites.py \
  --input data/la_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup

echo "Done. Commit data/nyc_metro_place_catalog_scores_merged.jsonl and data/la_metro_place_catalog_scores_merged.jsonl when satisfied."
