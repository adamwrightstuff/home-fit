"""
Natural Beauty V9 calibration analysis.

Groups catalog places by objective signals into character clusters,
compares current scores against subjective beauty expectations,
and tests formula variants to show cross-group impact.

Usage:
    python3 analysis/nb_calibration.py
"""
import json
import math
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Load catalog data
# ---------------------------------------------------------------------------

def load_places(fname: str, city: str) -> List[dict]:
    places = []
    with open(fname) as f:
        for line in f:
            p = json.loads(line)
            nb = p["score"]["livability_pillars"].get("natural_beauty", {})
            det = nb.get("details", {})
            vb = det.get("v9_breakdown", {})
            if not vb:
                continue
            inp = vb.get("inputs", {})
            places.append({
                "city": city,
                "name": p["catalog"]["name"],
                "ptype": p["catalog"].get("type", ""),
                "score": nb.get("score", 0) or 0,
                "gvi": vb.get("gvi_score") or 0,
                "water": vb.get("water_score") or 0,
                "canopy": vb.get("canopy_score") or 0,
                "topo": vb.get("topo_score") or 0,
                "landcover": vb.get("landcover_score") or 0,
                "bio": vb.get("bio_score") or 0,
                "water_type": inp.get("water_type") or "",
                "water_dist": inp.get("water_dist_km"),
            })
    return places


# ---------------------------------------------------------------------------
# Group classification
# ---------------------------------------------------------------------------

def classify(p: dict) -> str:
    wt = (p["water_type"] or "").lower()
    wd = p["water_dist"] or 99
    is_ocean = wt in ("ocean", "coastline", "coast", "bay")
    is_river = wt in ("river", "stream", "canal")

    # Ocean / coastal groups
    if is_ocean and wd < 0.5:
        if p["canopy"] > 30 or p["gvi"] > 40:
            return "ocean_front_wooded"
        return "ocean_front_open"
    if is_ocean and wd < 3.0:
        if p["canopy"] > 40 or p["gvi"] > 50:
            return "coastal_wooded"
        return "coastal_open"

    # Wooded groups (no significant ocean)
    if p["canopy"] > 60 and p["topo"] > 40:
        return "wooded_hilly"
    if p["canopy"] > 60:
        return "wooded_flat"
    if p["gvi"] > 70 and p["topo"] > 50:
        # High GVI + high topo = mountain-adjacent valley capturing background terrain
        return "mountain_adjacent"

    # River-adjacent
    if is_river and wd < 1.0:
        if p["gvi"] > 40:
            return "river_greenway"
        return "river_urban"

    # Dense urban (all signals low)
    if p["canopy"] < 15 and p["gvi"] < 25 and p["water"] < 40:
        return "dense_urban"

    # Catch-all
    return "suburban_inland"


# Expected score ranges per group: (label, lo, hi, note)
GROUP_EXPECTATIONS = {
    "ocean_front_open":    (65, 88, "Pacific/Atlantic beach city — exceptional water, minimal canopy"),
    "ocean_front_wooded":  (78, 95, "Beach + trees — top tier natural beauty"),
    "coastal_wooded":      (72, 93, "Near coast + leafy — classic beautiful suburb"),
    "coastal_open":        (55, 78, "Coastal but sparse canopy"),
    "wooded_hilly":        (78, 96, "Forested hills — dense leafy estate terrain"),
    "wooded_flat":         (65, 88, "Heavily treed flat suburb"),
    "mountain_adjacent":   (45, 68, "Valley near mountains — nice backdrop, not IN nature"),
    "river_greenway":      (40, 65, "Natural river corridor with vegetation"),
    "river_urban":         (20, 48, "Channelized/concrete river in urban area"),
    "dense_urban":         (5,  28, "Dense concrete urban, minimal nature"),
    "suburban_inland":     (28, 58, "Generic inland suburb"),
}


# ---------------------------------------------------------------------------
# Formula variants
# ---------------------------------------------------------------------------

def owa_score(components: List[float], weights: List[float]) -> float:
    ranked = sorted(components, reverse=True)
    return round(sum(w * s for w, s in zip(weights, ranked)), 2)


def v9_water(dist_km: Optional[float], water_type: str,
             river_max: float = 60.0, river_decay: float = 0.35,
             ocean_max: float = 100.0, ocean_decay: float = 0.20) -> float:
    if dist_km is None or not water_type:
        return 5.0
    wt = water_type.lower()
    if wt in ("ocean", "bay", "coastline", "coast"):
        m, d = ocean_max, ocean_decay
    elif wt in ("lake", "reservoir"):
        m, d = 70.0, 0.30
    else:
        m, d = river_max, river_decay
    if dist_km <= 0:
        return m
    return max(3.0, m * math.exp(-d * dist_km))


VARIANTS = {
    "current": {
        "owa": [0.50, 0.30, 0.15, 0.04, 0.01, 0.00],
        "river_max": 60.0, "river_decay": 0.35,
        "ocean_max": 100.0, "ocean_decay": 0.20,
        "gvi_canopy_ratio_cap": None,
    },
    # Raise top OWA weight to reward single-exceptional places (beach cities)
    "owa_heavy_top": {
        "owa": [0.62, 0.25, 0.10, 0.02, 0.01, 0.00],
        "river_max": 60.0, "river_decay": 0.35,
        "ocean_max": 100.0, "ocean_decay": 0.20,
        "gvi_canopy_ratio_cap": None,
    },
    # Cut river max score — concrete channels don't compete with ocean
    "river_cut": {
        "owa": [0.50, 0.30, 0.15, 0.04, 0.01, 0.00],
        "river_max": 40.0, "river_decay": 0.35,
        "ocean_max": 100.0, "ocean_decay": 0.20,
        "gvi_canopy_ratio_cap": None,
    },
    # GVI cap: when GVI >> canopy, background terrain is inflating the score.
    # Cap GVI at canopy * ratio_cap. Leaves genuine green neighborhoods untouched
    # (their GVI ≈ canopy); targets mountain-adjacent Valley neighborhoods.
    "gvi_cap": {
        "owa": [0.50, 0.30, 0.15, 0.04, 0.01, 0.00],
        "river_max": 60.0, "river_decay": 0.35,
        "ocean_max": 100.0, "ocean_decay": 0.20,
        "gvi_canopy_ratio_cap": 1.8,
    },
    # All three fixes together
    "v10": {
        "owa": [0.62, 0.25, 0.10, 0.02, 0.01, 0.00],
        "river_max": 40.0, "river_decay": 0.35,
        "ocean_max": 100.0, "ocean_decay": 0.20,
        "gvi_canopy_ratio_cap": 1.8,
    },
}


def score_place(p: dict, variant: dict) -> float:
    water = v9_water(
        p["water_dist"], p["water_type"],
        river_max=variant["river_max"],
        river_decay=variant["river_decay"],
        ocean_max=variant["ocean_max"],
        ocean_decay=variant["ocean_decay"],
    )
    gvi = p["gvi"]
    cap_ratio = variant.get("gvi_canopy_ratio_cap")
    if cap_ratio and p["canopy"] > 0 and gvi / p["canopy"] > cap_ratio:
        gvi = p["canopy"] * cap_ratio
    components = [gvi, water, p["canopy"], p["topo"], p["landcover"], p["bio"]]
    return owa_score(components, variant["owa"])


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def run_analysis(places: List[dict]):
    # Classify
    for p in places:
        p["group"] = classify(p)

    groups = sorted(set(p["group"] for p in places))

    # Header
    variant_names = list(VARIANTS.keys())
    col = 22
    print(f"\n{'Group':<22} {'N':>3} {'Target':>10} ", end="")
    for vn in variant_names:
        print(f" {vn:>12}", end="")
    print()
    print("-" * (22 + 4 + 11 + 13 * len(variant_names)))

    for grp in groups:
        members = [p for p in places if p["group"] == grp]
        n = len(members)
        lo, hi, _ = GROUP_EXPECTATIONS.get(grp, (0, 100, ""))
        print(f"\n{grp:<22} {n:>3}  [{lo:2d}–{hi:2d}]   ", end="")

        for vn, vparams in VARIANTS.items():
            scores = [score_place(p, vparams) for p in members]
            mean = sum(scores) / len(scores)
            in_range = sum(1 for s in scores if lo <= s <= hi)
            pct = in_range * 100 // n
            print(f"  {mean:5.1f} ({pct:3d}%)", end="")
        print()

        # Show worst offenders under current formula
        current_scores = [(score_place(p, VARIANTS["current"]), p) for p in members]
        current_scores.sort(key=lambda x: abs((x[0] - (lo + hi) / 2)), reverse=True)
        for sc, p in current_scores[:3]:
            delta = sc - (lo + hi) / 2
            flag = "▲" if delta > 15 else ("▼" if delta < -15 else " ")
            print(f"  {flag} {p['city']:3} {p['name']:<25} cur={sc:5.1f}  ", end="")
            for vn, vparams in VARIANTS.items():
                if vn == "current":
                    continue
                ns = score_place(p, vparams)
                diff = ns - sc
                print(f"  {vn}={ns:5.1f}({diff:+.1f})", end="")
            print()


if __name__ == "__main__":
    nyc = load_places("data/nyc_metro_place_catalog_scores_merged.jsonl", "NYC")
    la  = load_places("data/la_metro_place_catalog_scores_merged.jsonl",  "LA")
    all_places = nyc + la
    print(f"Loaded {len(nyc)} NYC + {len(la)} LA = {len(all_places)} places with V9 data")
    run_analysis(all_places)
