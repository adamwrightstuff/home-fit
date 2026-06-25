#!/usr/bin/env python3
"""
Offline Social Fabric v16 recompute (no pillar API calls).

For each row:
  1. Re-lookup social_capital from Atlas with corrected clustering/support weights (0.65/0.35).
  2. Compute peer_civic from stored civic_effective_weighted + civic_band_tier using bands.
  3. Recompute composite:
       w_sc    = 0.20 if social_capital available else 0.0
       w_civic = 0.10 if peer_civic > 0 else 0.0
       w_part  = 1.0 - w_sc - w_civic
       score   = w_sc×sc + w_part×participation + w_civic×peer_civic
  4. Update breakdown keys: participation, social_capital, peer_civic.

Weights from external validation (ec_zip + atlas_civic_orgs, non-circular, n=267):
  participation corr=0.184, social_capital corr=0.161, peer_civic corr=0.089
  Rootedness dropped (corr=-0.039). Clustering weight reverted to 0.65 (external corr=0.30
  vs support 0.07 — previous flip was based on circular correlation with composite).

Reference: Zahnow (2024) validates social infrastructure as a pathway to cohesion and
wellbeing; peer-normalized civic score re-enters at 10% as the encounter-facilitation term.

Usage:
  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_v15_offline.py \\
    --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
    --output data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl
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

from data_sources import social_capital_cohesion, social_fabric_bands


_bands = social_fabric_bands.load_bands()


def _peer_civic_score(civic_eff: Optional[float], band_tier: Optional[str]) -> Optional[float]:
    if not civic_eff or not band_tier or not _bands:
        return None
    try:
        return social_fabric_bands.score_civic_gathering_from_bands(
            float(civic_eff), band_tier, _bands, proximity=False
        )
    except Exception:
        return None


def _v16_score(participation: float, social_capital: Optional[float], peer_civic: Optional[float], rootedness: Optional[float]) -> float:
    w_sc    = 0.20 if social_capital is not None else 0.0
    w_civic = 0.10 if (peer_civic is not None and peer_civic > 0) else 0.0
    w_root  = 0.10 if rootedness is not None else 0.0
    w_part  = 1.0 - w_sc - w_civic - w_root
    raw = (w_sc   * (social_capital or 0.0)
           + w_root * (rootedness or 0.0)
           + w_part * participation
           + w_civic * (peer_civic or 0.0))
    return round(max(0.0, min(100.0, raw)), 1)


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


def recompute_row(row: dict) -> str:
    sf = row.get("score", {}).get("livability_pillars", {}).get("social_fabric")
    if not sf or sf.get("status") != "success":
        return "skip_no_sf"

    breakdown = sf.get("breakdown") or {}
    summary   = sf.get("summary") or {}

    participation = breakdown.get("participation") or breakdown.get("engagement")
    if participation is None:
        return "skip_missing"

    zip_code  = row.get("score", {}).get("location_info", {}).get("zip")
    area_type = (sf.get("area_classification") or {}).get("area_type")

    # Re-lookup social capital (corrected clustering 0.65 / support 0.35)
    new_sc, sc_diag = social_capital_cohesion.get_cohesion_score(zip_code, area_type)
    if new_sc is not None:
        summary["cohesion_score"]          = new_sc
        summary["cohesion_clustering_score"] = sc_diag.get("clustering_score")
        summary["cohesion_support_score"]    = sc_diag.get("support_score")
        summary["cohesion_resolution"]       = sc_diag.get("resolution")
        sf["summary"] = summary

    # Peer-normalized civic score from stored data
    civic_eff  = summary.get("civic_effective_weighted")
    band_tier  = summary.get("civic_band_tier")
    peer_civic = _peer_civic_score(civic_eff, band_tier)

    rootedness = summary.get("stability_blend_pct")
    new_score = _v16_score(float(participation), new_sc, peer_civic, rootedness)
    old_score = sf.get("score")

    sf["breakdown"] = {
        "participation":  round(float(participation), 1),
        "social_capital": new_sc,
        "peer_civic":     round(peer_civic, 1) if peer_civic is not None else None,
        "rootedness":     round(rootedness, 1) if rootedness is not None else None,
    }
    sf["score"] = new_score
    if isinstance(sf.get("details"), dict):
        sf["details"]["version"] = "v16b_sf_with_rootedness"

    row["score"]["total_score"] = _recompute_total(row["score"]["livability_pillars"])

    changed = old_score is None or abs(float(old_score) - new_score) > 0.05
    return "changed" if changed else "unchanged"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",   required=True, type=Path)
    parser.add_argument("--output",  type=Path, default=None)
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
            sf  = row["score"]["livability_pillars"]["social_fabric"]
            bd  = sf["breakdown"]
            name = (row.get("catalog") or {}).get("name", "?")
            sc   = bd.get("social_capital")
            pc   = bd.get("peer_civic")
            examples.append(
                f"  {name}: score={sf['score']}"
                f"  sc={round(sc,1) if sc is not None else 'N/A'}"
                f"  part={bd['participation']}"
                f"  civic={round(pc,1) if pc is not None else 'N/A'}"
            )

    print(json.dumps(counts, indent=2))
    if examples:
        print("Sample:")
        for e in examples:
            print(e)

    if not args.dry_run and args.output:
        args.output.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        print(f"\nWrote {len(rows)} rows → {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
