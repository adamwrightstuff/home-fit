"""
Fetch live built_environment signals for V2 anchor places and score them with
the V2 calibrated scorer. Run from repo root:

    PYTHONPATH=. python3 scripts/manual/test_v2_beauty_anchor.py

Prints a before/after table: V1 (current catalog), V2 (new formula), expected range.
Takes ~10-15 min (one live OSM fetch per place).
"""

import json
import math
import os
import sys

# ── anchor set ────────────────────────────────────────────────────────────────
# (name, lat, lon, expected_range, catalog_score_or_None)
ANCHORS = [
    # HIGH — enclosed historic fabric
    ("West Village",      40.7352, -74.0040, "88-93",  100),
    ("SoHo",              40.7233, -74.0030, "85-90",  100),
    ("Brooklyn Heights",  40.6958, -73.9936, "82-88",   97),
    ("Park Slope",        40.6681, -73.9800, "80-88",   68),
    ("Carroll Gardens",   40.6799, -73.9990, "80-87",   78),
    # MID
    ("Financial District",40.7074, -74.0113, "52-65",  100),
    ("Hell's Kitchen",    40.7638, -73.9953, "58-68",  100),
    ("Battery Park City", 40.7116, -74.0155, "48-58",   44),
    ("Carnegie Hill",     40.7842, -73.9552, "68-78",   80),
    ("Williamsburg",      40.7081, -73.9571, "65-75",   93),
    ("Greenpoint",        40.7282, -73.9542, "72-82",   78),
    # Beautiful suburb
    ("Bronxville",        40.9387, -73.8327, "65-78",   73),
    # LOW — auto-dominant
    ("Hempstead",         40.7062, -73.6187, "28-42",   61),
    ("Flushing",          40.7673, -73.8330, "40-55",   68),
    ("Great Kills",       40.5530, -74.1507, "35-48",   81),
    # Calibration controls
    ("Beacon Hill",       42.3588, -71.0707, "85-92",  None),
    ("Savannah Historic", 32.0809, -81.0912, "82-92",  None),
    ("Tysons Corner",     38.9187, -77.2311, "20-32",  None),
    ("Schaumburg",        42.0334, -88.0834, "18-30",  None),
    ("Hudson Yards",      40.7536, -74.0019, "22-38",  None),
]

# ── imports ───────────────────────────────────────────────────────────────────
sys.path.insert(0, os.getcwd())

from data_sources import arch_diversity as ad
from pillars.built_environment import _fetch_historic_data
from data_sources.data_quality import get_contextual_tags
from data_sources import census_api
from pillars.architectural_beauty_calibrated import (
    compute_calibrated_architectural_beauty_score,
    compute_v2_architectural_beauty_score,
)


def fetch_signals(name, lat, lon):
    print(f"  fetching {name}...", flush=True)
    try:
        div = ad.compute_arch_diversity(lat, lon, radius_m=2000)
        # retry once on zero-coverage
        if not (div.get("built_coverage_ratio") or 0) > 0:
            _fresh = getattr(ad.compute_arch_diversity, "__wrapped__", ad.compute_arch_diversity)
            div = _fresh(lat, lon, radius_m=2000)

        hist = _fetch_historic_data(lat, lon, radius_m=2000)
        density = census_api.get_population_density(lat, lon) or 0.0

        # score_architectural_diversity_as_beauty gives us coverage_cap_metadata
        from data_sources.arch_diversity import score_architectural_diversity_as_beauty
        result = score_architectural_diversity_as_beauty(
            div.get("levels_entropy", 0),
            div.get("building_type_diversity", 0),
            div.get("footprint_area_cv", 0),
            "urban_core",
            density,
            div.get("built_coverage_ratio"),
            historic_landmarks=hist.get("historic_landmarks_count", 0),
            median_year_built=hist.get("median_year_built"),
            vintage_share=hist.get("vintage_pct"),
            lat=lat,
            lon=lon,
        )
        if isinstance(result, tuple):
            _, meta = result
        else:
            meta = {}

        median_year_built = hist.get("median_year_built")
        pre_1940_pct = (hist.get("year_built_data") or {}).get("pre_1940_pct")
        nrhp_count = hist.get("nrhp_count", 0)
        heritage_count = (meta.get("heritage_profile") or {}).get("count", 0)
        heritage_count_total = (heritage_count or 0) + (nrhp_count or 0)

        contextual_tags = get_contextual_tags(
            "urban_core", density,
            div.get("built_coverage_ratio"),
            median_year_built,
            hist.get("historic_landmarks_count", 0),
            levels_entropy=div.get("levels_entropy"),
            building_type_diversity=div.get("building_type_diversity"),
            footprint_area_cv=div.get("footprint_area_cv"),
            pre_1940_pct=pre_1940_pct,
            nrhp_count=nrhp_count or 0,
        )

        # Build HistoricCoherence (V1 path)
        coherence = (meta.get("age_coherence_signal") or 0) * 100.0
        if "historic" in contextual_tags:
            coherence = max(coherence, 92.0)
        if "rowhouse" in contextual_tags:
            _yr = int(median_year_built) if median_year_built else None
            _pre40 = float(pre_1940_pct or 0)
            if (_yr and _yr <= 1955) or _pre40 >= 10.0 or (nrhp_count or 0) >= 7:
                coherence = max(coherence, 95.0)

        block_grain = meta.get("block_grain") or 0
        block_size_m = max(60.0, min(700.0, 420.0 - 3.5 * block_grain)) if block_grain else None
        frontage = meta.get("streetwall_continuity") or 0

        v1_row = {
            "height_diversity":    div.get("levels_entropy", 0),
            "type_diversity":      div.get("building_type_diversity", 0),
            "footprint_variation": div.get("footprint_area_cv", 0),
            "built_coverage":      div.get("built_coverage_ratio", 0),
            "ParkingFraction":     meta.get("parking_share_estimate"),
            "BlockSize":           block_size_m,
            "FrontageContinuity":  frontage,
            "HistoricCoherence":   coherence,
        }

        v2_row = {
            "height_diversity":    div.get("levels_entropy", 0),
            "type_diversity":      div.get("building_type_diversity", 0),
            "footprint_variation": div.get("footprint_area_cv", 0),
            "built_coverage":      div.get("built_coverage_ratio", 0),
            "StreetwallContinuity": frontage,
            "BlockGrain":           block_grain,
            "SetbackConsistency":   meta.get("setback_consistency") or 0,
            "HeritageCount":        heritage_count_total,
            "Density":              density,
            "MedianYearBuilt":      median_year_built,
            "ParkingFraction":      meta.get("parking_share_estimate"),
            "BlockSize":            block_size_m,
        }

        return {
            "v1_row": v1_row, "v2_row": v2_row,
            "sw": frontage, "bg": block_grain,
            "sb": meta.get("setback_consistency") or 0,
            "coverage": div.get("built_coverage_ratio", 0),
            "density": density,
            "myr": median_year_built,
            "nrhp": nrhp_count, "hpc": heritage_count,
            "tags": contextual_tags,
        }
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def main():
    print(f"\nFetching live signals for {len(ANCHORS)} anchor places...\n")
    results = []
    for name, lat, lon, exp, was in ANCHORS:
        sigs = fetch_signals(name, lat, lon)
        if sigs is None:
            results.append((name, exp, was, None, None, None))
            continue
        v1 = compute_calibrated_architectural_beauty_score(sigs["v1_row"])
        v2 = compute_v2_architectural_beauty_score(sigs["v2_row"])
        results.append((name, exp, was, v1, v2, sigs))

    print(f"\n{'Place':25s} {'V1':>5} {'V2':>5}  {'Expected':>10}  {'Cat':>5}  {'sw':>5} {'bg':>5} {'sb':>5} {'c':>5}")
    print("-" * 90)
    ok_v1 = ok_v2 = 0
    for name, exp, was, v1, v2, sigs in results:
        if v1 is None:
            print(f"{name:25s}  FAILED")
            continue
        lo, hi = map(int, exp.split("-"))
        v1_ok = lo <= v1 <= hi
        v2_ok = lo <= v2 <= hi
        if v1_ok: ok_v1 += 1
        if v2_ok: ok_v2 += 1
        was_str = f"{was:.0f}" if was else " --"
        flag = "" if v2_ok else " <<<"
        print(
            f"{name:25s} {v1:5.1f} {v2:5.1f}  {exp:>10}  {was_str:>5}"
            f"  {sigs['sw']:5.1f} {sigs['bg']:5.1f} {sigs['sb']:5.1f} {sigs['coverage']:5.3f}"
            f"{flag}"
        )

    total = sum(1 for r in results if r[3] is not None)
    print(f"\nV1: {ok_v1}/{total} in range   V2: {ok_v2}/{total} in range")
    print("\nRaw signal dump (for tuning):")
    for name, exp, was, v1, v2, sigs in results:
        if sigs:
            print(f"  {name}: density={sigs['density']:.0f} myr={sigs['myr']} "
                  f"nrhp={sigs['nrhp']} hpc={sigs['hpc']} tags={sigs['tags']}")


if __name__ == "__main__":
    main()
