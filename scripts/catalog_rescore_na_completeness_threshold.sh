#!/usr/bin/env bash
# Deprecated: use catalog_rescore_pillar_completeness_threshold.sh (same behavior; default PILLAR=neighborhood_amenities).
exec "$(cd "$(dirname "$0")" && pwd)/catalog_rescore_pillar_completeness_threshold.sh" "$@"
