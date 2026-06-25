#!/usr/bin/env python3
"""
Offline Social Fabric v15 recompute (no pillar API calls).

For each row:
  1. If the row now has a ZIP (backfilled) but no stored social_capital, re-lookup from Atlas.
  2. Re-blend social_capital using updated clustering/support weights (0.35/0.65).
  3. Recompute composite with updated pillar weights:
       social capital available: 0.45×sc + 0.40×rootedness + 0.15×participation
       fallback (no Atlas):      0.85×rootedness + 0.15×participation
  4. Migrate breakdown keys to v15 names.

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

from data_sources import social_capital_cohesion


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


def _v15_score(rootedness: float, participation: float, social_capital: Optional[float]) -> float:
    if social_capital is not None:
        raw = 0.45 * social_capital + 0.40 * rootedness + 0.15 * participation
    else:
        raw = 0.85 * rootedness + 0.15 * participation
    return round(max(0.0, min(100.0, raw)), 1)


def recompute_row(row: dict) -> str:
    sf = row.get("score", {}).get("livability_pillars", {}).get("social_fabric")
    if not sf or sf.get("status") != "success":
        return "skip_no_sf"

    breakdown = sf.get("breakdown") or {}
    summary = sf.get("summary") or {}

    rootedness = breakdown.get("rootedness") or breakdown.get("stability")
    participation = breakdown.get("participation") or breakdown.get("engagement")
    stored_sc = breakdown.get("social_capital") or breakdown.get("cohesion")

    if rootedness is None or participation is None:
        return "skip_missing"

    zip_code = row.get("score", {}).get("location_info", {}).get("zip")
    area_type = (sf.get("area_classification") or {}).get("area_type")

    # Re-lookup social capital — covers newly backfilled ZIPs and corrects
    # the clustering/support weights (now 0.35/0.65 from 0.65/0.35).
    new_sc, sc_diag = social_capital_cohesion.get_cohesion_score(zip_code, area_type)

    # Update summary diagnostics with new cohesion blend
    if new_sc is not None:
        summary["cohesion_score"] = new_sc
        summary["cohesion_clustering_score"] = sc_diag.get("clustering_score")
        summary["cohesion_support_score"] = sc_diag.get("support_score")
        summary["cohesion_resolution"] = sc_diag.get("resolution")
        sf["summary"] = summary

    social_capital = new_sc  # may be None if ZIP still not in Atlas

    new_score = _v15_score(float(rootedness), float(participation), social_capital)
    old_score = sf.get("score")

    sf["breakdown"] = {
        "rootedness": rootedness,
        "participation": participation,
        "social_capital": social_capital,
    }
    sf["score"] = new_score
    if isinstance(sf.get("details"), dict):
        sf["details"]["version"] = "v15_sf_three_pillars"

    pillars = row["score"]["livability_pillars"]
    row["score"]["total_score"] = _recompute_total(pillars)

    newly_got_sc = (stored_sc is None and new_sc is not None)
    changed = newly_got_sc or old_score is None or abs(float(old_score) - new_score) > 0.05
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
        if status == "changed" and len(examples) < 8:
            sf = row["score"]["livability_pillars"]["social_fabric"]
            bd = sf["breakdown"]
            name = (row.get("catalog") or {}).get("name", "?")
            sc = bd.get("social_capital")
            examples.append(
                f"  {name}: score={sf['score']}  sc={'N/A' if sc is None else round(sc,1)}"
                f"  root={round(bd['rootedness'],1)}  part={round(bd['participation'],1)}"
            )

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
