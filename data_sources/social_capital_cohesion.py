"""
Network cohesion sub-score for Social Fabric (the "bonding" channel).

Direct measurement of how tight-knit a place is, from the Social Capital Atlas
(Chetty et al., Nature 2022 — 21B Facebook friendships):
  - clustering_zip:  do your friends know each other (friendship clustering)
  - support_ratio_zip: share of friendships that are reciprocated/supported
  - civic_organizations_zip: behavioral civic-org membership density

Urban friendship networks are structurally ~25% less clustered than suburban/rural
ones (urban_core clustering p50≈0.082 vs rural≈0.110). Grading on a single national
curve therefore mis-ranks dense neighborhoods as community-poor when they are
perfectly normal for their morphology. We score each metric against AREA-TYPE peer
bands (see scripts/build_social_cohesion_bands.py) so a place is judged against
places that look like it.

Cohesion is the suburban-leaning expression of social fabric; the urban-leaning
expression (social infrastructure x encounter) lives in social_fabric.civic. The
pillar combines them with a soft-OR so a place can be strong via either morphology.
"""
from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, Optional, Tuple

from data_sources import social_fabric_bands
from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")

_SCA_ZIP_PATH = os.getenv("SCA_ZIP_PATH", os.path.join(_DATA_DIR, "social_capital_zip.csv"))
_BANDS_PATH = os.getenv(
    "SOCIAL_COHESION_BANDS_PATH", os.path.join(_DATA_DIR, "social_cohesion_bands.json")
)

# zip -> {clustering, support, civic_orgs}
_cohesion_by_zip: Dict[str, Dict[str, float]] = {}
_bands: Dict[str, Any] = {}


def _fval(v: Any) -> Optional[float]:
    if v in (None, "", "NA"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load() -> None:
    global _bands
    try:
        if os.path.isfile(_BANDS_PATH):
            with open(_BANDS_PATH, encoding="utf-8") as f:
                _bands = json.load(f)
    except Exception as e:  # pragma: no cover
        logger.warning("social_capital_cohesion: failed to load bands: %s", e)

    try:
        if os.path.isfile(_SCA_ZIP_PATH):
            with open(_SCA_ZIP_PATH, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    z = str(row.get("zip", "")).zfill(5)
                    if not z:
                        continue
                    rec: Dict[str, float] = {}
                    c = _fval(row.get("clustering_zip"))
                    s = _fval(row.get("support_ratio_zip"))
                    cv = _fval(row.get("civic_organizations_zip"))
                    if c is not None:
                        rec["clustering"] = c
                    if s is not None:
                        rec["support"] = s
                    if cv is not None:
                        rec["civic_orgs"] = cv
                    if rec:
                        _cohesion_by_zip[z] = rec
            logger.info(
                "social_capital_cohesion: loaded %d ZIPs, bands=%s",
                len(_cohesion_by_zip),
                bool(_bands),
            )
    except Exception as e:  # pragma: no cover
        logger.warning("social_capital_cohesion: failed to load SCA zip data: %s", e)


_load()

# Area types that have their own bands; everything else falls back to nearest tier.
_AREA_FALLBACK = {
    "urban_core": "urban_core",
    "urban_residential": "urban_residential",
    "suburban": "suburban",
    "exurban": "exurban",
    "rural": "rural",
    "urban_cluster": "exurban",
    None: "suburban",
}


def _band_for(area_type: Optional[str], metric: str) -> Optional[Dict[str, Any]]:
    by_at = (_bands.get("by_area_type") or {}) if _bands else {}
    key = _AREA_FALLBACK.get(area_type, "suburban")
    q = (by_at.get(key) or {}).get(metric)
    if not q:
        # Walk toward more populous tiers, then suburban as last resort.
        for alt in ("urban_residential", "suburban", "exurban", "rural", "urban_core"):
            q = (by_at.get(alt) or {}).get(metric)
            if q:
                break
    return q


def _score_metric(value: Optional[float], area_type: Optional[str], metric: str) -> Optional[float]:
    if value is None or not _bands:
        return None
    q = _band_for(area_type, metric)
    if not q:
        return None
    anchors = social_fabric_bands._anchors_from_bands(_bands)
    return social_fabric_bands.interpolate_from_quantile_bands(value, q, anchors)


def get_cohesion_score(
    zip_code: Optional[str],
    area_type: Optional[str],
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Return (cohesion 0-100 or None, diagnostics).

    Blend: 0.65 clustering (network tightness) + 0.35 support ratio (reciprocity),
    each scored against area-type peers. Clustering is the primary felt-tightness
    signal; support ratio sharpens it. Returns None when the ZIP is absent from the
    Atlas so the caller can fall back to the tenure-based stability channel.
    """
    diag: Dict[str, Any] = {
        "clustering": None,
        "support_ratio": None,
        "clustering_score": None,
        "support_score": None,
        "area_type_band": _AREA_FALLBACK.get(area_type, "suburban"),
        "resolution": None,
    }
    if not zip_code:
        return None, diag
    key = str(zip_code).split("-")[0].zfill(5)
    rec = _cohesion_by_zip.get(key)
    if not rec:
        return None, diag

    clustering = rec.get("clustering")
    support = rec.get("support")
    diag["clustering"] = clustering
    diag["support_ratio"] = support

    c_score = _score_metric(clustering, area_type, "clustering_zip")
    s_score = _score_metric(support, area_type, "support_ratio_zip")
    diag["clustering_score"] = round(c_score, 1) if c_score is not None else None
    diag["support_score"] = round(s_score, 1) if s_score is not None else None

    if c_score is not None and s_score is not None:
        score = 0.65 * c_score + 0.35 * s_score
        diag["resolution"] = "clustering+support"
    elif c_score is not None:
        score = c_score
        diag["resolution"] = "clustering_only"
    elif s_score is not None:
        score = s_score
        diag["resolution"] = "support_only"
    else:
        return None, diag

    return max(0.0, min(100.0, round(score, 1))), diag


def get_civic_orgs_value(zip_code: Optional[str]) -> Optional[float]:
    """Raw Atlas civic-org membership density for the ZIP (behavioral engagement signal)."""
    if not zip_code:
        return None
    key = str(zip_code).split("-")[0].zfill(5)
    rec = _cohesion_by_zip.get(key)
    return rec.get("civic_orgs") if rec else None


def get_civic_orgs_score(zip_code: Optional[str], area_type: Optional[str]) -> Optional[float]:
    """
    Area-type peer-normalized score (0-100) for Atlas civic-org membership density.
    Behavioral counterpart to IRS BMF: BMF measures where nonprofits *register*,
    this measures where people actually *join*.
    """
    val = get_civic_orgs_value(zip_code)
    return _score_metric(val, area_type, "civic_organizations_zip")
