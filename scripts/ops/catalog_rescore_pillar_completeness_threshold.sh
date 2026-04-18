#!/usr/bin/env bash
# Rescore one pillar via prod API only where that pillar's completeness < TH, then recompute
# composites for NYC + LA merged JSONLs, commit/push, and print rows still below TH.
#
# Set HOMEFIT_API_BASE and HOMEFIT_PROXY_SECRET, then e.g.:
#   ./scripts/ops/catalog_rescore_pillar_completeness_threshold.sh
#   PILLAR=built_beauty TH=0.85 ./scripts/ops/catalog_rescore_pillar_completeness_threshold.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TH="${TH:-0.8}"
PILLAR="${PILLAR:-neighborhood_amenities}"

if [[ -z "${HOMEFIT_API_BASE:-}" || -z "${HOMEFIT_PROXY_SECRET:-}" ]]; then
  echo "Set HOMEFIT_API_BASE and HOMEFIT_PROXY_SECRET." >&2
  exit 1
fi

export PYTHONPATH="$ROOT"
export COMP_TH="$TH"
export PILLAR

echo "=== pillar=${PILLAR}  TH (completeness)=${TH} ==="

python3 scripts/catalog/rescore_catalog_pillar.py \
  --input data/nyc_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup \
  --pillars "$PILLAR" \
  --completeness-filter-lt "$TH" \
  --completeness-filter-pillar "$PILLAR" \
  --use-catalog-coordinates \
  --delay 2

python3 scripts/catalog/rescore_catalog_pillar.py \
  --input data/la_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup \
  --pillars "$PILLAR" \
  --completeness-filter-lt "$TH" \
  --completeness-filter-pillar "$PILLAR" \
  --use-catalog-coordinates \
  --delay 2

python3 scripts/catalog/recompute_catalog_composites.py \
  --input data/nyc_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup

python3 scripts/catalog/recompute_catalog_composites.py \
  --input data/la_metro_place_catalog_scores_merged.jsonl \
  --in-place --no-backup

git add data/nyc_metro_place_catalog_scores_merged.jsonl data/la_metro_place_catalog_scores_merged.jsonl
git commit -m "Rescore ${PILLAR} where completeness < ${TH}; refresh composites"

git push origin main

echo ""
echo "=== Still below ${TH} ${PILLAR} completeness (should be empty if all cleared) ==="
python3 -c "
import json, os
TH = float(os.environ['COMP_TH'])
pillar = os.environ['PILLAR']
for path, lab in [
  ('data/nyc_metro_place_catalog_scores_merged.jsonl', 'NYC'),
  ('data/la_metro_place_catalog_scores_merged.jsonl', 'LA'),
]:
  for line in open(path):
    line = line.strip()
    if not line:
      continue
    o = json.loads(line)
    if not o.get('success'):
      continue
    p = (o.get('score') or {}).get('livability_pillars', {}).get(pillar) or {}
    dq = p.get('data_quality') or {}
    c = dq.get('completeness')
    try:
      cf = float(c) if c is not None else None
    except (TypeError, ValueError):
      cf = None
    if cf is not None and cf >= TH:
      continue
    cat = o.get('catalog') or {}
    print(lab, (cat.get('search_query') or cat.get('name') or '?'), 'completeness=', cf)
"
