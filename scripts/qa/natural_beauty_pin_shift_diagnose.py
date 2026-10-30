#!/usr/bin/env python3
"""
Diagnose the two natural beauty findings from natural_beauty_pin_shift.py (LIVE: GEE and Overpass).
  1. Big 500 m moves (Midtown east, Southport north): print the inputs and part scores at the base pin and the
     shifted pin so the driver is visible.
  2. Live vs stored at the same pin (Washington Heights, Maspeth, Midtown East, Midtown): print the live
     breakdown next to the stored one.
Writes analysis/natural_beauty_pin_shift_diagnosis.txt as it goes.

  cd /Users/adamwright/Dev/home-fit && OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python3 scripts/qa/natural_beauty_pin_shift_diagnose.py 2>&1 | grep -E "^(==|  )"
"""
import glob
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from pillars.natural_beauty import get_natural_beauty_score  # noqa: E402

STORED = {"Midtown": 24.8, "Southport": 62.3, "Washington Heights": 83.0, "Maspeth": 38.5, "Midtown East": 32.4}
JOBS = [  # (name, label, north_m, east_m)
    ("Midtown", "base", 0, 0), ("Midtown", "E500", 0, 500),
    ("Southport", "base", 0, 0), ("Southport", "N250", 250, 0), ("Southport", "N500", 500, 0),
    ("Washington Heights", "base", 0, 0), ("Maspeth", "base", 0, 0), ("Midtown East", "base", 0, 0),
]
KEYS = ["region", "gvi_pct", "canopy_pct", "gvi_score", "canopy_score", "topo_score", "water_type", "water_dist_km",
        "water_score", "water_status", "streets_score", "scenery_score", "blend_raw"]
OUT = ROOT / "analysis" / "natural_beauty_pin_shift_diagnosis.txt"


def find(name, score):
    for p in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(p, encoding="utf-8"):
            if '"%s"' % name not in line:
                continue
            r = json.loads(line)
            nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            if r["catalog"]["name"] == name and isinstance(nb.get("score"), (int, float)) and abs(nb["score"] - score) < 0.1:
                return r, nb
    return None, None


def flat(v9):
    i = (v9 or {}).get("inputs") or {}
    d = {**(v9 or {}), **i}
    d["water_dist_km"] = i.get("water_distance_km", i.get("water_nearest_km", (v9 or {}).get("water_distance_km")))
    return {k: d.get(k) for k in KEYS}


def fmt(d):
    return "  ".join(f"{k}={round(v, 1) if isinstance(v, float) else v}" for k, v in d.items() if v is not None)


def out(s):
    print(s, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def main():
    if not os.getenv("OVERPASS_URL"):
        sys.exit("OVERPASS_URL not set")
    OUT.write_text("")
    for name, lab, dn, de in JOBS:
        r, nb = find(name, STORED[name])
        if r is None:
            out(f"== {name}: stored row not found"); continue
        lat, lon = float(r["catalog"]["lat"]), float(r["catalog"]["lon"])
        at = ((r["score"].get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")
        la, lo = lat + dn / 111320.0, lon + de / (111320.0 * math.cos(math.radians(lat)))
        if lab == "base":
            v9s = (nb.get("details") or {}).get("v9_breakdown") or nb.get("v9_breakdown")
            out(f"== {name} STORED score {nb['score']}")
            out("  " + fmt(flat(v9s)))
        try:
            s, det = get_natural_beauty_score(la, lo, city="New York" if r["catalog"]["state_abbr"] == "NY" else None, area_type=at, location_name=name)
            v9 = (det or {}).get("v9_breakdown") or ((det or {}).get("details") or {}).get("v9_breakdown")
            out(f"== {name} LIVE {lab} score {None if s is None else round(s, 1)}")
            out("  " + fmt(flat(v9)))
            ta = (det or {}).get("tree_analysis") or {}
            out(f"  canopy radius profile: area_type={at} multi_radius={ta.get('multi_radius_canopy')}")
        except Exception as e:
            out(f"== {name} LIVE {lab} ERR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
