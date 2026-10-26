#!/usr/bin/env python3
"""
Offline: apply the linear essentials-proximity decay (full credit within 400 m, zero at 1,200 m) to stored
neighborhood amenities scores, using only the stored business_list.

A row changes only if its stored proximity reproduces under the previous step rule with the supermarket-only
grocery run. Rows whose stored proximity already equals the decay value are counted as already decayed
(places re-read after the change); anything else is reported and left alone. New score =
min(100, 0.6 x new home + stored location quality). Cascade composites afterwards with
recompute_catalog_composites.py --no-census for the printed search queries.

  PYTHONPATH=. python3 scripts/catalog/recompute_amenities_proximity_decay_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_amenities_proximity_decay_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOT_A_GROCERY_RUN = {"convenience", "greengrocer"}
FULL_M, ZERO_M = 400, 1200


def _step(d):
    if d is None:
        return 0.0
    for limit, v in ((150, 1.0), (300, 0.85), (500, 0.6), (800, 0.35)):
        if d <= limit:
            return v
    return 0.0


def _decay(d):
    if d is None:
        return 0.0
    if d <= FULL_M:
        return 1.0
    if d >= ZERO_M:
        return 0.0
    return (ZERO_M - d) / (ZERO_M - FULL_M)


def proximity(biz, decay: bool, max_points: float = 25) -> float:
    limit = 10 ** 9 if decay else 800
    walk = [b for b in biz if b.get("distance_m") is not None and b["distance_m"] <= limit]

    def nearest(types, is_grocery=False):
        ds = [b["distance_m"] for b in walk if b.get("type") in types
              and not (is_grocery and b.get("shop") in NOT_A_GROCERY_RUN)]
        return min(ds) if ds else None

    f = _decay if decay else _step
    return round((f(nearest({"grocery"}, True)) * 0.45 + f(nearest({"cafe", "bakery"})) * 0.30
                  + f(nearest({"restaurant", "bar"})) * 0.25) * max_points, 2)


def adjust(a: dict):
    if a.get("score") is None:
        return "no score"
    b = a.get("breakdown") or {}
    hw = b.get("home_walkability") or {}
    parts = hw.get("breakdown") or {}
    biz = b.get("business_list") or []
    if "proximity" not in parts or not biz:
        return "no list"
    old_p, new_p = proximity(biz, False), proximity(biz, True)
    stored = parts["proximity"]
    if abs(new_p - stored) <= 0.06 and abs(old_p - stored) > 0.06:
        return "already decayed"
    if abs(old_p - stored) > 0.06:
        return "stored proximity does not reproduce"
    if abs(new_p - old_p) < 0.005:
        return "unchanged"
    old_score = a["score"]
    home = round(hw["score"] - (old_p - new_p), 1)
    new_score = round(min(100.0, home * 0.6 + (b.get("location_quality") or 0.0)), 1)
    parts["proximity"] = round(new_p, 1)
    hw["score"] = home
    a["score"] = new_score
    a["contribution"] = round(new_score * (a.get("weight") or 0) / 100, 4)
    sb = (a.get("summary") or {}).get("score_breakdown")
    if isinstance(sb, dict):
        sb["home_walkability"] = home
    return old_score, new_score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    hits, skips = [], {}
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out, old_vals = [], {}
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            try:
                rec = json.loads(line)
            except Exception:
                out.append(line)
                continue
            s = rec.get("score") or {}
            h = (s.get("livability_pillars") or {}).get("neighborhood_amenities")
            if not isinstance(h, dict):
                out.append(line)
                continue
            old = json.loads(json.dumps(h))
            r = adjust(h)
            if isinstance(r, str):
                skips[r] = skips.get(r, 0) + 1
                out.append(line)
                continue
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            tb = (s.get("total_score_breakdown") or {}).get("neighborhood_amenities")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = h["score"], h["contribution"]
            hits.append((metro, cat.get("name"), r[0], r[1], cat.get("search_query")))
            old_vals[f"{metro}|{cat.get('name')}"] = {"neighborhood_amenities": old, "total_score": s.get("total_score")}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_amenities_decay_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| places changed:", len(hits), "| skipped:", skips)
    json.dump([[m, n, o, nw, q] for m, n, o, nw, q in hits], open(os.environ.get("HITS_OUT", os.devnull), "w"))


if __name__ == "__main__":
    main()
