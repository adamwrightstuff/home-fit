#!/usr/bin/env python3
"""
Triage SF emergency_services rescore: keep improvements, revert regressions to backup.
Overpass was still down for 44/50 places, causing major declines. Only 6 places
where Overpass partially succeeded should be kept.
"""
import json
from pathlib import Path

BACKUP = Path("data/sf_metro_place_catalog_scores_merged.bak.20260904-084006")
MERGED = Path("data/sf_metro_place_catalog_scores_merged.jsonl")

def place_name(row):
    return (row.get("catalog", {}) or {}).get("name") or row.get("name", "")

backup = {}
with open(BACKUP) as f:
    for line in f:
        row = json.loads(line)
        backup[place_name(row)] = row

current = {}
with open(MERGED) as f:
    for line in f:
        row = json.loads(line)
        current[place_name(row)] = row

def hc_score(row):
    return ((row.get("score", {}).get("livability_pillars", {}) or {}).get("healthcare_access", {}) or {}).get("score", 0) or 0

kept = reverted = unchanged = 0
result_lines = []

for name, bak_row in backup.items():  # noqa: E501
    cur_row = current.get(name)
    if cur_row is None:
        result_lines.append(bak_row)
        continue

    bak_sc = hc_score(bak_row)
    cur_sc = hc_score(cur_row)

    if cur_sc > bak_sc:
        result_lines.append(cur_row)
        kept += 1
        print(f"  KEEP  {name}: {bak_sc:.1f} → {cur_sc:.1f} (+{cur_sc - bak_sc:.1f})")
    elif cur_sc == bak_sc:
        result_lines.append(bak_row)
        unchanged += 1
    else:
        result_lines.append(bak_row)
        reverted += 1
        print(f"  REVERT {name}: {cur_sc:.1f} → {bak_sc:.1f} (saved {bak_sc - cur_sc:.1f})")

print(f"\nKept {kept} improvements, reverted {reverted} regressions, {unchanged} unchanged")

with open(MERGED, "w") as f:
    for row in result_lines:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
print(f"Wrote {len(result_lines)} lines to {MERGED}")
