#!/usr/bin/env python3
"""
Offline: apply Social Fabric v21 to stored catalog scores (2026-11-25). No API calls; never edits the inputs.

v21 = cohesion is the stored Atlas support score only (clustering is a density artifact, kept as a diagnostic) and
economic connectedness and civic spots are diagnostics (weights come from pillars.social_fabric_blend; v22 = 0.60 / 0.20 / 0.20). Participation and rootedness are read from the stored breakdown.

  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_v21_offline.py --out-dir analysis/sf_v21
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
from pillars.social_fabric_blend import blend_social_fabric  # noqa: E402


FILLED = {"n": 0, "above_85": 0}


def recompute(score: dict):
    sf = (score.get("livability_pillars") or {}).get("social_fabric")
    if not sf or not isinstance(sf.get("score"), (int, float)):
        return "no_social_fabric"
    b, s = sf.get("breakdown") or {}, sf.get("summary") or {}
    if b.get("participation") is None:
        return "no_participation"
    cohesion = s.get("cohesion_support_score")
    # Stored gap: some rows carry the stability percent and its band score (summary.rooted_pct) but a null
    # breakdown.rootedness, so rootedness was silently left out of the blend. The score is already stored; use it
    # (no API call). It is the band score before the above-85% home-value exemption, so it is conservative for places
    # above 85% (counted in FILLED_ABOVE_85).
    if b.get("rootedness") is None and s.get("stability_blend_pct") is not None and s.get("rooted_pct") is not None:
        b["rootedness"] = s["rooted_pct"]
        s["rootedness_filled_offline"] = True
        FILLED["n"] += 1
        if s["stability_blend_pct"] > 85:
            FILLED["above_85"] += 1
    try:
        new, weights, _ = blend_social_fabric(participation=b["participation"], cohesion=cohesion,
                                              rootedness=b.get("rootedness"), civic=b.get("peer_civic"),
                                              economic_connectedness=b.get("economic_connectedness"))
    except RuntimeError:
        return "not_enough_components"
    old = sf["score"]
    b["social_capital"] = cohesion
    s["cohesion_score"] = cohesion
    s["cohesion_resolution"] = "support_only" if cohesion is not None else None
    s["weights_used"] = {k: round(v, 4) for k, v in weights.items()}
    s["social_fabric_version"] = "v21"
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
    print(f"rootedness filled from stored score: {FILLED}")
    print(f"places {len(changes)}, mean change {sum(d)/len(d):+.2f}, skipped {skipped}")


if __name__ == "__main__":
    main()
