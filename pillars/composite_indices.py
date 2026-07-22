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
    "social_fabric": 35.0,       # Holt-Lunstad (2015): social isolation = 29% mortality increase
    "active_outdoors": 22.0,     # Li (2019 JAMA, 900k): greenspace → 12-24% lower all-cause mortality; Kokkinos (2022 NEJM): fitness = top longevity predictor
    "neighborhood_amenities": 15.0,  # Blue Zone "Move Naturally" walkability pathway; food access
    "healthcare_access": 10.0,   # RWJF 2023: 5-7yr life expectancy gap between highest/lowest primary care access counties
    "climate_risk": 8.0,         # Pope (2009): reducing fine particles → 0.61yr life expectancy gain
    "natural_beauty": 5.0,       # Independent stress-reduction / cortisol pathway; partially overlaps active_outdoors
    "quality_education": 3.0,    # Cutler & Lleras-Muney (2008): each year of education → 1.8% lower mortality
    "community_safety": 8.0,     # Trauma and chronic stress from crime are real mortality factors; renormalized when degraded
}

INDEX_VERSION_LONGEVITY = "2"
INDEX_VERSION_STATUS = "6"
INDEX_VERSION_HAPPINESS = "3"

INDICES_VERSION_METADATA = {
    "longevity": INDEX_VERSION_LONGEVITY,
    "status_signal": INDEX_VERSION_STATUS,
    "happiness": INDEX_VERSION_HAPPINESS,
}


def _area_type_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Morphological area_type from stored API score (data_quality_summary), if present."""
    dq = payload.get("data_quality_summary") or {}
    at = dq.get("area_type")
    if not (isinstance(at, str) and at.strip()):
        ac = dq.get("area_classification")
        if isinstance(ac, dict):
            at = ac.get("area_type")
    if isinstance(at, str) and at.strip():
        return at.strip()
    return None




def build_total_score_breakdown(
    livability_pillars: Dict[str, Any],
    token_allocation: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Per-pillar score / weight / contribution for catalog exporters and clients that expect
    ``total_score_breakdown`` alongside ``total_score``.
    """
    breakdown: Dict[str, Any] = {}
    ta = token_allocation or {}
    for name, pdata in (livability_pillars or {}).items():
        if not isinstance(pdata, dict):
            continue
        w = pdata.get("weight")
        if w is None:
            w = ta.get(name)
        breakdown[str(name)] = {
            "score": pdata.get("score"),
            "weight": w,
            "contribution": pdata.get("contribution"),
        }
    return breakdown


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
            has_weight = float(token_allocation.get(p, 0.0) or 0.0) > 0
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
    return round(min(100.0, total), 2), contributions


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
    zip_code = (loc.get("zip") or "").strip() or None
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

    area_type_bt = _area_type_from_payload(response)

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
                area_type=area_type_bt,
                zip_code=zip_code,
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
                community_safety_details=pillars.get("community_safety"),
                neighborhood_amenities_details=amenities,
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
    Recompute longevity, status_signal, happiness, and total_score from stored pillar JSON
    (no pillar re-run). Also applies stored-data corrections before computing composites:
      F15 — social fabric stability cliff suppressed for high-value markets.
      F19 — fabricated neighborhood_amenities scores (confidence=0) nullified.
      F02 — ghost weight redistribution; total_score recomputed with corrected weights.
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
        "longevity_index_breakdown": None,
        "status_signal": None,
        "status_signal_breakdown": None,
        "happiness_index": None,
        "happiness_index_breakdown": None,
        "total_score_breakdown": None,
        "total_score": None,
        "data_gaps": None,
        "indices_version": dict(INDICES_VERSION_METADATA),
    }

    # F15: Stability cliff tiebreaker from stored data.
    # stability_blend_pct > 85 in a high-value market (median_home_value >= $350k) means
    # community attachment, not captivity — suppress the cliff penalty.
    sf_data = pillars.get("social_fabric")
    hv_data = pillars.get("housing_value")
    if isinstance(sf_data, dict) and isinstance(hv_data, dict):
        sf_summary = sf_data.get("summary") or {}
        hv_summary = hv_data.get("summary") or {}
        stab_pct = sf_summary.get("stability_blend_pct")
        median_hv = hv_summary.get("median_home_value")
        sf_breakdown = sf_data.get("breakdown") or {}
        rootedness = sf_breakdown.get("rootedness")
        if (
            isinstance(stab_pct, (int, float))
            and stab_pct > 85.0
            and isinstance(median_hv, (int, float))
            and median_hv >= 350_000
            and isinstance(rootedness, (int, float))
        ):
            uncapped = min(100.0, (stab_pct / 85.0) * 100.0)
            if rootedness < uncapped:
                corrected_root = uncapped
                s_cap = float(sf_breakdown.get("social_capital") or 0.0)
                p_civ = float(sf_breakdown.get("peer_civic") or 0.0)
                part = float(sf_breakdown.get("participation") or 0.0)
                w_sc = 0.20 if s_cap > 0 else 0.0
                w_civic = 0.10 if p_civ > 0 else 0.0
                w_root = 0.10
                w_part = 1.0 - w_sc - w_civic - w_root
                new_raw = w_sc * s_cap + w_root * corrected_root + w_part * part + w_civic * p_civ
                sf_data["score"] = round(max(0.0, min(100.0, new_raw)), 1)
                sf_breakdown["rootedness"] = round(corrected_root, 1)
                # Update stored contribution so total_score recomputation picks up the fix.
                _sf_w = sf_data.get("weight")
                if isinstance(_sf_w, (int, float)):
                    sf_data["contribution"] = round(sf_data["score"] * _sf_w / 100.0, 4)

    # F19: Nullify fabricated neighborhood_amenities scores (confidence=0 with a score set).
    na_data = pillars.get("neighborhood_amenities")
    if isinstance(na_data, dict) and na_data.get("confidence") == 0 and na_data.get("score") is not None:
        na_data["score"] = None

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
    _zip = (location_info.get("zip") or "").strip() or None
    area_type_pl = _area_type_from_payload(payload)

    if housing and econ and (social or diversity_details):
        if census_tract is not None:
            # Full recompute: census tract available, baseline selection will be correct.
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
                    area_type=area_type_pl,
                    zip_code=_zip,
                )
                if result is not None:
                    score, breakdown = result
                    if score is not None:
                        out["status_signal"] = max(0.0, min(100.0, float(score)))
                    out["status_signal_breakdown"] = breakdown
            except Exception:
                pass
        else:
            # census_tract unavailable — recomputing status_signal without it would use the
            # national fallback baseline instead of the correct metro baseline (nyc_metro /
            # la_metro), producing badly wrong z-scores. Preserve the stored values instead.
            stored_ss = payload.get("status_signal")
            stored_ss_bd = payload.get("status_signal_breakdown")
            if stored_ss is not None:
                out["status_signal"] = stored_ss
            if stored_ss_bd is not None:
                out["status_signal_breakdown"] = stored_ss_bd

    try:
        happiness_result = compute_happiness_index_with_breakdown(
            housing,
            pillars.get("public_transit_access"),
            econ,
            pillars.get("natural_beauty"),
            state,
            social_fabric_details=social,
            community_safety_details=pillars.get("community_safety"),
            neighborhood_amenities_details=pillars.get("neighborhood_amenities"),
        )
        if happiness_result is not None:
            hi_score, hi_breakdown = happiness_result
            if hi_score is not None:
                out["happiness_index"] = max(0.0, min(100.0, float(hi_score)))
            out["happiness_index_breakdown"] = hi_breakdown
    except Exception:
        pass

    lic = out.get("longevity_index_contributions")
    if isinstance(lic, dict) and lic:
        out["longevity_index_breakdown"] = dict(lic)
    else:
        out["longevity_index_breakdown"] = {}

    try:
        out["total_score_breakdown"] = build_total_score_breakdown(pillars, token_allocation)
    except Exception:
        out["total_score_breakdown"] = {}

    # F02: Total score from stored contributions (authoritative) + recomputed for pillars
    # whose contribution was not stored.  Per-pillar weight is authoritative (it reflects
    # any redistribution that happened at original scoring time); token_allocation is the
    # fallback only when per-pillar weight is absent (None).
    #
    # Ghost weight redistribution applies to the recomputed-contribution pillars only:
    # if a pillar has no score (None) and a non-zero weight, zero its weight and
    # redistribute proportionally across the recomputed-contribution pillars.
    # Stored-contribution pillars are left as-is (they already baked in whatever
    # redistribution happened at scoring time).
    _stored_total = 0.0
    _recompute_weights: Dict[str, float] = {}

    for p_name, p_data in (pillars or {}).items():
        if not isinstance(p_data, dict):
            continue
        contrib = p_data.get("contribution")
        if isinstance(contrib, (int, float)):
            _stored_total += float(contrib)
        else:
            # Contribution not stored — recompute from weight × score.
            # Per-pillar weight takes precedence; token_allocation is the fallback.
            w = p_data.get("weight")
            if not isinstance(w, (int, float)):
                w = (token_allocation or {}).get(p_name)
            _recompute_weights[p_name] = float(w) if isinstance(w, (int, float)) else 0.0

    _data_gap_pillars: List[str] = []
    for p_name, p_data in (pillars or {}).items():
        if not isinstance(p_data, dict) or p_name not in _recompute_weights:
            continue
        if p_data.get("score") is None and _recompute_weights[p_name] > 0:
            _recompute_weights[p_name] = 0.0
            _data_gap_pillars.append(p_name)

    _recomp_rem = sum(_recompute_weights.values())
    if _recomp_rem > 0 and _data_gap_pillars:
        # Redistribute only the weights freed by F02 zeroing within recomputed pillars.
        _scale = (_recomp_rem + sum(
            _recompute_weights[p] for p in _data_gap_pillars  # already zeroed, but track delta
        )) / _recomp_rem
        # simpler: just renormalize the remaining non-zero weights to their original sum
        _orig_sum = _recomp_rem + sum(
            float((pillars.get(p) or {}).get("weight") or (token_allocation or {}).get(p) or 0)
            for p in _data_gap_pillars
        )
        if _recomp_rem > 0:
            _scale = _orig_sum / _recomp_rem
            _recompute_weights = {k: v * _scale for k, v in _recompute_weights.items()}

    _recomp_total = 0.0
    for p_name, w in _recompute_weights.items():
        p_score = (pillars.get(p_name) or {}).get("score")
        if isinstance(p_score, (int, float)) and w > 0:
            _recomp_total += float(p_score) * w / 100.0

    out["total_score"] = round(min(100.0, max(0.0, _stored_total + _recomp_total)), 2)
    out["data_gaps"] = {
        "pillars": _data_gap_pillars,
        "rescore_available": True,
        "note": "These pillars had no data. Their weights were redistributed to scored pillars.",
    } if _data_gap_pillars else None

    return out
