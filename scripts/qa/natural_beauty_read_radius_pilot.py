#!/usr/bin/env python3
"""
LIVE pilot (GEE + private Overpass) of the single 1,200 m green view radius (area type no longer changes how greenery
is read).  Rescores 8 urban residential places (previously read at 800 m) and 2 suburban controls (already 1,200 m, so
r800 vs r1200 there shows what changing the radius does to a place the old rule never touched) and prints the live score at 800 m and at 1,200 m for each (same run, same inputs otherwise).  Places are in the private server's states.

  cd /Users/adamwright/Dev/home-fit && OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python3 scripts/qa/natural_beauty_read_radius_pilot.py 2>&1 | grep -E "^(PLACE|DONE)"
"""
import glob, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
from pillars import natural_beauty as NB

STATES = {"NY", "NJ", "CT", "CA", "WA", "TX", "IL", "IN", "PA", "DE", "MD"}
if not os.getenv("OVERPASS_URL"): sys.exit("OVERPASS_URL not set")
rows = {"urban_residential": [], "suburban": []}
for p in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
    for line in open(p, encoding="utf-8"):
        if not line.strip(): continue
        r = json.loads(line); nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
        at = ((r["score"].get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")
        if at in rows and r["catalog"]["state_abbr"] in STATES and isinstance(nb.get("score"), (int, float)) \
                and (nb.get("data_quality") or {}).get("degraded") is not True:
            rows[at].append((r["catalog"]["name"], r["catalog"]["state_abbr"], float(r["catalog"]["lat"]), float(r["catalog"]["lon"]), at, nb["score"]))
import random
rnd = random.Random(5)
picks = rnd.sample(rows["urban_residential"], 8) + rnd.sample(rows["suburban"], 2)
for name, st, la, lo, at, stored in picks:
    res = {}
    for rad in (800, 1200):  # same place, same run: only the green view radius differs
        NB.NB_READ_RADIUS_M = rad
        try:
            sc, d = NB.get_natural_beauty_score(la, lo, city="New York" if st == "NY" else None, area_type=at, location_name=name)
            v = d.get("v9_breakdown") or (d.get("details") or {}).get("v9_breakdown") or {}
            res[rad] = (sc, (v.get("inputs") or {}).get("gvi_pct"))
        except Exception as e:
            res[rad] = (None, f"ERR {type(e).__name__}")
    a, b = res[800], res[1200]
    dl = f"{b[0] - a[0]:+.1f}" if a[0] is not None and b[0] is not None else "n/a"
    print(f"PLACE {name}, {st} ({at}): r800 {a[0] if a[0] is None else round(a[0], 1)} (gvi {a[1]}) | r1200 {b[0] if b[0] is None else round(b[0], 1)} (gvi {b[1]}) | delta {dl} | stored {stored:.1f}", flush=True)
print("DONE")
