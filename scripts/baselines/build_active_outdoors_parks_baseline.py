"""
Build data/active_outdoors_parks_baseline.json: the expected distance-weighted park count within 2,000 m of a pin,
as a function of people plus jobs per gross acre in the 1 km around it (PlaceContext.activity_per_acre).

The value is an empirical peer median from one version of the pillar's park query, not a published
standard. Rolling median over places sorted by activity, evaluated at fixed knots, then made monotone
(running maximum) so a denser place is never expected to have fewer parks.

Inputs (not in the repo):
  --places  JSON list of {"name", "state", "act"}   act = activity per acre
  --parks   JSON {"<name>|<state>": {"outcome": "overpass_ok", "parks": [{"distance_m": ...}, ...]}}
            one park query per place at 2,000 m or more (distances beyond RADIUS_M are ignored), all from the same query version

Usage:
  PYTHONPATH=. python3 scripts/baselines/build_active_outdoors_parks_baseline.py --places P --parks Q
"""
import argparse
import json
import math
import os
import statistics

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "data", "active_outdoors_parks_baseline.json")
RADIUS_M = 2000
# Same decay the pillar uses for its nearest-park term (8 * exp(-0.0012 * metres)); one constant, not a new tunable.
DECAY_PER_M = 0.0012
KNOTS = [2, 5, 10, 15, 25, 45, 100, 200]
WINDOW = 100  # places in the rolling median, centered on the knot


def fit(rows, knots=KNOTS, window=WINDOW):
    rows = sorted(rows)  # (act, count)
    values = []
    for k in knots:
        i = min(range(len(rows)), key=lambda j: abs(rows[j][0] - k))
        lo = max(0, min(i - window // 2, len(rows) - window))
        values.append(statistics.median(c for _, c in rows[lo:lo + window]))
    out, top = [], 0.0
    for v in values:
        top = max(top, v)
        out.append(round(top, 1))
    return out


def weighted(items) -> float:
    return round(sum(math.exp(-DECAY_PER_M * x["distance_m"]) for x in items if x["distance_m"] <= RADIUS_M), 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--places", required=True)
    ap.add_argument("--parks", required=True)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    parks = json.load(open(args.parks))
    park_rows, play_rows = [], []
    for p in json.load(open(args.places)):
        r = parks.get(f"{p['name']}|{p['state']}")
        if p.get("act") is None or not r or r.get("outcome") != "overpass_ok":
            continue
        park_rows.append((float(p["act"]), weighted(r["parks"])))
        if "playgrounds" in r:
            play_rows.append((float(p["act"]), weighted(r["playgrounds"])))

    rows = park_rows
    values = fit(rows)
    # Split-half check: same fit on two interleaved halves, so the stability is recorded with the data.
    ordered = sorted(rows)
    halves = [fit(ordered[0::2], window=WINDOW // 2), fit(ordered[1::2], window=WINDOW // 2)]
    play_ordered = sorted(play_rows)
    doc = {
        "measure": "sum over parks within radius_m of exp(-decay_per_m * distance_m); median of catalog places at similar activity per acre",
        "decay_per_m": DECAY_PER_M,
        "radius_m": RADIUS_M,
        "x": "people plus jobs per gross acre in the 1 km around the pin",
        "interpolation": "log-log between knots; below the first knot and above the last, hold the end value",
        "knots": KNOTS,
        "expected_parks": values,
        "split_half": halves,
        "n_places": len(rows),
        "status": "empirical peer median, not a published standard; fit on 11 states with a private Overpass server",
        "window_places": WINDOW,
        # Same measure for playgrounds (0 to 5 point term): weighted count within radius_m, same knots and decay.
        "expected_playgrounds": fit(play_rows),
        "split_half_playgrounds": [fit(play_ordered[0::2], window=WINDOW // 2), fit(play_ordered[1::2], window=WINDOW // 2)],
        "n_places_playgrounds": len(play_rows),
    }
    with open(args.out, "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
