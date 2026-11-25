#!/usr/bin/env python3
"""
Offline: apply Social Fabric v22 to stored catalog scores (2026-11-25). No API calls; never edits the inputs.

v22 = the Atlas ZIP volunteering rate is scored against density-band (area-type) peers from
data/social_cohesion_bands.json instead of one national z-score, so a dense neighborhood is ranked against dense
neighborhoods. Participation stays 0.65 x volunteering + 0.35 x Atlas civic-organization score (already banded); a place
with no ZIP volunteering value keeps its stored participation. Cohesion, rootedness and weights are read from the
stored v21 record.

  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_v22_offline.py --out-dir analysis/sf_v22
  then, per output file: recompute_catalog_composites.py --input <new> --output <new2> --no-census
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from data_sources import social_capital_cohesion  # noqa: E402
from pillars.social_fabric_blend import blend_social_fabric  # noqa: E402


def recompute(score: dict):
    sf = (score.get("livability_pillars") or {}).get("social_fabric")
    if not sf or not isinstance(sf.get("score"), (int, float)):
        return "no_social_fabric"
    b, s = sf.get("breakdown") or {}, sf.get("summary") or {}
    zip_code = (score.get("location_info") or {}).get("zip")
    area_type = (sf.get("area_classification") or {}).get("area_type")
    rate = social_capital_cohesion.get_volunteering_value(zip_code)
    vol = social_capital_cohesion._score_metric(rate, area_type, "volunteering_rate_zip") if rate is not None else None
    if vol is None:
        return "no_zip_volunteering_or_band"
    atlas = s.get("atlas_civic_orgs_score")
    part = 0.65 * vol + 0.35 * atlas if atlas is not None else vol
    try:
        new, weights, _ = blend_social_fabric(participation=part, cohesion=b.get("social_capital"),
                                              rootedness=b.get("rootedness"), civic=b.get("peer_civic"),
                                              economic_connectedness=b.get("economic_connectedness"))
    except RuntimeError:
        return "not_enough_components"
    old = sf["score"]
    b["participation"] = round(part, 1)
    s["volunteering_resolution"] = "sca_zip_band"
    s["weights_used"] = {k: round(v, 4) for k, v in weights.items()}
    s["social_fabric_version"] = "v22"
    sf["breakdown"], sf["summary"], sf["score"] = b, s, new
    if isinstance(sf.get("weight"), (int, float)):
        sf["contribution"] = round(sf["weight"] * new / 100.0, 4)
    return old, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    out_dir = Path(a.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        sys.exit(f"{out_dir} is not empty; refusing to overwrite")
    out_dir.mkdir(parents=True, exist_ok=True)
    changes, skipped = [], {}
    for path in sorted(glob.glob(a.glob)):
        out = []
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            row = json.loads(line)
            res = recompute(row.get("score") or {})
            if isinstance(res, tuple):
                cat = row.get("catalog") or {}
                changes.append((os.path.basename(path).split("_metro")[0], cat.get("name"), cat.get("state_abbr"), *res))
            else:
                skipped[res] = skipped.get(res, 0) + 1
            out.append(json.dumps(row, ensure_ascii=False))
        (out_dir / os.path.basename(path)).write_text("\n".join(out) + "\n", encoding="utf-8")
    with open(out_dir / "changes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metro", "name", "state", "old", "new"])
        w.writerows(changes)
    d = [c[4] - c[3] for c in changes]
    print(f"places {len(changes)}, mean change {sum(d)/len(d):+.2f}, skipped {skipped}")


if __name__ == "__main__":
    main()
