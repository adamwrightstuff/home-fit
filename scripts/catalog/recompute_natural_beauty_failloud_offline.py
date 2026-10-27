#!/usr/bin/env python3
"""
Offline: apply the natural beauty fail-loud rules (design principles v2, P9) to the stored catalog.
No API calls, no GEE.  Touches only places the rules change:

  1. Missing water: water_type is null and the water score is the old made-up 5.0.  Active Outdoors stored
     water features for these places, so the read failed rather than found nothing; the label is
     "unavailable".  Scenery is scored from terrain alone and the place is marked degraded.
  2. Green view under 2% that was replaced by 0.7 x canopy (gvi_source canopy_proxy): rescored with the
     measured green view.
  3. No greenery measurement at all (both streets inputs exact zeros): the pillar becomes no data, in the
     stored-gap shape (score None, contribution 0.0, confidence 0, status no_data), so the composites
     cascade redistributes its weight.

Places whose tree_analysis has component scores are re-run through pillars.natural_beauty._apply_v9_formula
(reproduces the other 1,020 stored scores to 0.02).  Places stored in the older shape (no component scores
in tree_analysis, 239 in NYC and LA) are recomputed from the stored per-dimension scores, which covers the
water rule only; proxy places in that group are listed, not changed.

  PYTHONPATH=. python3 scripts/catalog/recompute_natural_beauty_failloud_offline.py                       # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_natural_beauty_failloud_offline.py --write --backup-dir <dir>
Then: PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --in-place --no-census
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
sys.path.insert(0, str(ROOT))

from pillars import natural_beauty as NB  # noqa: E402

WATER_REASON = "water_read_unavailable: scenery scored from terrain alone"


def _v9(nb: dict):
    d = nb.get("details") or {}
    return next((c for c in (d.get("v9_breakdown"), nb.get("v9_breakdown")) if isinstance(c, dict) and "gvi_score" in c), None)


def _ao_has_water(pillars: dict) -> bool:
    s = (pillars.get("active_outdoors") or {}).get("summary") or {}
    w = s.get("water") if isinstance(s, dict) else None
    return isinstance(w, dict) and (w.get("features") or 0) > 0


def _set_degraded(nb: dict, reasons: list) -> None:
    dq = nb.get("data_quality") if isinstance(nb.get("data_quality"), dict) else {}
    dq["degraded"] = True
    dq["degraded_reasons"] = [r for r in (dq.get("degraded_reasons") or []) if not str(r).startswith("natural_beauty:")] + \
        [f"natural_beauty: {r}" for r in reasons]
    nb["data_quality"] = dq


def make_no_data(nb: dict, reason: str) -> None:
    nb["score"] = None
    nb["contribution"] = 0.0
    nb["confidence"] = 0
    nb["status"] = "no_data"
    nb["rescore_available"] = True
    nb["summary"] = {"no_data_reason": reason}
    _set_degraded(nb, [f"no_data: {reason}"])
    dq = nb["data_quality"]
    dq.update({"quality_tier": "none", "confidence": 0})


def apply_score(nb: dict, score: float, v9: dict, old_score) -> None:
    d = nb.setdefault("details", {})
    d.setdefault("score_before_failloud", old_score)
    nb["score"] = round(float(score), 2)
    d["score_v9"] = nb["score"]
    d["v9_breakdown"] = v9
    if isinstance(nb.get("v9_breakdown"), dict):
        nb["v9_breakdown"] = v9  # older runs keep a second copy at the pillar root; it must not go stale
    if isinstance(nb.get("weight"), (int, float)):
        nb["contribution"] = round(nb["weight"] * nb["score"] / 100.0, 4)
    if v9.get("degraded_reasons"):
        _set_degraded(nb, v9["degraded_reasons"])


def process(rec: dict):
    """Returns (kind, old_score, new_score) or None when the place is untouched."""
    s = rec.get("score") or {}
    P = s.get("livability_pillars") or {}
    nb = P.get("natural_beauty")
    if not isinstance(nb, dict) or not isinstance(nb.get("score"), (int, float)):
        return None
    v9 = _v9(nb)
    if v9 is None:
        return None
    # Places already rewritten by this script whose pillar-root copy of the breakdown is still the old one.
    top = nb.get("v9_breakdown")
    if isinstance(top, dict) and top != v9 and "degraded_reasons" in v9 and v9.get("method") == "two_part_v10":
        nb["v9_breakdown"] = v9
        return ("synced_root_copy", nb["score"], nb["score"])
    i = v9.get("inputs") or {}
    old = nb["score"]
    ta = (nb.get("details") or {}).get("tree_analysis") or {}
    has_cs = bool((ta.get("natural_context") or {}).get("component_scores"))
    water_missing = i.get("water_type") is None and v9.get("water_score") == 5.0
    proxy = str(i.get("gvi_source", "")).startswith("canopy_proxy")
    no_greenery = NB.streets_inputs_missing(i.get("gvi_pct"), i.get("canopy_pct")) and v9.get("topo_score") in (0, 0.0, None)
    if not (water_missing or proxy or no_greenery):
        return None
    if water_missing and not _ao_has_water(P):
        return ("skipped_no_water_evidence", old, None)
    if no_greenery:
        make_no_data(nb, "no greenery measurement (green view and canopy both missing) and no terrain")
        return ("no_data", old, None)
    coords = s.get("coordinates") or {}
    if has_cs:
        ta2 = dict(ta)
        ta2["water_read_status"] = "unavailable" if water_missing else ta2.get("water_read_status")
        try:
            new, v9n = NB._apply_v9_formula({}, ta2, lat=coords.get("lat"), lon=coords.get("lon"))
        except NB.NaturalBeautyNoData as e:
            make_no_data(nb, str(e))
            return ("no_data", old, None)
        apply_score(nb, new, v9n, old)
        return ("rerun_" + ("water" if water_missing else "") + ("proxy" if proxy else ""), old, nb["score"])
    if proxy and not water_missing:
        return ("skipped_old_shape_proxy", old, None)
    # Old shape: water rule only, from stored per-dimension scores.
    comps = {k: v9.get(k) for k in ("gvi_score", "canopy_score", "topo_score", "water_score")}
    comps["water_score"] = None
    parts = NB.nb_two_part(comps, None, None)
    v9["water_score"] = None
    v9["water_status"] = "unavailable"
    v9["streets_score"], v9["scenery_score"] = parts["streets"], parts["scenery"]
    v9["blend_raw"], v9["streets_share"] = parts["blend"], parts["streets_share"]
    v9["method"] = "two_part_v10"
    v9["degraded_reasons"] = [WATER_REASON]
    v9["low_confidence"] = True
    apply_score(nb, parts["score"], v9, old)
    return ("old_shape_water", old, nb["score"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    tally, rows = {}, []
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out, changed = [], False
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            try:
                rec = json.loads(line)
            except Exception:
                out.append(line)
                continue
            res = process(rec)
            if res is None:
                out.append(line)
                continue
            kind, old, new = res
            tally[kind] = tally.get(kind, 0) + 1
            name = (rec.get("catalog") or {}).get("name")
            rows.append((metro, name, kind, old, new))
            if kind.startswith("skipped"):
                out.append(line)
                continue
            tb = ((rec.get("score") or {}).get("total_score_breakdown") or {}).get("natural_beauty")
            nbp = rec["score"]["livability_pillars"]["natural_beauty"]
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = nbp["score"], nbp.get("contribution", 0.0)
            out.append(json.dumps(rec, ensure_ascii=False))
            changed = True
        if a.write and changed:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| by kind:", tally)
    deltas = [r[4] - r[3] for r in rows if r[4] is not None]
    if deltas:
        print(f"scored places changed: {len(deltas)} | mean {sum(deltas)/len(deltas):+.2f} | min {min(deltas):+.1f} | max {max(deltas):+.1f}")
    for kind in sorted({r[2] for r in rows if r[4] is not None}):
        d = [r[4] - r[3] for r in rows if r[2] == kind and r[4] is not None]
        print(f"   {kind}: n {len(d)} | mean {sum(d)/len(d):+.2f} | min {min(d):+.1f} | max {max(d):+.1f} | moved >5: {sum(abs(x) > 5 for x in d)}")
    for r in rows:
        if r[2] in ("no_data",) or r[2].startswith("skipped"):
            print("  ", r)


if __name__ == "__main__":
    main()
