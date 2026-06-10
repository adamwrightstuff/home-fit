"""
Simulate V10 natural beauty scores across both catalogs.

Three changes vs V9:
  1. OWA weights: [0.62, 0.25, 0.10, 0.02, 0.01, 0.00]  (heavy top — rewards single exceptional signals)
  2. River max_score: 60 → 40                             (concrete channels don't compete with ocean)
  3. Ocean→Bay reclassify: places with water_type='ocean'
     that are on enclosed tidal harbor (not open ocean/sound) → 'bay'
     Bay scoring: max=70, decay=0.30 vs ocean max=100, decay=0.20

Bay reclassification rule:
  If water_type='ocean' AND the place coordinates are within an inner-harbor
  bounding box (i.e. Manhattan island, known to be East River / Hudson only),
  reclassify to 'bay'. Long Island Sound, Pacific Ocean, Atlantic coast → unchanged.
"""
import json, math
from typing import Optional

# ---------------------------------------------------------------------------
# Bounding boxes for known tidal-channel zones that OSM tags as coastline
# ---------------------------------------------------------------------------
INNER_HARBOR_BOXES = [
    # Manhattan island — East River and Hudson tagged natural=coastline
    {"name": "Manhattan",  "lat": (40.68, 40.88), "lon": (-74.02, -73.91)},
]

def is_inner_harbor(lat: float, lon: float) -> bool:
    for box in INNER_HARBOR_BOXES:
        if box["lat"][0] <= lat <= box["lat"][1] and box["lon"][0] <= lon <= box["lon"][1]:
            return True
    return False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def v9_water(dist: Optional[float], wt: str,
             river_max=60.0, river_decay=0.35,
             ocean_max=100.0, ocean_decay=0.20,
             bay_max=70.0, bay_decay=0.30) -> float:
    if dist is None or not wt:
        return 5.0
    wt = wt.lower()
    if wt in ("ocean",):
        m, d = ocean_max, ocean_decay
    elif wt in ("bay", "coastline", "coast"):
        m, d = bay_max, bay_decay
    elif wt in ("lake", "reservoir"):
        m, d = 70.0, 0.30
    else:
        m, d = river_max, river_decay
    return max(3.0, m * math.exp(-d * dist)) if dist > 0 else m


def owa(components, weights):
    return round(sum(w * s for w, s in zip(weights, sorted(components, reverse=True))), 1)


def score_vb(vb: dict, lat: float, lon: float,
             weights, river_max=60, reclassify_harbor=False) -> dict:
    inp = vb.get("inputs", {})
    wt  = inp.get("water_type") or ""
    wd  = inp.get("water_dist_km")

    effective_wt = wt
    if reclassify_harbor and wt.lower() in ("ocean", "coastline", "coast") and is_inner_harbor(lat, lon):
        effective_wt = "bay"

    water  = v9_water(wd, effective_wt, river_max=river_max)
    gvi    = vb.get("gvi_score") or 0
    canopy = vb.get("canopy_score") or 0
    topo   = vb.get("topo_score") or 0
    lc     = vb.get("landcover_score") or 0
    bio    = vb.get("bio_score") or 0

    return {
        "score": owa([gvi, water, canopy, topo, lc, bio], weights),
        "water_score": round(water, 1),
        "water_type_used": effective_wt,
        "reclassified": effective_wt != wt,
    }


V9_OWA  = [0.50, 0.30, 0.15, 0.04, 0.01, 0.00]
V10_OWA = [0.62, 0.25, 0.10, 0.02, 0.01, 0.00]


# ---------------------------------------------------------------------------
# Load + simulate
# ---------------------------------------------------------------------------

def load_and_simulate(fname: str, city: str):
    rows = []
    with open(fname) as f:
        for line in f:
            p = json.loads(line)
            cat = p["catalog"]
            nb  = p["score"]["livability_pillars"].get("natural_beauty", {})
            vb  = nb.get("details", {}).get("v9_breakdown", {})
            if not vb:
                continue
            lat = float(p["score"]["coordinates"]["lat"])
            lon = float(p["score"]["coordinates"]["lon"])

            v9  = score_vb(vb, lat, lon, V9_OWA,  river_max=60, reclassify_harbor=False)
            v10 = score_vb(vb, lat, lon, V10_OWA, river_max=40, reclassify_harbor=True)

            rows.append({
                "city": city,
                "name": cat["name"],
                "type": cat.get("type", ""),
                "lat": lat, "lon": lon,
                "v9":  v9["score"],
                "v10": v10["score"],
                "delta": round(v10["score"] - v9["score"], 1),
                "water_v9":  round((vb.get("water_score") or 0), 1),
                "water_v10": v10["water_score"],
                "wt_v9":  (vb.get("inputs", {}).get("water_type") or ""),
                "wt_v10": v10["water_type_used"],
                "reclassified": v10["reclassified"],
            })
    return rows


if __name__ == "__main__":
    nyc = load_and_simulate("data/nyc_metro_place_catalog_scores_merged.jsonl", "NYC")
    la  = load_and_simulate("data/la_metro_place_catalog_scores_merged.jsonl",  "LA")
    all_rows = nyc + la

    # --- Reclassified places ---
    reclassified = [r for r in all_rows if r["reclassified"]]
    if reclassified:
        print("RECLASSIFIED ocean→bay:")
        for r in sorted(reclassified, key=lambda x: x["name"]):
            print(f"  {r['city']} {r['name']:<25}  water {r['water_v9']:5.1f}→{r['water_v10']:5.1f}  score {r['v9']:5.1f}→{r['v10']:5.1f} ({r['delta']:+.1f})")
        print()

    # --- Notable places ---
    notable = {
        "Manhattan Beach", "Venice", "Hermosa Beach", "Redondo Beach",
        "Coney Island", "Rockaway Beach", "Brighton Beach", "Belmont Shore",
        "Studio City", "Sherman Oaks", "Encino", "Tarzana", "Hollywood Hills",
        "Bel Air", "Pacific Palisades", "Rancho Palos Verdes", "Palos Verdes Estates",
        "Beverly Hills", "Hancock Park", "Larchmont Village", "Westwood",
        "Chinatown", "Tribeca", "Battery Park City", "Lower East Side",
        "Bedford", "Westport", "Darien", "Chappaqua", "South Orange", "Ardsley",
        "Borough Park", "Elmhurst", "Watts", "Compton",
        "Elysian Valley", "Frogtown", "Atwater Village", "Arts District",
    }

    print(f"{'':2}{'Place':<24} {'City':<5} {'V9':>6} {'V10':>6} {'Δ':>6}  {'Water V9→V10'}")
    print("─" * 80)
    for r in sorted(all_rows, key=lambda x: x["name"]):
        if r["name"] not in notable:
            continue
        arrow = "▲" if r["delta"] > 5 else ("△" if r["delta"] > 2 else ("▼" if r["delta"] < -5 else ("▽" if r["delta"] < -2 else "✓")))
        wt_note = f"{r['wt_v9']}→{r['wt_v10']}" if r["reclassified"] else r["wt_v9"]
        print(f"{arrow} {r['name']:<24} {r['city']:<5} {r['v9']:>6.1f} {r['v10']:>6.1f} {r['delta']:>+6.1f}  {wt_note}  w:{r['water_v9']:.0f}→{r['water_v10']:.0f}")

    # --- Biggest movers ---
    print()
    print("BIGGEST GAINERS:")
    for r in sorted(all_rows, key=lambda x: -x["delta"])[:12]:
        print(f"  {r['delta']:>+5.1f}  {r['v9']:5.1f}→{r['v10']:5.1f}  {r['city']} {r['name']}")

    print()
    print("BIGGEST LOSERS:")
    for r in sorted(all_rows, key=lambda x: x["delta"])[:12]:
        print(f"  {r['delta']:>+5.1f}  {r['v9']:5.1f}→{r['v10']:5.1f}  {r['city']} {r['name']}")

    # --- Group summary ---
    print()
    print(f"{'Group':<28} {'N':>3}  {'V9 mean':>8}  {'V10 mean':>9}  {'Δ':>6}")
    print("─" * 65)
    groups = {
        "Ocean beach city (LA Pacific)": lambda r: r["city"]=="LA" and r["wt_v9"]=="ocean" and float(r.get("water_v9",0))>70,
        "Ocean beach city (NYC Atlantic)": lambda r: r["city"]=="NYC" and r["wt_v9"]=="ocean" and not is_inner_harbor(r["lat"],r["lon"]),
        "Manhattan harbor (reclassified)": lambda r: r["reclassified"],
        "LA River adjacent (river<1km)":  lambda r: r["city"]=="LA" and r["wt_v9"]=="river" and (r.get("water_v9",0) or 0)>40,
        "Wooded suburban (NYC)":          lambda r: r["city"]=="NYC" and r["type"]=="suburb" and r["v9"]>75,
        "Dense urban (low score)":        lambda r: r["v9"] < 30 and r["delta"] > -3,
    }
    for label, fn in groups.items():
        members = [r for r in all_rows if fn(r)]
        if not members:
            continue
        mv9  = sum(r["v9"]  for r in members) / len(members)
        mv10 = sum(r["v10"] for r in members) / len(members)
        print(f"  {label:<28} {len(members):>3}  {mv9:>8.1f}  {mv10:>9.1f}  {mv10-mv9:>+6.1f}")
