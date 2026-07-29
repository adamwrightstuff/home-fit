#!/usr/bin/env bash
# Daily SchoolDigger cache pre-warm for SF catalog.
# Spins up the local API, rescores 7 places, kills API.
# Stays under the 20 hit/day Developer quota (each place ~2-3 hits).
# Run: cron fires daily at 9am. After ~16 days the full catalog is cached.

set -euo pipefail

REPO=/Users/adamwright/Dev/home-fit
LOG="$REPO/logs/school_cron.log"
CATALOG="$REPO/data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
PORT=8099

mkdir -p "$REPO/logs"
echo "--- $(date) ---" >> "$LOG"

# Load .env
set -a
# shellcheck source=/dev/null
source "$REPO/.env"
set +a

# Start API on a dedicated port (avoid colliding with dev server)
PYTHONPATH="$REPO" \
ENABLE_SCHOOL_SCORING=true \
SCHOOLDIGGER_QUOTA_WARNING_THRESHOLD=15 \
  python3 -m uvicorn main:app \
    --host 127.0.0.1 --port $PORT \
    --log-level warning >> "$LOG" 2>&1 &
API_PID=$!
trap "kill $API_PID 2>/dev/null || true" EXIT

# Wait for API to be ready (up to 30s)
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/health" > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

PYTHONPATH="$REPO" python3 "$REPO/scripts/catalog/rescore_catalog_pillar.py" \
  --input "$CATALOG" \
  --pillars quality_education \
  --base-url "http://127.0.0.1:$PORT" \
  --max-places 7 \
  --use-catalog-coordinates \
  --confidence-filter-lt 50 \
  --confidence-filter-pillar quality_education \
  --in-place \
  --no-backup >> "$LOG" 2>&1

echo "Done $(date)" >> "$LOG"
