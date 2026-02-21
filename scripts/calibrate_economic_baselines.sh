#!/usr/bin/env bash
#
# Run economic opportunities (economic_security) pillar calibration.
# Builds data/economic_baselines.json from data/locations.csv.
#
# Usage (run from project root or from anywhere):
#   ./scripts/calibrate_economic_baselines.sh
#   bash scripts/calibrate_economic_baselines.sh
#
# Optional: limit locations or min-samples
#   ./scripts/calibrate_economic_baselines.sh --limit 40 --min-samples 5
#

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

INPUT="${INPUT:-data/locations.csv}"
OUTPUT="${OUTPUT:-data/economic_baselines.json}"

echo "Economic baselines calibration: $INPUT -> $OUTPUT"
echo "Project root: $ROOT"
echo ""

export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
exec python3 scripts/build_economic_baselines.py \
  --input "$INPUT" \
  --output "$OUTPUT" \
  --min-samples 5 \
  --sleep 0.1 \
  "$@"
