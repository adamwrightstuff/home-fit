#!/usr/bin/env python3
"""
Offline: apply Social Fabric v20 to stored catalog scores (2026-11-24). No API calls; never edits the inputs.

v20 = IRS nonprofit rate removed from participation (volunteering only, then 65/35 with the Atlas civic-organization
score) and OSM civic gathering spots at weight 0 (kept in the breakdown as a diagnostic). Weights for the other four
components are the v18 weights divided by 0.92. Volunteering comes from the Atlas ZIP file; a place whose ZIP has no
volunteering value falls back to the Atlas civic-organization score alone; a place with neither is left as stored and
counted. Rootedness is read from the stored breakdown.

  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_v20_offline.py --out-dir analysis/sf_v20
  then, per output file: recompute_catalog_composites.py --input <new> --output <new2> --no-census
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pillars.social_fabric_blend import blend_social_fabric  # noqa: E402

_vol: dict = {}
with open(ROOT / "data" / "social_capital_zip.csv", newline="", encoding="utf-8") as _f:
    for _r in csv.DictReader(_f):
        _v = _r.get("volunteering_rate_zip")
        if _v and _v != "NA":
            _vol[str(_r["zip"]).zfill(5)] = float(_v)
_M, _S = statistics.mean(_vol.values()), statistics.stdev(_vol.values())


def _vol_score(zip_code):
    v = _vol.get(str(zip_code or "").split("-")[0].zfill(5))
    if v is None:
        return None
    z = max(-2.5, min(2.5, (v - _M) / _S))
    return (z + 2.5) / 5.0 * 100.0


def recompute(score: dict):
    sf = (score.get("livability_pillars") or {}).get("social_fabric")
    if not sf or not isinstance(sf.get("score"), (int, float)):
        return "no_social_fabric"
    b, s = sf.get("breakdown") or {}, sf.get("summary") or {}
    vol = _vol_score((score.get("location_info") or {}).get("zip"))
    atlas = s.get("atlas_civic_orgs_score")
    if vol is not None and atlas is not None:
        part = 0.65 * vol + 0.35 * atlas
    elif vol is not None:
        part = vol
    elif atlas is not None:
        part = float(atlas)
    else:
        return "no_volunteering_or_atlas_civic"
    try:
        new, weights, _ = blend_social_fabric(participation=part, cohesion=b.get("social_capital"),
                                              rootedness=b.get("rootedness"), civic=b.get("peer_civic"),
                                              economic_connectedness=b.get("economic_connectedness"))
    except RuntimeError:
        return "blend_failed"
    old = sf["score"]
    b["participation"] = round(part, 1)
    s["weights_used"] = {k: round(v, 4) for k, v in weights.items()}
    s["participation_mix"] = "vol_atlas" if vol is not None and atlas is not None else ("vol_only" if vol is not None else "atlas_only")
    s["social_fabric_version"] = "v20"
    sf["breakdown"], sf["summary"] = b, s
    sf["score"] = new
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
