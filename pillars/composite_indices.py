"""
Composite indices: single module for Longevity, Status Signal, and Happiness.

All formulas and version tags live here so API responses stay the source of truth.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Longevity Index (Blue Zone–inspired fixed weights on six pillars)
# ---------------------------------------------------------------------------
LONGEVITY_INDEX_WEIGHTS: Dict[str, float] = {
    "social_fabric": 40.0,
    "neighborhood_amenities": 25.0,
    "active_outdoors": 15.0,
    "natural_beauty": 10.0,
    "climate_risk": 8.0,
    "quality_education": 2.0,
}

INDEX_VERSION_LONGEVITY = "2"
INDEX_VERSION_STATUS = "2"
INDEX_VERSION_HAPPINESS = "2"

INDICES_VERSION_METADATA = {
    "longevity": INDEX_VERSION_LONGEVITY,
    "status_signal": INDEX_VERSION_STATUS,
    "happiness": INDEX_VERSION_HAPPINESS,
}


def compute_longevity_index(
    livability_pillars: Dict[str, Any],
    token_allocation: Optional[Dict[str, float]] = None,
    only_pillars: Optional[Set[str]] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Longevity Index 0–100 from livability_pillars using LONGEVITY_INDEX_WEIGHTS.

    With token_allocation: renormalize over eligible longevity pillars (weight > 0 or
    pillar was in only_pillars partial run). Fallback: any longevity pillar with a score.
    Without token_allocation: all six pillars, missing score = 0.
    """
    contributions: Dict[str, float] = {}
    if token_allocation is not None:

        def _has_score(p: str) -> bool:
            raw = (livability_pillars.get(p) or {}).get("score")
            return raw is not None and isinstance(raw, (int, float))

        def _eligible(p: str) -> bool:
            has_weight = (float(token_allocation.get(p, 0.0) or 0.0) > 0)
            was_requested = only_pillars is not None and p in only_pillars
            return _has_score(p) and (has_weight or was_requested)

        eligible: List[str] = [p for p in LONGEVITY_INDEX_WEIGHTS if _eligible(p)]
        if not eligible:
            eligible = [p for p in LONGEVITY_INDEX_WEIGHTS if _has_score(p)]
        if not eligible:
            return 0.0, contributions
        total_weight = sum(LONGEVITY_INDEX_WEIGHTS[p] for p in eligible)
        if total_weight <= 0:
            return 0.0, contributions
        total = 0.0
        for p in eligible:
            score = float((livability_pillars.get(p) or {}).get("score", 0.0) or 0.0)
            weight_pct = LONGEVITY_INDEX_WEIGHTS[p] / total_weight
            contrib = score * weight_pct
            contributions[p] = round(contrib, 2)
            total += contrib
        return round(total, 2), contributions

    total = 0.0
    for pillar, weight in LONGEVITY_INDEX_WEIGHTS.items():
        score = float((livability_pillars.get(pillar) or {}).get("score", 0.0) or 0.0)
        contrib = score * weight / 100.0
        contributions[pillar] = round(contrib, 2)
        total += contrib
    return round(total, 2), contributions


LONGEVITY_INDEX_PILLAR_KEYS = frozenset(LONGEVITY_INDEX_WEIGHTS.keys())


def should_emit_longevity_index(only_pillars: Optional[Set[str]]) -> bool:
    """
    Full-score responses always include longevity_index.

    Partial ``only=`` runs omit it unless all six longevity pillars were requested,
    so a single pillar (e.g. schools at 100) cannot dominate the index.
    """
    if only_pillars is None:
        return True
    return LONGEVITY_INDEX_PILLAR_KEYS.issubset(only_pillars)


def attach_indices_version(response: Dict[str, Any]) -> None:
    """Merge indices_version into response metadata (idempotent)."""
    md = response.get("metadata")
    if md is None or not isinstance(md, dict):
        md = {}
        response["metadata"] = md
    iv = md.setdefault("indices_version", {})
    if isinstance(iv, dict):
        iv.update(INDICES_VERSION_METADATA)


def backfill_status_happiness_if_missing(response: Dict[str, Any]) -> None:
    """
    If status_signal or happiness_index is missing but pillars + coords allow it, compute and set.
    Mirrors previous main.py cache-hit logic (amenities required for the shared try block).
    """
    from pillars.happiness_index import compute_happiness_index_with_breakdown
    from pillars.status_signal import compute_status_signal_with_breakdown

    coords = response.get("coordinates") or {}
    lat, lon = coords.get("lat"), coords.get("lon")
    loc = response.get("location_info") or {}
    state = loc.get("state")
    city = (loc.get("city") or "").strip() or None
    pillars = response.get("livability_pillars") or {}
    housing = pillars.get("housing_value")
    social = pillars.get("social_fabric")
    diversity_details = pillars.get("diversity")
    if not isinstance(diversity_details, dict):
        diversity_details = None
    econ = pillars.get("economic_security")
    amenities = pillars.get("neighborhood_amenities")
    if (
        lat is None
        or lon is None
        or not housing
        or not econ
        or not amenities
    ):
        return
    if not social and not diversity_details:
        return

    try:
        from data_sources import census_api as _ca

        census_tract = _ca.get_census_tract(float(lat), float(lon))
    except Exception:
        census_tract = None

    try:
        if response.get("status_signal") is None:
            business_list = (amenities.get("breakdown") or {}).get("business_list") or amenities.get("business_list") or []
            lat_f = float(lat) if isinstance(lat, (int, float)) else None
            lon_f = float(lon) if isinstance(lon, (int, float)) else None
            result = compute_status_signal_with_breakdown(
                housing,
                social,
                econ,
                business_list,
                census_tract,
                state,
                city=city,
                lat=lat_f,
                lon=lon_f,
                diversity_details=diversity_details,
            )
            if result is not None:
                score, breakdown = result
                if score is not None:
                    response["status_signal"] = max(0.0, min(100.0, float(score)))
                response["status_signal_breakdown"] = breakdown
        if response.get("happiness_index") is None:
            hi = compute_happiness_index_with_breakdown(
                housing,
                pillars.get("public_transit_access"),
                econ,
                pillars.get("natural_beauty"),
                state,
                social_fabric_details=social,
            )
            if hi is not None:
                hi_score, hi_breakdown = hi
                if hi_score is not None:
                    response["happiness_index"] = max(0.0, min(100.0, float(hi_score)))
                response["happiness_index_breakdown"] = hi_breakdown
    except Exception:
        pass


def recompute_composites_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recompute longevity, status_signal, happiness from stored pillar JSON (no pillar re-run).
    """
    from pillars.happiness_index import compute_happiness_index_with_breakdown
    from pillars.status_signal import compute_status_signal_with_breakdown

    pillars: Dict[str, Any] = payload.get("livability_pillars") or {}
    location_info = payload.get("location_info") or {}
    coordinates = payload.get("coordinates") or {}
    token_allocation = payload.get("token_allocation")

    state = (location_info.get("state") or "").strip() or None
    lat, lon = coordinates.get("lat"), coordinates.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        lat, lon = float(lat), float(lon)
    else:
        lat, lon = None, None

    out: Dict[str, Any] = {
        "longevity_index": None,
        "longevity_index_contributions": None,
        "status_signal": None,
        "status_signal_breakdown": None,
        "happiness_index": None,
        "happiness_index_breakdown": None,
        "indices_version": dict(INDICES_VERSION_METADATA),
    }

    try:
        li, contrib = compute_longevity_index(
            pillars,
            token_allocation=token_allocation,
            only_pillars=None,
        )
        out["longevity_index"] = round(li, 2)
        out["longevity_index_contributions"] = contrib
    except Exception:
        pass

    census_tract = None
    if lat is not None and lon is not None:
        try:
            from data_sources import census_api as _ca

            census_tract = _ca.get_census_tract(lat, lon)
        except Exception:
            pass

    housing = pillars.get("housing_value")
    social = pillars.get("social_fabric")
    diversity_details = pillars.get("diversity")
    if not isinstance(diversity_details, dict):
        diversity_details = None
    econ = pillars.get("economic_security")
    amenities = pillars.get("neighborhood_amenities") or {}
    _city = (location_info.get("city") or "").strip() or None

    if housing and econ and (social or diversity_details):
        try:
            business_list = (amenities.get("breakdown") or {}).get("business_list") or amenities.get("business_list") or []
            result = compute_status_signal_with_breakdown(
                housing,
                social,
                econ,
                business_list,
                census_tract,
                state,
                city=_city,
                lat=lat,
                lon=lon,
                diversity_details=diversity_details,
            )
            if result is not None:
                score, breakdown = result
                if score is not None:
                    out["status_signal"] = max(0.0, min(100.0, float(score)))
                out["status_signal_breakdown"] = breakdown
        except Exception:
            pass

    try:
        happiness_result = compute_happiness_index_with_breakdown(
            housing,
            pillars.get("public_transit_access"),
            econ,
            pillars.get("natural_beauty"),
            state,
            social_fabric_details=social,
        )
        if happiness_result is not None:
            hi_score, hi_breakdown = happiness_result
            if hi_score is not None:
                out["happiness_index"] = max(0.0, min(100.0, float(hi_score)))
            out["happiness_index_breakdown"] = hi_breakdown
    except Exception:
        pass

    return out
