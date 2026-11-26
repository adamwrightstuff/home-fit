"""Catalog list and detail endpoints, served from the API so the Vercel frontend does not carry the catalog.

The catalog is ~111 MB of scored JSONL. Shipping it inside every frontend deployment (and inside the server functions
that read it) is what pushed the Vercel Hobby team over its storage limits. The frontend now rewrites
/api/catalog-map/all and /api/catalog-map?metro=X&key=Y to the two routes below.

  GET /catalog/list                    slimmed list of every live-metro place (what ?metro=all used to return)
  GET /catalog/place?metro=nyc&key=..  full detail for one place (what ?metro=X&key=Y used to return)

The list is built once at image build time (scripts/catalog/build_catalog_list.py) into data_cache/ as JSON plus a
gzip copy, and served as a static file, so a request never parses the catalog. Per-place detail parses one metro file
and keeps the last two parsed metros in memory.

The slimming rules below are a port of the former frontend/lib/catalogSlim.ts: drop heavy per-pillar detail, keep the
paths the list views read, and drop every key name that nothing in the frontend source mentions (UNUSED_KEYS, found by
searching app/, components/, lib/, hooks/ and contexts/ on 2026-11-24, excluding names that appear even as a fragment
of a longer string). Before adding a read of one of those names to a list-level view, remove it from UNUSED_KEYS.
"""
from __future__ import annotations

import gzip
import json
import logging
import math
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("HOMEFIT_DATA_DIR", str(ROOT / "data")))
CACHE_DIR = Path(os.getenv("HOMEFIT_CATALOG_CACHE_DIR", str(ROOT / "data_cache")))
LIST_JSON = CACHE_DIR / "catalog_list.json"
LIST_GZ = CACHE_DIR / "catalog_list.json.gz"
CACHE_CONTROL = "public, s-maxage=86400, stale-while-revalidate=604800"

_MISSING = object()

HEAVY_PILLAR_KEYS = ("breakdown", "details", "data_quality", "v9_breakdown")
KEEP_DATA_QUALITY = ("fallback_used", "reason", "degraded")
KEEP_PATHS: Dict[str, List[List[str]]] = {
    "active_outdoors": [
        ["breakdown", "daily_urban_outdoors"], ["breakdown", "wild_adventure"], ["breakdown", "waterfront_lifestyle"],
        ["breakdown", "waterfront_breakdown", "ocean_beach"], ["breakdown", "waterfront_breakdown", "lake_river"],
        ["breakdown", "waterfront_breakdown", "bay_harbor"],
    ],
    "quality_education": [
        ["breakdown", "split"], ["breakdown", "levels"], ["breakdown", "early_ed_bonus"], ["breakdown", "access_bonus"],
    ],
    "housing_value": [["breakdown", "space"], ["breakdown", "value_efficiency"]],
    "political_lean": [["breakdown", "lean_2024"], ["breakdown", "dem_pct_2024"]],
    # (social_fabric ["breakdown", "social_capital"] and active_outdoors waterfront_access were removed: nothing in the
    # frontend reads those names, so UNUSED_KEYS already dropped them.)
    "public_transit_access": [["breakdown", "commute_time"], ["details", "commute_time", "score"]],
    "natural_beauty": [
        ["v9_breakdown", "gvi_score"], ["v9_breakdown", "canopy_score"], ["v9_breakdown", "topo_score"],
        ["v9_breakdown", "landcover_score"], ["v9_breakdown", "bio_score"], ["v9_breakdown", "inputs", "gvi_pct"],
        ["v9_breakdown", "inputs", "canopy_pct"], ["v9_breakdown", "water_score"], ["v9_breakdown", "water_type"],
        ["v9_breakdown", "inputs", "water_type"],
    ],
}

UNUSED_KEYS = frozenset({
    '_rescore_version', 'access_level', 'activity_per_acre', 'activity_weighted_per_acre',
    'adaptive_weights', 'adjusted_weights', 'affordability_basis', 'affordability_rating',
    'age_percentile_basis', 'aian_nh', 'air_tmax_jja_normal_c', 'analysis_radius_note',
    'anchored_balance', 'appreciation_3yr', 'archetype_rule', 'area_bucket',
    'area_km2', 'area_method', 'area_sample', 'area_type_key',
    'asian_nh', 'atlas_civic_orgs_score', 'attendance_area', 'avg_snow_in',
    'base_context_weights', 'base_weights', 'baseline_contexts', 'baseline_fallback_metrics',
    'best_feature_dist_m', 'best_feature_type', 'biodiversity', 'black_nh',
    'blend_weight', 'bonus_breakdown', 'by_tier', 'cache_timestamp',
    'camping_25km_read', 'canopy_expectation', 'canopy_weights', 'census_available',
    'chains_included', 'channel_a_bonding', 'channel_a_source', 'channel_b_infra_density',
    'civic_band_tier', 'civic_data_mode', 'civic_density_per_km2', 'civic_effective_weighted',
    'civic_imputed_floor_applied', 'civic_osm', 'civic_places', 'civic_places_fallback_used',
    'civic_reliability', 'civic_search_radius_m', 'classification_confidence', 'climate_zone',
    'clinic_count', 'closest_business', 'cohesion', 'cohesion_area_type_band',
    'cohesion_clustering', 'cohesion_clustering_score', 'cohesion_resolution', 'cohesion_score',
    'cohesion_support_ratio', 'cohesion_support_score', 'combined_hybrid', 'combined_new',
    'component_scores', 'component_weights', 'components_missing', 'composite_score',
    'confidence_notes', 'context_adjustments', 'context_area_type', 'context_bonus',
    'context_bonus_applied', 'context_raw', 'context_weights', 'cost_per_room',
    'count_total', 'coverage_year', 'culture_leisure', 'culture_share',
    'culture_venues', 'daily_essentials', 'daily_refresh_2026_11_03', 'data_availability',
    'data_available', 'data_coverage', 'data_gaps', 'debug_breakdown',
    'debug_water_proximity', 'degraded_osm_substitute', 'degraded_reasons', 'degraded_warnings',
    'density_band', 'developed_pct', 'developed_pct_effective', 'developed_pct_raw',
    'developed_penalty_adjustment', 'dewpoint_f', 'distance_mi', 'diversity_score_mode',
    'downgrade_reason', 'downtown_center_distance_m', 'dpv2_recompute', 'dpv2_recompute_2026_11_02',
    'drive_minutes_source', 'early_ed_access', 'early_ed_note', 'economic_connectedness',
    'economic_connectedness_raw', 'effective_area_type', 'elevation_mean_m', 'elevation_p10_m',
    'elevation_p90_m', 'emergency_services', 'employment_source', 'employment_to_population_pct',
    'engagement_available', 'engagement_bmf', 'engagement_volunteering', 'enhancer_bonus',
    'enhancer_breakdown', 'estabs_per_1k', 'expectation_effect', 'extended_canopy_pct',
    'facility_radius_m', 'failure_reason', 'few_venues', 'fld_zone',
    'flood_label', 'flood_mapped_fraction', 'flood_method', 'flood_zone_score',
    'flood_zone_shares', 'forest_pct', 'form_context', 'gee_available',
    'gee_canopy_pct', 'geoid', 'green_space_ratio', 'green_view_details',
    'green_view_index', 'gvi_available', 'gvi_method_adjustment', 'gvi_metrics',
    'gvi_source', 'hangout_share', 'hangouts_5min', 'has_international_hub',
    'has_regional_airport', 'hispanic', 'home_space', 'households_150k_plus_share',
    'housing_type', 'impervious_available', 'income_brackets', 'independent_venues_1200m',
    'indices_version', 'industry_diversity_hhi', 'industry_shares_pct', 'irs_bmf_status',
    'job_access_score', 'job_access_status', 'job_category_overlays', 'landcover_developed_pct',
    'landcover_metrics', 'landcover_source', 'landscape_context', 'landscape_context_tags',
    'landscape_tags', 'leafy_suburb_contradiction', 'limits', 'local_canopy_pct',
    'local_green_spaces', 'local_lst_c', 'local_places_blocked', 'luxury_presence',
    'luxury_presence_detail', 'macro_2000m', 'market_quality_score', 'matched',
    'mean_weighted_routes', 'median_gross_rent', 'median_monthly_housing_cost', 'median_rooms',
    'metro_name', 'micro_400m', 'min_area_ha', 'min_per_km',
    'mix_source', 'multi_radius_available', 'multi_radius_canopy', 'natural_context',
    'near_water_reweight_applied', 'near_water_reweight_meta', 'nearest_airport_minutes', 'nearest_airports',
    'nearest_bus', 'nearest_commuter_rail_m', 'nearest_distance_km', 'nearest_hospital_name',
    'nearest_light_rail', 'nearest_pharmacy', 'nearest_pharmacy_km', 'nearest_type',
    'nearest_urgent_care', 'nearest_waterbody', 'neighborhood_1000m', 'neighborhood_beauty',
    'net_estab_entry_per_1k', 'nhpi_nh', 'orgs_per_1k', 'original_archetype',
    'original_archetype_rule', 'osm_down_score_cap', 'osm_id', 'osm_local_outcome',
    'osm_regional_outcome', 'osm_trail_outcome', 'osm_type', 'osm_with_places_fallback',
    'other_nh', 'overall_coverage', 'overall_tier', 'overpass',
    'overture', 'park_clean_count_2026_11_04', 'parks_query', 'participation_mix',
    'path_entries_dropped', 'pct_family', 'pct_low_density', 'penalty',
    'penalty_reduction', 'per_pillar_degraded', 'pin_sensitive', 'pin_sensitivity',
    'place_long_tenure_pct', 'place_same_house_pct', 'places_ao', 'plateau_min',
    'pm25_match', 'pm25_source', 'pm25_years', 'pooled_inputs',
    'population_25_plus', 'primary_source', 'primary_value', 'provisional_composite_score',
    'proximity_source', 'qcew_employment_growth_pct', 'qcew_employment_per_1k', 'race_ethnicity',
    'radius_m', 'regional_places_blocked', 'release', 'reliability',
    'relief_intensity_m_per_km2', 'rerun_inputs', 'residents_within_radius', 'rooms_per_100k',
    'rooted_pct', 'rooted_pct_adjusted_for_bands', 'rootedness', 'route_id',
    'routes_within_15km_removed', 'ruggedness_index_m', 'same_house_pct_b07003', 'same_house_pct_b07013',
    'scaled_total', 'scenic_bonus', 'scenic_proxy', 'scenic_viewshed_score',
    'scope', 'score_breakdown', 'score_method', 'seasonal_consistency',
    'seasonal_variation', 'selected_job_categories', 'service_level', 'services_retail',
    'shift_m', 'short_name', 'slope_max_deg', 'slope_mean_deg',
    'slope_p85_deg', 'slope_std_deg', 'social_capital', 'social_dining',
    'social_fabric_bands', 'social_fabric_version', 'source_counts', 'source_status',
    'specialized_care', 'stability_mobility_acs', 'stability_place', 'stability_tract_input',
    'station_id', 'steep_fraction', 'stored_breakdown', 'stored_count_total',
    'stored_count_within_5km', 'stored_daily', 'stored_score', 'stored_water',
    'stored_wild', 'street_level_ndvi', 'street_tree_canopy_blend', 'street_tree_dedup',
    'sunshine_pct', 'terrain_prominence_m', 'terrain_ruggedness_m', 'top_options',
    'topography', 'topography_base', 'topography_metrics', 'topography_raw',
    'total_businesses', 'total_park_area_ha', 'total_population', 'total_routes',
    'total_score_breakdown', 'total_stops', 'total_units', 'tract_long_tenure_pct',
    'tract_population_density_sqmi', 'trail_clean_count_2026_11_03', 'trail_routes_removed_2026_11_10', 'trajectory_rule',
    'transit_modes_available', 'tree_analysis', 'tree_base_score', 'tree_canopy_pct',
    'tree_canopy_pct_5km', 'trend_c_per_decade', 'triggered', 'turnout_in_engagement_blend',
    'turnout_source', 'two_plus_nh', 'uplift_debug_v7', 'urgent_care_count',
    'vegetation_health', 'vegetation_health_score', 'velocity_6mo', 'venues_total',
    'viewshed', 'viewshed_metrics', 'viewshed_pre_quality_gate', 'viewshed_quality',
    'viewshed_quality_gate', 'viewshed_quality_mult', 'viewshed_relief_m', 'visible_green_fraction',
    'visible_natural_pct', 'visible_natural_terrain_pct', 'volunteering_resolution', 'wage_p25_annual',
    'wage_p75_annual', 'warnings', 'water_density_km2', 'water_proximity_available',
    'water_proximity_type', 'water_source_confidence_adjustment', 'water_urban_guardrail', 'waterfront_access',
    'wealth_character', 'wealth_gap', 'weight_covered', 'weighted_canopy_pct',
    'weights_used', 'white_nh', 'wind_mph', 'within_5min_walk',
    'working_age',
})


# ---------------------------------------------------------------------------
# Slimming (port of frontend/lib/catalogSlim.ts)
# ---------------------------------------------------------------------------

def _pick(src: Any, path: List[str]) -> Any:
    cur = src
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return _MISSING
        cur = cur[k]
    return cur


def _assign(dst: Dict[str, Any], path: List[str], value: Any) -> None:
    cur = dst
    for k in path[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[path[-1]] = value


def _slim_pillar(key: str, pillar: Any) -> Any:
    if not isinstance(pillar, dict):
        return pillar
    out = {k: v for k, v in pillar.items() if k not in HEAVY_PILLAR_KEYS}
    dq = pillar.get("data_quality")
    if isinstance(dq, dict):
        out["data_quality"] = {k: dq[k] for k in KEEP_DATA_QUALITY if k in dq}
    for path in KEEP_PATHS.get(key, []):
        v = _pick(pillar, path)
        if v is not _MISSING:
            _assign(out, path, v)
    return out


def _drop_unused(value: Any) -> Any:
    if isinstance(value, list):
        return [_drop_unused(v) for v in value]
    if isinstance(value, dict):
        return {k: _drop_unused(v) for k, v in value.items() if k not in UNUSED_KEYS}
    return value


def slim_place(place: Dict[str, Any]) -> Dict[str, Any]:
    """List-sized copy of a catalog place. Never mutates the input."""
    score = place.get("score")
    pillars = score.get("livability_pillars") if isinstance(score, dict) else None
    if not isinstance(pillars, dict):
        return place
    slim_pillars = {k: _slim_pillar(k, v) for k, v in pillars.items()}
    new_score = _drop_unused({**score, "livability_pillars": slim_pillars})
    return {**place, "score": new_score}


# ---------------------------------------------------------------------------
# Loading (port of the loaders in frontend/lib/catalogMapServer.ts)
# ---------------------------------------------------------------------------

def live_metros() -> List[str]:
    """Live metro slugs in registry order (what the frontend's CATALOG_METROS lists)."""
    reg = json.loads((DATA_DIR / "metro_registry.json").read_text(encoding="utf-8"))["metros"]
    return [slug for slug, entry in reg.items() if entry.get("status") == "live"]


def row_key(catalog: Dict[str, Any]) -> str:
    return f"{catalog.get('name')}|{catalog.get('county_borough')}|{catalog.get('state_abbr')}"


def _plain_sum(values: Iterable[float]) -> float:
    """Left-to-right float addition like JavaScript's reduce; Python 3.12+ sum() compensates and can differ in the last bit."""
    total = 0.0
    for v in values:
        total += v
    return total


def _js_round(x: float, digits: int) -> float:
    """Math.round(x * 10**digits) / 10**digits, rounding halves up like JavaScript (floor(r + 0.5) can round up early)."""
    f = 10 ** digits
    r = x * f
    fl = math.floor(r)
    return (fl + 1 if r - fl >= 0.5 else fl) / f


@lru_cache(maxsize=1)
def _climate_index() -> Dict[str, Dict[str, float]]:
    path = DATA_DIR / "catalog_climate_profiles.jsonl"
    index: Dict[str, Dict[str, float]] = {}
    if not path.is_file():
        return index
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not row.get("source") or not row.get("name"):
                continue
            months = ((row.get("climate") or {}).get("months")) or []
            if not months:
                continue
            by_month = {m.get("month"): m for m in months}
            jan, jul = by_month.get(1) or {}, by_month.get(7) or {}
            if not jan.get("avg_temp_f") or not jul.get("avg_temp_f"):
                continue
            precip = _plain_sum((m.get("avg_precip_in") or 0) for m in months)
            solar = [m["solar_kwh_m2_day"] for m in months if m.get("solar_kwh_m2_day") is not None]
            avg_solar = _plain_sum(solar) / len(solar) if solar else 4.5
            index[f"{row['source']}::{row['name']}"] = {
                "jan_f": jan["avg_temp_f"],
                "jul_f": jul["avg_temp_f"],
                "swing_f": jul["avg_temp_f"] - jan["avg_temp_f"],
                "months_below_freezing": sum(1 for m in months if m.get("avg_temp_f") is not None and m["avg_temp_f"] < 32),
                "coldest_month_f": min(m["avg_temp_f"] for m in months if m.get("avg_temp_f") is not None),
                "annual_precip_in": _js_round(precip, 1),
                "avg_solar": _js_round(avg_solar, 2),
            }
    return index


@lru_cache(maxsize=1)
def _housing_costs() -> Dict[str, Any]:
    path = DATA_DIR / "catalog_housing_costs.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("places") or {}
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _surroundings() -> Dict[str, Any]:
    """Income and home value around each place (scripts/catalog/build_catalog_surroundings.py). Display only."""
    path = DATA_DIR / "catalog_surroundings.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("places") or {}
    except (OSError, ValueError):
        return {}


def _metro_file(metro: str) -> Path:
    return DATA_DIR / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"


def iter_metro_places(metro: str) -> Iterable[Dict[str, Any]]:
    """Full (unslimmed) catalog rows for one metro, joined with climate and housing cost, one at a time."""
    path = _metro_file(metro)
    if not path.is_file():
        return
    climate, housing, around = _climate_index(), _housing_costs(), _surroundings()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not row.get("success") or not row.get("catalog") or not row.get("score"):
                continue
            place: Dict[str, Any] = {
                "catalog": row["catalog"], "score": row["score"], "metro": metro,
                "cbd_transit_minutes": row.get("cbd_transit_minutes"),
                "cbd_transit_dest": row.get("cbd_transit_dest"),
                "work_commute": row.get("work_commute"),
            }
            clim = climate.get(f"{metro}_metro::{row['catalog'].get('name')}")
            if clim:
                place["climate"] = clim
            place["housing_cost"] = housing.get(f"{metro}::{row_key(row['catalog'])}")
            surroundings = around.get(f"{metro}::{row_key(row['catalog'])}")
            if surroundings:
                place["surroundings"] = surroundings
            yield place


@lru_cache(maxsize=2)
def _metro_index(metro: str) -> Dict[str, Dict[str, Any]]:
    return {row_key(p["catalog"]): p for p in iter_metro_places(metro)}


# ---------------------------------------------------------------------------
# The prebuilt list
# ---------------------------------------------------------------------------

_build_lock = threading.Lock()


def build_list_files(out_json: Optional[Path] = None, out_gz: Optional[Path] = None) -> Tuple[int, str]:
    """Write the slimmed all-metro list as JSON and gzip, one metro at a time. Returns (place count, source)."""
    out_json, out_gz = out_json or LIST_JSON, out_gz or LIST_GZ
    out_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_json, tmp_gz = out_json.with_suffix(".json.tmp"), out_gz.with_suffix(".gz.tmp")
    n, with_rows = 0, []
    with tmp_json.open("w", encoding="utf-8") as fj, gzip.open(tmp_gz, "wt", encoding="utf-8", compresslevel=6) as fz:
        def emit(s: str) -> None:
            fj.write(s)
            fz.write(s)
        emit('{"places":[')
        for metro in live_metros():
            found = False
            for place in iter_metro_places(metro):
                found = True
                emit(("," if n else "") + json.dumps(slim_place(place), separators=(",", ":"), ensure_ascii=False))
                n += 1
            if found:
                with_rows.append(metro)
        source = "all:" + "+".join(with_rows) if with_rows else "missing"
        emit('],"source":' + json.dumps(source) + "}")
    os.replace(tmp_json, out_json)
    os.replace(tmp_gz, out_gz)
    logger.info("catalog list built: %d places, source=%s", n, source)
    return n, source


def _ensure_list() -> None:
    if LIST_JSON.is_file() and LIST_GZ.is_file():
        return
    with _build_lock:
        if not (LIST_JSON.is_file() and LIST_GZ.is_file()):
            logger.warning("catalog list not prebuilt; building now (first request is slow)")
            build_list_files()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/catalog/list")
def catalog_list(request: Request):
    _ensure_list()
    headers = {"Cache-Control": CACHE_CONTROL, "Vary": "Accept-Encoding"}
    if "gzip" in request.headers.get("accept-encoding", "").lower():
        return FileResponse(LIST_GZ, media_type="application/json", headers={**headers, "Content-Encoding": "gzip"})
    return FileResponse(LIST_JSON, media_type="application/json", headers=headers)


@router.get("/catalog/place")
def catalog_place(metro: str = Query(...), key: str = Query(...)):
    metro = metro.lower()
    if metro not in live_metros():
        return JSONResponse({"error": "key needs a single metro"}, status_code=400)
    place = _metro_index(metro).get(key)
    if place is None:
        return JSONResponse({"error": "Place not found"}, status_code=404)
    return JSONResponse({"place": place}, headers={"Cache-Control": CACHE_CONTROL})
