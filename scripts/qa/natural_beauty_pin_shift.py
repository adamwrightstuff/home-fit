#!/usr/bin/env python3
"""
Natural beauty pin-shift test (design principles v2, P6). LIVE: calls GEE and Overpass, so the private Overpass
tunnel must be up (OVERPASS_URL=http://localhost:12345/api/interpreter) and the places must be in its states.

For each sampled catalog place it scores the stored pin and the pin moved 250 m and 500 m north and east, all
in this run (so GEE or catalog drift does not count as shift), then reports the score change against the
unshifted live score.  The gate is 5 points at p95.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/natural_beauty_pin_shift.py --n 12
"""
import argparse
import glob
import json
import math
import os
import random
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from pillars.natural_beauty import get_natural_beauty_score  # noqa: E402

STATES = {"NY", "NJ", "CT", "CA", "WA", "TX", "IL", "IN", "PA", "DE", "MD"}  # private Overpass coverage
SHIFTS = [("base", 0, 0)] + [(f"{d}{m}", m * dn, m * de) for m in (250, 500) for d, dn, de in (("N", 1, 0), ("E", 0, 1))]


def sample(n, seed):
    rows = []
    for p in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            at = ((r["score"].get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")
            if r["catalog"].get("state_abbr") in STATES and isinstance(nb.get("score"), (int, float)) and at:
                rows.append((r["catalog"]["name"], r["catalog"]["state_abbr"], float(r["catalog"]["lat"]), float(r["catalog"]["lon"]), at, nb["score"]))
    random.Random(seed).shuffle(rows)
    by_type, out = {}, []
    for row in rows:  # spread across area types
        by_type.setdefault(row[4], []).append(row)
    while len(out) < n and any(by_type.values()):
        for t in list(by_type):
            if by_type[t] and len(out) < n:
                out.append(by_type[t].pop())
    return out


def score_at(place, dn_m, de_m):
    name, st, lat, lon, at, _ = place
    la = lat + dn_m / 111320.0
    lo = lon + de_m / (111320.0 * math.cos(math.radians(lat)))
    try:
        s, _d = get_natural_beauty_score(la, lo, city="New York" if st == "NY" else None, area_type=at, location_name=name)
        return None if s is None else float(s)
    except Exception as e:  # a failed read is reported, not scored
        return f"ERR {type(e).__name__}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=2)  # 3 caused GEE read timeouts that degrade reads
    a = ap.parse_args()
    if not os.getenv("OVERPASS_URL"):
        sys.exit("OVERPASS_URL not set (open the tunnel first)")
    places = sample(a.n, a.seed)
    jobs = [(p, lab, dn, de) for p in places for lab, dn, de in SHIFTS]
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda j: score_at(j[0], j[2], j[3]), jobs))
    table, deltas = {}, {250: [], 500: []}
    for (p, lab, _, _), s in zip(jobs, res):
        table.setdefault(p[0], {"state": p[1], "area_type": p[4], "stored": round(p[5], 1)})[lab] = s if isinstance(s, str) or s is None else round(s, 1)
    for name, row in table.items():
        b = row.get("base")
        if isinstance(b, float):
            for lab in ("N250", "E250", "N500", "E500"):
                if isinstance(row.get(lab), float):
                    deltas[int(lab[1:])].append(abs(row[lab] - b))
        print(f"{name:28s} {row['area_type']:12s} stored {row['stored']:5.1f} | " + " ".join(f"{k}={row.get(k)}" for k in ("base", "N250", "E250", "N500", "E500")))
    for m, d in deltas.items():
        if d:
            d.sort()
            p95 = d[min(len(d) - 1, int(math.ceil(0.95 * len(d))) - 1)]
            print(f"\n{m} m shift: n={len(d)} median {statistics.median(d):.1f}  p95 {p95:.1f}  max {max(d):.1f}  (gate: p95 <= 5)")
    out = ROOT / "analysis" / "natural_beauty_pin_shift_results.json"
    out.write_text(json.dumps(table, indent=1))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
