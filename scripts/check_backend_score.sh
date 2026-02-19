#!/usr/bin/env bash
# Backend score job check: create job, poll until done, print total_score and pillar scores.
# Copy-paste this one line into terminal (no other typing):
#   cd /Users/adamwright/home-fit && ./scripts/check_backend_score.sh
# Or from project root: ./scripts/check_backend_score.sh
# Loads .env from project root if present (RAILWAY_API_BASE_URL, HOMEFIT_PROXY_SECRET).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env" 2>/dev/null || true
  set +a
fi
BASE="${RAILWAY_API_BASE_URL:-${BACKEND_URL:-https://home-fit-production.up.railway.app}}"
SECRET="${HOMEFIT_PROXY_SECRET:-${PROXY_SECRET:-}}"
LOCATION="${1:-Seattle}"
MAX_POLL=60
POLL_DELAY=2

echo "=== Backend score check ==="
echo "BASE=$BASE LOCATION=$LOCATION"

# Create job (POST)
echo ""
echo "Creating job..."
if [[ -n "$SECRET" ]]; then
  CREATE_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/score/jobs?location=$(printf %s "$LOCATION" | jq -sRr @uri)" -H "Accept: application/json" -H "X-HomeFit-Proxy-Secret: $SECRET")
else
  CREATE_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/score/jobs?location=$(printf %s "$LOCATION" | jq -sRr @uri)" -H "Accept: application/json")
fi
CREATE_BODY=$(echo "$CREATE_RESP" | sed '$d')
CREATE_CODE=$(echo "$CREATE_RESP" | tail -n 1)
echo "POST /score/jobs → HTTP $CREATE_CODE"
echo "$CREATE_BODY" | jq . 2>/dev/null || echo "$CREATE_BODY"

JOB_ID=$(echo "$CREATE_BODY" | jq -r '.job_id // empty')
if [[ -z "$JOB_ID" ]]; then
  echo "No job_id in response. Exiting."
  exit 1
fi
echo "job_id=$JOB_ID"
echo ""

# Poll until done
for i in $(seq 1 "$MAX_POLL"); do
  sleep "$POLL_DELAY"
  if [[ -n "$SECRET" ]]; then
    POLL_RESP=$(curl -s "$BASE/score/jobs/$JOB_ID" -H "Accept: application/json" -H "X-HomeFit-Proxy-Secret: $SECRET")
  else
    POLL_RESP=$(curl -s "$BASE/score/jobs/$JOB_ID" -H "Accept: application/json")
  fi
  STATUS=$(echo "$POLL_RESP" | jq -r '.status // "unknown"')
  echo "Poll $i: status=$STATUS"

  if [[ "$STATUS" == "done" ]]; then
    echo ""
    echo "=== Result ==="
    TOTAL=$(echo "$POLL_RESP" | jq -r '.result.total_score // "missing"')
    echo "total_score: $TOTAL"
    echo ""
    echo "Pillar scores:"
    echo "$POLL_RESP" | jq -r '.result.livability_pillars | to_entries[] | "  \(.key): \(.value.score)"' 2>/dev/null || echo "  (no livability_pillars or jq failed)"
    echo ""
    echo "Full result keys:"
    echo "$POLL_RESP" | jq -r '.result | keys' 2>/dev/null
    exit 0
  fi
  if [[ "$STATUS" == "error" ]]; then
    echo "Job failed: $(echo "$POLL_RESP" | jq -r '.error // .detail // "unknown"')"
    exit 1
  fi
done

echo "Timed out after ${MAX_POLL} polls."
exit 1
