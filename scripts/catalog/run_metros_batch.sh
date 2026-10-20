#!/usr/bin/env bash
# Score several metros back to back with the private Overpass server, one `metro_agent run` each, logging per metro.
# A failure in one metro does not stop the next. Archetype summaries are skipped (ANTHROPIC_API_KEY empty).
#
#   OVERPASS_URL=http://localhost:12346/api/interpreter bash scripts/catalog/run_metros_batch.sh phoenix san_antonio ...
#
# Education, the education weight, crime agency mapping and gap acceptance are done after the batch (they need no Overpass).
set -u
cd "$(dirname "$0")/../.."
source .venv/bin/activate
export PYTHONPATH=. HOMEFIT_TRANSIT_STABLE_COMMUTE=true ANTHROPIC_API_KEY=
LOGDIR="${LOGDIR:-/tmp/metro_batch_logs}"; mkdir -p "$LOGDIR"
for m in "$@"; do
  echo "$(date +%H:%M:%S) START $m" | tee -a "$LOGDIR/batch.log"
  python -u -m scripts.metro_agent run --metro "$m" > "$LOGDIR/$m.log" 2>&1
  echo "$(date +%H:%M:%S) END   $m (exit $?)" | tee -a "$LOGDIR/batch.log"
done
echo "$(date +%H:%M:%S) BATCH DONE" | tee -a "$LOGDIR/batch.log"
