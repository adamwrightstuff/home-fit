#!/usr/bin/env python3
"""
Add political_lean data to catalog JSONL entries.

Calls the lookup module directly (no API needed — reads local precinct JSON files).
Stores raw lean values in breakdown; score is null because it's preference-dependent.
agent_recommend.py computes the directional score at query time.

Usage:
    PYTHONPATH=. python3 scripts/catalog/rescore_political_lean.py \\
        --input data/nyc_metro_place_catalog_scores_merged.jsonl --in-place

    PYTHONPATH=. python3 scripts/catalog/rescore_political_lean.py \\
        --input data/la_metro_place_catalog_scores_merged.jsonl --in-place
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pillars.political_lean import get_political_lean_score


def _backup_path(input_path: Path) -> Path:
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return input_path.with_suffix(f".jsonl.bak.{ts}")


def process_catalog(input_path: Path, in_place: bool, no_backup: bool, dry_run: bool) -> None:
    lines = input_path.read_text(encoding="utf-8").splitlines()
    out_lines = []
    hit = miss = skip = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            out_lines.append(line)
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue

        cat = obj.get("catalog") or {}
        score = obj.get("score") or {}
        lat_raw = cat.get("lat")
        lon_raw = cat.get("lon")
        state = cat.get("state_abbr") or (score.get("location_info") or {}).get("state")

        try:
            lat, lon = float(lat_raw), float(lon_raw)
        except (TypeError, ValueError):
            skip += 1
            out_lines.append(line)
            continue

        if not state:
            skip += 1
            out_lines.append(line)
            continue

        score_val, details = get_political_lean_score(lat, lon, state_abbr=state)

        pillar_entry: Dict[str, Any] = {
            "score": score_val,
            "weight": 0,
            "contribution": 0.0,
            "breakdown": details.get("breakdown", {}),
            "data_quality": details.get("data_quality", {}),
        }
        if details.get("error"):
            pillar_entry["status"] = "failed"
            pillar_entry["error"] = details["error"]
            miss += 1
        else:
            hit += 1

        liv = score.setdefault("livability_pillars", {})
        liv["political_lean"] = pillar_entry
        obj["score"] = score
        out_lines.append(json.dumps(obj, ensure_ascii=False))

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(lines)} — hit={hit} miss={miss} skip={skip}")

    print(f"\nDone: {hit} scored, {miss} no-data, {skip} skipped")

    if dry_run:
        print("Dry run — not writing output.")
        return

    if in_place:
        if not no_backup:
            bp = _backup_path(input_path)
            shutil.copy2(input_path, bp)
            print(f"Backup: {bp}")
        input_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"Updated in-place: {input_path}")
    else:
        out_path = input_path.with_suffix(".political_lean.jsonl")
        out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"Written: {out_path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Catalog JSONL path")
    p.add_argument("--in-place", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = REPO_ROOT / input_path
    if not input_path.is_file():
        print(f"File not found: {input_path}")
        sys.exit(1)

    process_catalog(input_path, args.in_place, args.no_backup, args.dry_run)


if __name__ == "__main__":
    main()
