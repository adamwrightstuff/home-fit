#!/usr/bin/env python3
"""
Offline Social Fabric v15 recompute (no API calls).

Reads stored breakdown sub-scores (stability/rootedness, engagement/participation,
cohesion/social_capital) and recomputes the composite using the v15 three-pillar formula:

  When Atlas cohesion available: (cohesion + stability + engagement) / 3
  When cohesion missing:         0.6 * stability + 0.4 * engagement

Also migrates breakdown keys from old v14 names to new v15 names:
  stability        → rootedness
  engagement       → participation
  cohesion         → social_capital
  (civic_gathering, bonding_cohesion, infrastructure_density dropped)

Usage:
  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_v15_offline.py \\
    --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
    --output data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl

Pass --dry-run to preview without writing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _recompute_total(pillars: dict) -> float:
    weighted = total = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        s = p.get("score")
        w = p.get("weight")
        if s is not None and w is not None:
            weighted += float(s) * float(w)
            total += float(w)
    return round(weighted / total, 4) if total > 0 else 0.0


def _v15_score(stability: float, engagement: float, cohesion: Optional[float]) -> float:
    if cohesion is not None:
        raw = (cohesion + stability + engagement) / 3.0
    else:
        raw = 0.6 * stability + 0.4 * engagement
    return round(max(0.0, min(100.0, raw)), 1)


def recompute_row(row: dict) -> str:
    sf = row.get("score", {}).get("livability_pillars", {}).get("social_fabric")
    if not sf or sf.get("status") != "success":
        return "skip_no_sf"

    breakdown = sf.get("breakdown") or {}

    # Support both old key names (v14) and new (v15 if partially applied)
    stability = breakdown.get("stability") or breakdown.get("rootedness")
    engagement = breakdown.get("engagement") or breakdown.get("participation")
    cohesion = breakdown.get("cohesion") or breakdown.get("social_capital")

    if stability is None or engagement is None:
        return "skip_missing"

    new_score = _v15_score(float(stability), float(engagement), float(cohesion) if cohesion is not None else None)
    old_score = sf.get("score")

    # Migrate breakdown keys
    sf["breakdown"] = {
        "rootedness": stability,
        "participation": engagement,
        "social_capital": cohesion,
    }

    sf["score"] = new_score
    sf["details"] = sf.get("details") or {}
    if isinstance(sf.get("details"), dict):
        sf["details"]["version"] = "v15_sf_three_pillars"

    pillars = row["score"]["livability_pillars"]
    row["score"]["total_score"] = _recompute_total(pillars)

    changed = old_score is None or abs(float(old_score) - new_score) > 0.05
    return "changed" if changed else "unchanged"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.output:
        print("ERROR: provide --output or --dry-run", file=sys.stderr)
        return 2

    rows = [json.loads(l) for l in args.input.read_text().splitlines() if l.strip()]
    counts: dict = {"changed": 0, "unchanged": 0, "skip_no_sf": 0, "skip_missing": 0}

    examples: list = []
    for row in rows:
        status = recompute_row(row)
        counts[status] = counts.get(status, 0) + 1
        if status == "changed" and len(examples) < 5:
            sf = row["score"]["livability_pillars"]["social_fabric"]
            name = (row.get("catalog") or {}).get("name", "?")
            examples.append(f"  {name}: new={sf['score']}")

    print(json.dumps(counts, indent=2))
    if examples:
        print("Sample changed:")
        for e in examples:
            print(e)

    if not args.dry_run and args.output:
        args.output.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        print(f"\nWrote {len(rows)} rows → {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
