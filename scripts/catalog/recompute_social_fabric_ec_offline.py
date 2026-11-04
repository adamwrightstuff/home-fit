#!/usr/bin/env python3
"""
Offline: add the economic connectedness (EC) component to stored social fabric scores (DPv2, 2026-11-03).

No API calls. Reads the catalog JSONL files, never edits them: writes new files into --out-dir plus a change CSV.
Inputs per place: stored participation, cohesion and civic scores; the rootedness score is recovered from the stored
score and the stored weights_used (accurate to +-0.5 because the stored score is rounded to 0.1); EC comes from the
Atlas file by the ZIP in location_info. A place whose ZIP is not in the Atlas keeps EC out and the other weights
rescale (principle 9), so its score equals the pre-EC blend of the same components.

  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_ec_offline.py --out-dir analysis/dpv2_social_fabric_ec
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
        return None
    b, s = sf.get("breakdown") or {}, sf.get("summary") or {}
    w = s.get("weights_used") or {}
    part, coh, civ = b.get("participation"), b.get("social_capital"), b.get("peer_civic")
    stab = None
    if "rootedness" in w:
        rest = sum(w[k] * v for k, v in (("participation", part), ("cohesion", coh), ("civic", civ)) if k in w and v is not None)
        stab = (sf["score"] - rest) / w["rootedness"]
        if not -2.0 <= stab <= 102.0:
            return "reconstruction_failed"
    zip_code = (score.get("location_info") or {}).get("zip")
    ec_score, ec_raw = social_capital_cohesion.get_ec_score(zip_code)
    new, weights, _ = blend_social_fabric(participation=part, cohesion=coh, rootedness=stab,
                                          civic=civ if civ else None, economic_connectedness=ec_score)
    old = sf["score"]
    b["economic_connectedness"] = ec_score
    s["economic_connectedness_raw"] = ec_raw
    s["weights_used"] = {k: round(v, 4) for k, v in weights.items()}
    cm = dict(s.get("components_missing") or {})
    cm.pop("economic_connectedness", None)  # EC is a separate stored measure now, not a blend component
    s["components_missing"] = cm
    sf["breakdown"], sf["summary"] = b, s
    sf["score"] = new
    if isinstance(sf.get("weight"), (int, float)):
        sf["contribution"] = round(sf["weight"] * new / 100.0, 4)
    return old, new, ec_score, ec_raw, (score.get("location_info") or {}).get("zip")


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
                at = (((row["score"].get("livability_pillars") or {}).get("social_fabric") or {}).get("area_classification") or {}).get("area_type")
                changes.append((os.path.basename(path).split("_metro")[0], cat.get("name"), cat.get("state_abbr"), at, *res))
            else:
                skipped[res] = skipped.get(res, 0) + 1
            out.append(json.dumps(row, ensure_ascii=False))
        (out_dir / os.path.basename(path)).write_text("\n".join(out) + "\n", encoding="utf-8")
    with open(out_dir / "changes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metro", "name", "state", "area_type", "old", "new", "ec_score", "ec_raw", "zip"])
        w.writerows(changes)
    n_ec = sum(1 for c in changes if c[6] is not None)
    print(f"places {len(changes)}, with EC {n_ec}, without EC {len(changes) - n_ec}, skipped {skipped}")


if __name__ == "__main__":
    main()
