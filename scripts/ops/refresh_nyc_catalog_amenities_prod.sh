#!/usr/bin/env bash
# Refresh NYC merged catalog neighborhood_amenities from production /score (same as manual curl).
# Requires HOMEFIT_PROXY_SECRET (e.g. in repo root .env — gitignored).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env" 2>/dev/null || true
  set +a
fi
export HOMEFIT_API_BASE="${HOMEFIT_API_BASE:-https://home-fit-production.up.railway.app}"
if [[ -z "${HOMEFIT_PROXY_SECRET:-}" ]]; then
  echo "Set HOMEFIT_PROXY_SECRET (e.g. add to $ROOT/.env from Railway Variables)." >&2
  exit 1
fi
export PYTHONPATH=.
python3 scripts/catalog/rescore_catalog_pillar.py \
  --input data/nyc_metro_place_catalog_scores_merged.jsonl \
  --in-place \
  --pillars neighborhood_amenities \
  --use-catalog-coordinates \
  --confidence-filter-pillar neighborhood_amenities \
  --confidence-filter-lt 85 \
  --base-url "$HOMEFIT_API_BASE"
python3 scripts/catalog/recompute_catalog_composites.py \
  --input data/nyc_metro_place_catalog_scores_merged.jsonl \
  --in-place
echo "Done. Verify Rye: python3 -c \"import json;[print(json.loads(l)['score']['livability_pillars']['neighborhood_amenities'].get('score')) for l in open('data/nyc_metro_place_catalog_scores_merged.jsonl') if json.loads(l).get('catalog',{}).get('name')=='Rye']\""
