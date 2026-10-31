#!/usr/bin/env python3
"""
LIVE pilot (private Overpass only) of an "open coast" test for the natural beauty water type.  Changes no score.
For each pilot place it finds the nearest OSM coastline segment, casts a ray from that point toward the water side
(OSM convention: land on the left of a coastline way, water on the right) and measures how far the ray runs before it
reaches another coastline segment.  A tidal strait (East River, Hudson) hits the far bank within a few km; an open
coast runs out to the search limit.  Prints the measured width, so any cutoff (2, 5, 10 km) can be applied afterwards.
The cutoff is a judgment with no source; this pilot only shows what each one would do.

  cd /Users/adamwright/Dev/home-fit && OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python3 scripts/qa/natural_beauty_openness_pilot.py 2>&1 | grep -E "^(PLACE|DONE)"
"""
import json, math, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
import requests

SEARCH_KM, LIMIT_KM = 15, 30
# (name, state, lat, lon): pin coordinates from the catalog, so the pilot needs no scoring run
PLACES = [("Midtown", "NY"), ("Midtown East", "NY"), ("Maspeth", "NY"), ("Washington Heights", "NY"), ("Southport", "CT"),
          ("Culver City", "CA"), ("Bel Air", "CA"), ("Santa Monica", "CA"), ("Marina", "CA"), ("Seattle Waterfront", "WA"), ("Brooklyn Heights", "NY")]


def project(lat0, lon0, lat, lon):
    return ((lon - lon0) * 111.32 * math.cos(math.radians(lat0)), (lat - lat0) * 110.57)  # km east, km north


def coastline(lat, lon):
    q = f'[out:json][timeout:120];way["natural"="coastline"](around:{(SEARCH_KM + LIMIT_KM) * 1000},{lat},{lon});out geom;'
    r = requests.post(os.environ["OVERPASS_URL"], data={"data": q}, timeout=180); r.raise_for_status()
    ways = []
    for el in r.json().get("elements", []):
        pts = [project(lat, lon, g["lat"], g["lon"]) for g in el.get("geometry", [])]
        if len(pts) > 1:
            ways.append(pts)
    return ways


def nearest_on_segment(a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy))) if dx or dy else 0.0
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(px, py), (px, py)


def ray_hit(o, d, a, b):
    """Distance along unit ray d from o to segment ab, or None."""
    (ox, oy), (dx, dy), (ax, ay), (bx, by) = o, d, a, b
    ex, ey = bx - ax, by - ay; den = dx * ey - dy * ex
    if abs(den) < 1e-12:
        return None
    t = ((ax - ox) * ey - (ay - oy) * ex) / den; u = ((ax - ox) * dy - (ay - oy) * dx) / den
    return t if t > 0.02 and 0 <= u <= 1 else None  # 20 m guard against the start segment itself


def openness(ways):
    """(distance to nearest coast km, width km across the water on the perpendicular, median width over a +-40 degree fan)."""
    best = None
    for w in ways:
        for i in range(len(w) - 1):
            d, p = nearest_on_segment(w[i], w[i + 1])
            if best is None or d < best[0]:
                best = (d, p, w[i], w[i + 1])
    if best is None:
        return None
    dist, p, a, b = best
    ex, ey = b[0] - a[0], b[1] - a[1]; n = math.hypot(ex, ey)
    right = (ey / n, -ex / n)  # water side
    widths = []
    for deg in (-40, -20, 0, 20, 40):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        d = (right[0] * c - right[1] * s, right[0] * s + right[1] * c)
        hits = [h for w in ways for i in range(len(w) - 1) if (h := ray_hit(p, d, w[i], w[i + 1])) is not None]
        widths.append(min(hits) if hits and min(hits) <= LIMIT_KM else float("inf"))
    fan = sorted(widths)[len(widths) // 2]
    return dist, widths[2], fan


def find(name, st):
    import glob
    for path in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(path, encoding="utf-8"):
            if f'"{name}"' in line:
                r = json.loads(line)
                if r["catalog"]["name"] == name and r["catalog"]["state_abbr"] == st:
                    return float(r["catalog"]["lat"]), float(r["catalog"]["lon"])


if __name__ == "__main__":
    if not os.getenv("OVERPASS_URL"):
        sys.exit("OVERPASS_URL not set")
    for name, st in PLACES:
        c = find(name, st)
        if not c:
            print(f"PLACE {name}, {st}: not in catalog", flush=True); continue
        try:
            o = openness(coastline(*c))
            if o is None:
                print(f"PLACE {name}, {st}: no coastline within {SEARCH_KM + LIMIT_KM} km", flush=True); continue
            dist, perp, fan = o
            f = lambda x: ">%d km (open)" % LIMIT_KM if x == float("inf") else f"{x:.1f} km"
            print(f"PLACE {name}, {st}: coast {dist:.1f} km away | width across water: perpendicular {f(perp)}, fan median {f(fan)}", flush=True)
        except Exception as e:
            print(f"PLACE {name}, {st}: ERR {type(e).__name__} {e}", flush=True)
    print("DONE")
