"""
Social Fabric pillar: stability (tract + place mobility), civic gathering (OSM),
and engagement (IRS BMF + voter turnout), z-scored vs area type where applicable.

Composite (fixed denominator): (1.2×Stability + 1.2×Civic + 1.0×Engagement) / 3.4.
Diversity is a separate pillar (pillars/diversity.py).

Stability blend: 0.7×tract same-house (B07003 tract) + 0.3×place same-house (Incorporated Place/CDP B07003).
Civic search radius follows tract population density: ~600 m / 1200 m / 3000 m.
Places API augments thin OSM (like neighborhood_amenities); imputed civic floor for dense areas if still empty.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Tuple

from data_sources import census_api, data_quality, osm_api
from data_sources import irs_bmf
from data_sources.places_social_fabric_client import maybe_augment_civic_nodes_with_places
from data_sources import social_fabric_bands
from data_sources import voter_turnout
from data_sources.us_census_divisions import get_division
from logging_config import get_logger

logger = get_logger(__name__)

_STATE_FIPS_TO_ABBREV = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "72": "PR",
}

_stability_baselines_path = os.getenv(
    "STABILITY_BASELINES_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stability_baselines.json"),
)
_stability_baselines: Dict[str, Dict[str, float]] = {}
if _stability_baselines_path and os.path.isfile(_stability_baselines_path):
    try:
        with open(_stability_baselines_path, "r") as f:
            raw = json.load(f)
        for k, v in (raw or {}).items():
            if isinstance(v, dict) and "mean" in v and "std" in v:
                _stability_baselines[str(k)] = {"mean": float(v["mean"]), "std": float(v["std"])}
        if _stability_baselines:
            logger.info("Loaded stability baselines for %d regions", len(_stability_baselines))
    except Exception as e:
        logger.warning("Failed to load stability baselines from %s: %s", _stability_baselines_path, e)


def _score_stability_from_pct(same_house_pct: float) -> float:
    try:
        x = float(same_house_pct)
    except (TypeError, ValueError):
        return 0.0
    if x <= 0:
        return 0.0
    if x <= 85.0:
        return max(0.0, min(100.0, (x / 85.0) * 100.0))
    score = 100.0 - 2.0 * (x - 85.0)
    return max(0.0, min(100.0, score))


def _score_stability_from_z(same_house_pct: float, mean: float, std: float, clip_z: float = 2.5) -> float:
    try:
        x = float(same_house_pct)
    except (TypeError, ValueError):
        return 0.0
    if std <= 0:
        return _score_stability_from_pct(x)
    z = (x - mean) / std
    z = max(-clip_z, min(clip_z, z))
    return max(0.0, min(100.0, ((z + clip_z) / (2 * clip_z)) * 100.0))


def _score_engagement_from_rate(orgs_per_1k: float, mean: float, std: float, clip_z: float = 2.5) -> float:
    try:
        v = float(orgs_per_1k)
    except (TypeError, ValueError):
        return 0.0
    if std <= 0:
        return 0.0
    z = (v - mean) / std
    z = max(-clip_z, min(clip_z, z))
    return max(0.0, min(100.0, ((z + clip_z) / (2 * clip_z)) * 100.0))


def _civic_radius_m_from_tract_density(density_sqmi: Optional[float]) -> int:
    """People per sq mi (tract) → OSM civic search radius."""
    if density_sqmi is None or density_sqmi <= 0:
        return 1200
    d = float(density_sqmi)
    if d >= 10_000:
        return 600
    if d >= 2500:
        return 1200
    return 3000


def _civic_imputed_floor_score(area_type: Optional[str], density: Optional[float]) -> Optional[float]:
    """
    Conservative civic_gathering score when OSM+Places yield zero nodes (NA-style urban/suburban floors).
    Density is people per sq mi (same as get_population_density).
    """
    d = float(density) if density is not None else 0.0
    should_apply = False
    if area_type in ("urban_core", "urban_residential", "suburban"):
        should_apply = True
    elif d > 1500:
        should_apply = True
    elif area_type is None and d > 1000:
        should_apply = True
    if not should_apply:
        return None
    if area_type == "urban_core":
        return 25.0
    if area_type == "urban_residential":
        return 20.0
    if area_type == "suburban":
        return 15.0
    if d > 5000:
        return 25.0
    if d > 2000:
        return 20.0
    if d > 1500:
        return 18.0
    return 15.0


def get_social_fabric_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    city: Optional[str] = None,
) -> Tuple[float, Dict]:
    tract = census_api.get_census_tract(lat, lon)
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density=density, city=city)

    civic_radius_m = _civic_radius_m_from_tract_density(density)
    bands = social_fabric_bands.load_bands()

    division_code = None
    if tract:
        state_fips = tract.get("state_fips")
        state_abbrev = _STATE_FIPS_TO_ABBREV.get(state_fips) if state_fips else None
        if state_abbrev:
            division_code = get_division(state_abbrev)

    def _get_mobility():
        return census_api.get_mobility_data(lat, lon, tract=tract)

    def _get_place_same_house():
        info = census_api.get_place_fips_for_coordinates(lat, lon)
        if not info:
            return None, None
        pct = census_api.get_place_same_house_pct(info["state_fips"], info["place_fips"])
        return info, pct

    def _get_civic():
        return osm_api.query_civic_nodes(lat, lon, radius_m=civic_radius_m)

    def _get_bmf():
        return irs_bmf.get_civic_orgs_per_1k(
            lat, lon, tract=tract, division_code=division_code, area_type=area_type
        )

    def _get_turnout():
        return voter_turnout.get_voter_turnout_score(tract=tract, area_type=area_type)

    with ThreadPoolExecutor(max_workers=5) as executor:
        f_m = executor.submit(_get_mobility)
        f_p = executor.submit(_get_place_same_house)
        f_c = executor.submit(_get_civic)
        f_b = executor.submit(_get_bmf)
        f_t = executor.submit(_get_turnout)
        mobility = f_m.result()
        place_info, place_same_house_pct = f_p.result()
        civic = f_c.result()
        bmf_result = f_b.result()
        turnout_result = f_t.result()

    if civic is None:
        civic = {
            "nodes": [],
            "source_status": "error",
            "error": {
                "source": "overpass",
                "code": "unavailable",
                "message": "Civic OSM query failed or timed out",
            },
        }

    expected_m = data_quality.data_quality_manager.get_expected_minimums(lat, lon, area_type or "suburban")
    civic_min = max(1, int(expected_m.get("civic_nodes_min") or 3))
    osm_cs_pre = civic.get("source_status")
    n_pre = len([x for x in (civic.get("nodes") or []) if isinstance(x, dict)])
    if osm_cs_pre == "error":
        civic_compl = 0.0
    else:
        civic_compl = min(1.0, float(n_pre) / float(civic_min))

    civic, places_civic_meta = maybe_augment_civic_nodes_with_places(
        civic,
        lat,
        lon,
        civic_radius_m,
        osm_completeness=civic_compl,
        civic_min_expected=civic_min,
    )
    if places_civic_meta.get("used") and places_civic_meta.get("http_ok"):
        logger.info(
            "Social Fabric Places civic augment: trigger=%s nodes_added=%s completeness_before=%s",
            places_civic_meta.get("trigger"),
            places_civic_meta.get("nodes_added"),
            places_civic_meta.get("osm_completeness_before"),
        )

    same_house_pct = mobility.get("same_house_pct") if mobility else None
    rooted_pct_adjusted = None
    stability_pct: Optional[float] = None
    if same_house_pct is not None:
        if place_same_house_pct is not None:
            stability_pct = 0.7 * float(same_house_pct) + 0.3 * float(place_same_house_pct)
        else:
            stability_pct = float(same_house_pct)

    stability_score = 0.0
    if stability_pct is not None:
        if bands:
            rooted_pct_adjusted = social_fabric_bands.adjust_rooted_pct_for_regional_bands(
                stability_pct, division_code, bands
            )
            stability_score = social_fabric_bands.score_stability_from_bands(
                stability_pct, division_code, bands
            )
        else:
            baseline = None
            if division_code and _stability_baselines:
                baseline = _stability_baselines.get(division_code) or _stability_baselines.get("all")
            if baseline:
                stability_score = _score_stability_from_z(stability_pct, baseline["mean"], baseline["std"])
            else:
                stability_score = _score_stability_from_pct(stability_pct)

    nodes = civic.get("nodes") or []
    civic_count = len(nodes)
    civic_band_key = social_fabric_bands.civic_band_area_type_for_radius(civic_radius_m)

    civic_imputed_floor_applied = False
    if civic_count <= 0:
        floor = _civic_imputed_floor_score(area_type, density)
        if floor is not None:
            civic_score = floor
            civic_imputed_floor_applied = True
        else:
            civic_score = 0.0
    elif bands:
        civic_score = social_fabric_bands.score_civic_gathering_from_bands(
            civic_count, civic_band_key, bands, proximity=False
        )
    else:
        if civic_count <= 2:
            civic_score = 40.0
        elif civic_count <= 5:
            civic_score = 70.0
        else:
            civic_score = 100.0

    bmf_score = None
    orgs_per_1k = None
    turnout_score = None
    turnout_rate = None

    if bmf_result is not None:
        orgs_per_1k, engagement_stats = bmf_result
        if engagement_stats and orgs_per_1k is not None:
            mean = engagement_stats.get("mean", 0.0)
            std = engagement_stats.get("std", 0.0)
            bmf_score = _score_engagement_from_rate(orgs_per_1k, mean, std)

    if turnout_result is not None:
        turnout_score, _stats_t, turnout_rate = turnout_result

    engagement_score: Optional[float] = None
    if bmf_score is not None and turnout_score is not None:
        engagement_score = 0.60 * bmf_score + 0.40 * turnout_score
    elif bmf_score is not None:
        engagement_score = bmf_score
    elif turnout_score is not None:
        engagement_score = turnout_score
    else:
        engagement_score = None

    e = float(engagement_score) if engagement_score is not None else 0.0
    raw = 1.2 * stability_score + 1.2 * civic_score + 1.0 * e
    score = max(0.0, min(100.0, round(raw / 3.4, 1)))

    source_status: Dict[str, str] = {}
    source_errors: list = []

    if mobility is not None:
        source_status["stability_mobility_acs"] = "ok"
    else:
        source_status["stability_mobility_acs"] = "error"
        if tract is None:
            source_errors.append(
                {
                    "source": "census",
                    "key": "tract_geocode",
                    "code": "no_tract",
                    "message": "Could not resolve Census tract for coordinates",
                }
            )
        else:
            source_errors.append(
                {
                    "source": "census",
                    "key": "b07003_mobility",
                    "code": "acs_unavailable",
                    "message": "ACS B07003 mobility data unavailable for this tract",
                }
            )

    source_status["stability_place"] = "ok" if place_same_house_pct is not None else "empty"

    # OSM outcome: after Places augment, `source_status` is effective (ok/empty) but
    # `osm_source_status` preserves Overpass result when Places ran.
    osm_cs = civic.get("osm_source_status") or civic.get("source_status")
    pm = civic.get("places_civic_fallback") or {}
    places_recovered = bool(pm.get("used") and pm.get("http_ok"))

    if pm.get("used") and pm.get("http_ok"):
        source_status["civic_places"] = "ok" if civic_count else "empty"
    else:
        source_status["civic_places"] = "not_used"

    if osm_cs == "error":
        source_status["civic_osm"] = "error"
        if not places_recovered:
            err = civic.get("error") or {}
            source_errors.append(
                {
                    "source": err.get("source", "overpass"),
                    "key": "civic_nodes",
                    "code": err.get("code", "error"),
                    "message": err.get("message", ""),
                }
            )
    elif osm_cs == "empty":
        source_status["civic_osm"] = "empty"
    elif osm_cs == "ok":
        source_status["civic_osm"] = "ok"
    else:
        source_status["civic_osm"] = "ok" if civic_count else "empty"

    if bmf_result is not None:
        _op1k, _eng_stats = bmf_result
        source_status["engagement_bmf"] = (
            "ok" if (_eng_stats and _op1k is not None) else "empty"
        )
    else:
        source_status["engagement_bmf"] = "empty"
    source_status["engagement_turnout"] = "ok" if turnout_result is not None else "empty"

    combined_data = {
        "stability_score": stability_score,
        "civic_score": civic_score,
        "engagement_score": engagement_score,
        "score": score,
        "mobility": mobility,
        "civic_nodes_count": civic_count,
        "civic_search_radius_m": civic_radius_m,
        "orgs_per_1k": orgs_per_1k,
        "source_status": source_status,
        "source_errors": source_errors,
        "places_civic_augmented": places_recovered,
        "civic_imputed_floor_applied": civic_imputed_floor_applied,
        "area_classification": {"area_type": area_type},
    }

    quality_metrics = data_quality.assess_pillar_data_quality(
        "social_fabric",
        combined_data,
        lat,
        lon,
        area_type,
        fallback_used=bool(places_recovered or civic_imputed_floor_applied),
    )

    rooted_pct = mobility.get("rooted_pct") if mobility else None

    breakdown = {
        "stability": stability_score,
        "civic_gathering": civic_score,
        "engagement": engagement_score,
    }

    summary = {
        "same_house_pct": round(same_house_pct, 1) if same_house_pct is not None else None,
        "place_same_house_pct": round(place_same_house_pct, 1) if place_same_house_pct is not None else None,
        "stability_blend_pct": round(stability_pct, 1) if stability_pct is not None else None,
        "rooted_pct": round(rooted_pct, 1) if rooted_pct is not None else None,
        "civic_node_count": civic_count,
        "civic_search_radius_m": civic_radius_m,
        "civic_band_tier": civic_band_key,
        "tract_population_density_sqmi": round(density, 1) if density else None,
        "engagement_available": engagement_score is not None,
        "orgs_per_1k": orgs_per_1k,
        "voter_turnout_rate": round(turnout_rate, 4) if turnout_rate is not None else None,
        "rooted_pct_adjusted_for_bands": round(rooted_pct_adjusted, 2) if rooted_pct_adjusted is not None else None,
        "social_fabric_bands": bool(bands),
        "civic_places_fallback_used": places_recovered,
        "civic_imputed_floor_applied": civic_imputed_floor_applied,
    }

    details = {
        "breakdown": breakdown,
        "summary": summary,
        "data_quality": quality_metrics,
        "source_status": source_status,
        "source_errors": source_errors,
        "area_classification": {"area_type": area_type},
        "version": "v8_places_civic_na_parity",
    }

    logger.info(
        "Social Fabric Score: %s/100 (stability=%s, civic=%s, engagement=%s, civic_nodes=%s@%sm, orgs_per_1k=%s)",
        score,
        stability_score,
        civic_score,
        engagement_score,
        civic_count,
        civic_radius_m,
        orgs_per_1k,
    )
    return score, details
