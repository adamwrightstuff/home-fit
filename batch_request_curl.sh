#!/bin/bash
# Batch request for locations with schools disabled
# Usage: ./batch_request_curl.sh [API_URL]
# Default API_URL: https://home-fit-production.up.railway.app

API_URL="${1:-https://home-fit-production.up.railway.app}"

curl -X POST "${API_URL}/batch" \
  -H "Content-Type: application/json" \
  -d '{
  "locations": [
    "Hudson OH",
    "Hyde Park Chicago IL",
    "Inner Harbor Baltimore MD",
    "Irvine CA",
    "Jackson WY",
    "Kiawah Island SC",
    "Lake Placid NY"
  ],
  "enable_schools": false,
  "include_chains": true,
  "adaptive_delays": true
}'
