#!/usr/bin/env bash
# Debug status_signal from production. Requires HOMEFIT_PROXY_SECRET (from Railway Variables).
# Usage: HOMEFIT_PROXY_SECRET=your_secret ./scripts/debug_production_status_signal.sh
#        Or: export HOMEFIT_PROXY_SECRET=your_secret && ./scripts/debug_production_status_signal.sh

BASE="${HOMEFIT_BASE_URL:-https://home-fit-production.up.railway.app}"
SECRET="${HOMEFIT_PROXY_SECRET:-}"

echo "=== healthz ==="
curl -s "${BASE}/healthz" | jq .

if [[ -z "$SECRET" ]]; then
  echo ""
  echo "Set HOMEFIT_PROXY_SECRET to call /score (e.g. export HOMEFIT_PROXY_SECRET=your_secret)"
  exit 0
fi

echo ""
echo "=== score for 20 Moore St (status_signal + breakdown only) ==="
curl -s "${BASE}/score?location=20%20Moore%20St%2C%20New%20York%20NY" \
  -H "X-HomeFit-Proxy-Secret: ${SECRET}" | jq '{ status_signal, status_signal_breakdown }'
