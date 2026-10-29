#!/usr/bin/env python3
"""
LIVE pilot (GEE + private Overpass) of the best-type water rule.  Scores each place once with the current rule
and recomputes the total with the best-type water score from the same read, so the two are directly comparable.
Places are limited to the private Overpass server's states (Florida and Colorado are not covered).

  cd /Users/adamwright/Dev/home-fit && OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python3 scripts/qa/natural_beauty_water_pilot.py 2>&1 | grep -E "^(PLACE|DONE)"
"""
import glob, json, math, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
from pillars import natural_beauty as NB

JOBS = [("Midtown", "NY", 0, 0, 24.8), ("Midtown", "NY", 0, 500, 24.8), ("Midtown East", "NY", 0, 0, 32.4), ("Maspeth", "NY", 0, 0, 38.5),
        ("Washington Heights", "NY", 0, 0, 83.0), ("Southport", "CT", 0, 0, 62.3), ("Southport", "CT", 500, 0, 62.3),
        ("Culver City", "CA", 0, 0, None), ("Bel Air", "CA", 0, 0, None), ("Loomis", "CA", 0, 0, None), ("The Woodlands", "TX", 0, 0, None)]

def find(name, st, score):
    for p in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(p, encoding="utf-8"):
            if f'"{name}"' not in line: continue
            r = json.loads(line); nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            if r["catalog"]["name"] == name and r["catalog"]["state_abbr"] == st and isinstance(nb.get("score"), (int, float)) and (score is None or abs(nb["score"] - score) < .1):
                return r, nb

if not os.getenv("OVERPASS_URL"): sys.exit("OVERPASS_URL not set")
for name, st, dn, de, sc in JOBS:
    r, nb = find(name, st, sc)
    lat, lon = float(r["catalog"]["lat"]), float(r["catalog"]["lon"])
    la, lo = lat + dn / 111320.0, lon + de / (111320.0 * math.cos(math.radians(lat)))
    at = ((r["score"].get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")
    try:
        s, d = NB.get_natural_beauty_score(la, lo, city="New York" if st == "NY" else None, area_type=at, location_name=name)
        v = d.get("v9_breakdown") or (d.get("details") or {}).get("v9_breakdown") or {}
        comps = {k: v.get(k) for k in ("gvi_score", "canopy_score", "topo_score", "water_score")}
        new = None
        if v.get("water_score_best_type") is not None:
            comps["water_score"] = v["water_score_best_type"]
            new = NB.nb_two_part(comps, None, None)["score"]
        print(f"PLACE {name}, {st} {'+%dN%dE' % (dn, de) if dn or de else 'base'}: stored {nb['score']:.1f} | current {s:.1f} water {v.get('water_score')} ({(v.get('inputs') or {}).get('water_type')}, {(v.get('inputs') or {}).get('water_dist_km')} km)"
              f" | best-type water {v.get('water_score_best_type')} -> total {None if new is None else round(new, 1)}", flush=True)
    except Exception as e:
        print(f"PLACE {name}, {st}: ERR {type(e).__name__} {e}", flush=True)
print("DONE")
