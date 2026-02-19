"""
Economic Security data retrieval utilities.

Goal: Fetch area-level (CBSA preferred, county fallback) labor-market, earnings,
and resilience signals in a profession-agnostic way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Tuple

import requests

from .cache import cached, CACHE_TTL
from .census_api import (
    CENSUS_API_KEY,
    CENSUS_BASE_URL,
    _make_request_with_retry,  # type: ignore
    get_census_tract,
)
from .error_handling import safe_api_call, handle_api_timeout


@dataclass(frozen=True)
class EconomicGeo:
    level: str  # "cbsa" | "county"
    name: Optional[str]
    state_fips: str
    county_fips: Optional[str]
    cbsa_code: Optional[str]


def _geo_from_tract(tract: Dict[str, Any]) -> Optional[EconomicGeo]:
    state_fips = tract.get("state_fips")
    county_fips = tract.get("county_fips")
    if not state_fips or not county_fips:
        return None

    # Prefer CBSA/MSA if available (5-digit code)
    cbsa_code = tract.get("cbsa_code")
    cbsa_name = tract.get("cbsa_name")
    if isinstance(cbsa_code, str) and cbsa_code.strip():
        return EconomicGeo(
            level="cbsa",
            name=str(cbsa_name) if cbsa_name else None,
            state_fips=str(state_fips),
            county_fips=str(county_fips),
            cbsa_code=str(cbsa_code),
        )

    # Fallback to county
    return EconomicGeo(
        level="county",
        name=None,
        state_fips=str(state_fips),
        county_fips=str(county_fips),
        cbsa_code=None,
    )


@cached(ttl_seconds=CACHE_TTL["census_data"])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=20)
def get_economic_geography(lat: float, lon: float, tract: Optional[Dict[str, Any]] = None) -> Optional[EconomicGeo]:
    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None
    return _geo_from_tract(tract)


def _acs_geo_params(geo: EconomicGeo) -> Dict[str, str]:
    if geo.level == "cbsa" and geo.cbsa_code:
        # ACS uses this geography label for CBSA-level queries
        return {
            "for": f"metropolitan statistical area/micropolitan statistical area:{geo.cbsa_code}"
        }
    # county fallback
    if not geo.county_fips:
        raise ValueError("county_fips required for county geography")
    return {
        "for": f"county:{geo.county_fips}",
        "in": f"state:{geo.state_fips}",
    }


def _parse_first_row_table(data: Any, variables: List[str]) -> Optional[Dict[str, Optional[float]]]:
    if not isinstance(data, list) or len(data) < 2:
        return None
    header = data[0]
    row = data[1]
    idx = {name: i for i, name in enumerate(header)}

    out: Dict[str, Optional[float]] = {}
    for var in variables:
        i = idx.get(var)
        if i is None or i >= len(row):
            out[var] = None
            continue
        raw = row[i]
        if raw is None or raw == "" or raw in {"-666666666", "-999999999", "-888888888", "-555555555"}:
            out[var] = None
            continue
        try:
            out[var] = float(raw)
        except Exception:
            out[var] = None
    return out


@cached(ttl_seconds=CACHE_TTL["census_data"])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=20)
def fetch_acs_profile_dp03(
    *,
    year: int,
    geo: EconomicGeo,
    variables: List[str],
) -> Optional[Dict[str, Optional[float]]]:
    if not CENSUS_API_KEY:
        return None

    url = f"{CENSUS_BASE_URL}/{year}/acs/acs5/profile"
    params: Dict[str, str] = {
        "get": ",".join([*variables, "NAME"]),
        "key": CENSUS_API_KEY,
    }
    params.update(_acs_geo_params(geo))

    response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
    if response is None:
        return None
    try:
        data = response.json()
    except Exception:
        return None
    parsed = _parse_first_row_table(data, variables)
    if parsed is None:
        return None
    return parsed


@cached(ttl_seconds=CACHE_TTL["census_data"])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=20)
def fetch_acs_table(
    *,
    year: int,
    geo: EconomicGeo,
    variables: List[str],
    dataset: str = "acs/acs5",
) -> Optional[Dict[str, Optional[float]]]:
    if not CENSUS_API_KEY:
        return None
    url = f"{CENSUS_BASE_URL}/{year}/{dataset}"
    params: Dict[str, str] = {
        "get": ",".join([*variables, "NAME"]),
        "key": CENSUS_API_KEY,
    }
    params.update(_acs_geo_params(geo))

    response = _make_request_with_retry(url, params, timeout=15, max_retries=3)
    if response is None:
        return None
    try:
        data = response.json()
    except Exception:
        return None
    parsed = _parse_first_row_table(data, variables)
    if parsed is None:
        return None
    return parsed


@cached(ttl_seconds=CACHE_TTL["census_data"])
@safe_api_call("census", required=False)
@handle_api_timeout(timeout_seconds=25)
def fetch_bds_establishment_dynamics(
    *,
    year: int,
    geo: EconomicGeo,
) -> Optional[Dict[str, Optional[float]]]:
    """
    Fetch BDS establishment metrics for the given geography (all sectors, NAICS=00).

    Returns ESTAB (total establishments), ESTABS_ENTRY, ESTABS_EXIT, and *_RATE.
    """
    if not CENSUS_API_KEY:
        return None

    base = "https://api.census.gov/data/timeseries/bds"
    vars_needed = ["ESTAB", "ESTABS_ENTRY", "ESTABS_EXIT", "ESTABS_ENTRY_RATE", "ESTABS_EXIT_RATE"]

    params: Dict[str, str] = {
        "get": ",".join([*vars_needed, "NAME"]),
        "YEAR": str(year),
        "NAICS": "00",  # all sectors
        "key": CENSUS_API_KEY,
    }

    # BDS uses the same metro geography label format as ACS, not `cbsa:`.
    if geo.level == "cbsa" and geo.cbsa_code:
        params["for"] = f"metropolitan statistical area/micropolitan statistical area:{geo.cbsa_code}"
    else:
        if not geo.county_fips:
            return None
        params["for"] = f"county:{geo.county_fips}"
        params["in"] = f"state:{geo.state_fips}"

    # Use requests directly; BDS has different infra from ACS endpoints.
    try:
        resp = requests.get(base, params=params, timeout=20)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    parsed = _parse_first_row_table(data, vars_needed)
    return parsed


def compute_industry_hhi(industry_shares_pct: Dict[str, Optional[float]]) -> Optional[float]:
    """
    Compute Herfindahl-Hirschman Index (HHI) from industry share percentages.

    Returns HHI in [0, 1] (sum of squared shares as fractions).
    Lower = more diversified.
    """
    shares: List[float] = []
    for v in industry_shares_pct.values():
        if v is None:
            continue
        val = float(v)
        if val < 0:
            continue
        shares.append(val / 100.0)

    if not shares:
        return None
    # Shares should roughly sum to 1.0; we do not force-normalize because DP03
    # percentages can have small rounding errors.
    return sum(s * s for s in shares)


def compute_anchored_vs_cyclical_balance(industry_shares_pct: Dict[str, Optional[float]]) -> Optional[float]:
    """
    Compute a simple anchored-vs-cyclical balance score in [-1, +1].

    anchored = (education+healthcare) + (public administration)
    cyclical = construction + manufacturing + leisure/hospitality

    Returns (anchored - cyclical) / 100.
    """
    def g(k: str) -> float:
        v = industry_shares_pct.get(k)
        return float(v) if isinstance(v, (int, float)) else 0.0

    anchored = g("educ_health") + g("public_admin")
    cyclical = g("construction") + g("manufacturing") + g("leisure_hospitality")
    return (anchored - cyclical) / 100.0

