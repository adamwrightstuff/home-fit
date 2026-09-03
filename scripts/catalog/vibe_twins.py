"""
Compute vibe-twin similarity across the catalog.

Vibe vector (per place, all normalized 0-1):
  scene, race_entropy, bachelor_pct, dem_pct, social_capital, gvi, water_score

Pre-filters (hard):
  - area_type must match
  - water bucket (coastal vs inland) must match

Weights derived from pairwise contribution analysis across 300 catalog places.
Water downweighted because pre-filter handles the binary coastal/inland split.
dem_pct downweighted because it correlates 0.49 with scene (progressive areas
have more cafes). Rootedness dropped (55% null). Participation dropped (1.4%
of pairwise distance).

Usage:
  PYTHONPATH=. python3 scripts/catalog/vibe_twins.py "Hoboken, NJ" --top 10
"""

import argparse
import json
import math
import sys
from pathlib import Path

CATALOG_FILES = [
    "data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    "data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]

COASTAL_TYPES = {"ocean", "bay", "river", "lake"}

WEIGHTS = {
    "scene":    2.0,
    "race":     1.5,
    "bach":     2.0,
    "dem_pct":  0.75,
    "s_cap":    1.5,
    "gvi":      1.5,
    "water":    0.75,
}


def safe_get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
        if d is None:
            return default
    return d


def extract_features(record):
    score = record.get("score", {})
    pillars = score.get("livability_pillars", {}) if isinstance(score, dict) else {}

    area_type = (
        safe_get(score, "data_quality_summary", "area_classification", "area_type")
        or safe_get(pillars, "social_fabric", "area_classification", "area_type")
        or safe_get(pillars, "diversity", "area_classification", "area_type")
    )

    scene = score.get("local_scene_score") if isinstance(score, dict) else None

    div = pillars.get("diversity", {})
    race = safe_get(div, "breakdown", "race_entropy")
    bach = safe_get(div, "education_attainment", "bachelor_pct")

    pl = pillars.get("political_lean", {})
    dem_pct = safe_get(pl, "breakdown", "dem_pct_2024")

    sf = pillars.get("social_fabric", {})
    s_cap = safe_get(sf, "breakdown", "social_capital")

    nb = pillars.get("natural_beauty", {})
    gvi = safe_get(nb, "v9_breakdown", "gvi_score")
    water = safe_get(nb, "v9_breakdown", "water_score")
    water_type = (
        safe_get(nb, "v9_breakdown", "inputs", "water_type")
        or safe_get(nb, "v9_breakdown", "water_type")
        or "none"
    )
    water_bucket = "coastal" if water_type in COASTAL_TYPES else "inland"

    return {
        "area_type": area_type,
        "water_bucket": water_bucket,
        "water_type": water_type,
        "scene": scene,
        "race": race,
        "bach": bach,
        "dem_pct": dem_pct,
        "s_cap": s_cap,
        "gvi": gvi,
        "water": water,
    }


def normalize(features):
    out = {}
    for k in ["scene", "race", "bach", "dem_pct", "s_cap", "gvi", "water"]:
        v = features.get(k)
        out[k] = (v / 100.0) if v is not None else 0.5
    return out


def weighted_distance(a, b):
    total = 0.0
    weight_sum = 0.0
    for k, w in WEIGHTS.items():
        diff = a[k] - b[k]
        total += w * diff * diff
        weight_sum += w
    return math.sqrt(total / weight_sum)


def load_places():
    places = []
    for path in CATALOG_FILES:
        p = Path(path)
        if not p.exists():
            print(f"Warning: {path} not found", file=sys.stderr)
            continue
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                cat = record.get("catalog", {})
                name = cat.get("name", "")
                state = cat.get("state_abbr", "")
                if not name:
                    continue
                feats = extract_features(record)
                places.append({
                    "name": name,
                    "state": state,
                    "label": f"{name}, {state}",
                    "features": feats,
                    "norm": normalize(feats),
                    "local_scene_bucket": record.get("score", {}).get("local_scene_bucket"),
                    "total_score": record.get("score", {}).get("total_score"),
                    "water_bucket": feats["water_bucket"],
                })
    return places


def find_query(places, query):
    q = query.lower()
    for p in places:
        if p["label"].lower() == q or p["name"].lower() == q:
            return p
    # fuzzy: name starts with
    for p in places:
        if p["name"].lower().startswith(q.split(",")[0].strip().lower()):
            return p
    return None


def compute_twins(query_place, all_places, top_n):
    qf = query_place["norm"]
    qa = query_place["features"]["area_type"]

    qwb = query_place["features"]["water_bucket"]
    candidates = [p for p in all_places if p["label"] != query_place["label"]]
    if qa:
        candidates = [p for p in candidates if p["features"]["area_type"] == qa]
    candidates = [p for p in candidates if p["features"]["water_bucket"] == qwb]

    scored = []
    for p in candidates:
        dist = weighted_distance(qf, p["norm"])
        similarity = max(0.0, 1.0 - dist)
        scored.append((similarity, dist, p))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Place name, e.g. 'Hoboken, NJ'")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    places = load_places()
    query_place = find_query(places, args.query)
    if not query_place:
        print(f"Place not found: {args.query}", file=sys.stderr)
        sys.exit(1)

    twins = compute_twins(query_place, places, args.top)

    if args.json:
        out = {
            "query": {
                "label": query_place["label"],
                "area_type": query_place["features"]["area_type"],
                "local_scene_bucket": query_place["local_scene_bucket"],
                "water_type": query_place["features"]["water_type"],
                "total_score": query_place["total_score"],
                "features": {k: round(v * 100, 1) for k, v in query_place["norm"].items()},
            },
            "twins": [
                {
                    "rank": i + 1,
                    "label": p["label"],
                    "similarity": round(sim * 100, 1),
                    "area_type": p["features"]["area_type"],
                    "local_scene_bucket": p["local_scene_bucket"],
                    "water_type": p["features"]["water_type"],
                    "total_score": p["total_score"],
                    "features": {k: round(v * 100, 1) for k, v in p["norm"].items()},
                }
                for i, (sim, dist, p) in enumerate(twins)
            ],
        }
        print(json.dumps(out, indent=2))
    else:
        qf = query_place["features"]
        print(f"\nVibe twins for: {query_place['label']}")
        print(f"  area_type={qf['area_type']}  water_bucket={qf['water_bucket']}  scene={query_place['local_scene_bucket']}")
        print(f"  scene={qf['scene']:.0f}  race={qf['race']:.0f}  bach={qf['bach']:.0f}  dem={qf['dem_pct']:.0f}  s_cap={qf['s_cap']:.0f}  gvi={qf['gvi']:.0f}  water={qf['water']:.0f}\n")
        print(f"{'Rank':<5} {'Place':<30} {'Sim%':<7} {'Scene':<10} {'Race':>6} {'Bach':>6} {'Dem':>5} {'SCap':>6} {'GVI':>5} {'Score':>6}")
        print("-" * 95)
        for i, (sim, dist, p) in enumerate(twins):
            pf = p["features"]
            print(f"{i+1:<5} {p['label']:<30} {sim*100:>5.1f}%  {(p['local_scene_bucket'] or 'n/a'):<10} {pf['race'] or 0:>6.0f} {pf['bach'] or 0:>6.0f} {pf['dem_pct'] or 0:>5.0f} {pf['s_cap'] or 0:>6.0f} {pf['gvi'] or 0:>5.0f} {p['total_score'] or 0:>6.1f}")


if __name__ == "__main__":
    main()
