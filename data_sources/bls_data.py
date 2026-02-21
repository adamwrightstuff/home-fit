"""
BLS (Bureau of Labor Statistics) data for economic pillar.

- QCEW: employment level and YoY growth by area (CSV API).
- OEWS: 25th/75th percentile wages by metro (from pre-built JSON; see scripts/build_oews_metro_wages.py).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .cache import cached, CACHE_TTL

# QCEW annual slice: https://data.bls.gov/cew/data/api/YEAR/a/area/AREA.csv
QCEW_BASE = "https://data.bls.gov/cew/data/api"
# 2024+ uses July 2023 CBSA delineations; MSA code = C + first 4 digits of 5-digit Census CBSA
CURRENT_QCEW_YEAR = 2023  # use 2023 for compatibility; 2024 when available

OEWS_METRO_JSON = Path("data/oews_metro_wage_distribution.json")


def cbsa_to_qcew_area_code(cbsa_code: str) -> str:
    """Convert Census CBSA (5-digit) to QCEW MSA area code: C + first 4 digits."""
    s = (cbsa_code or "").strip()
    if len(s) >= 4:
        return "C" + s[:4]
    return ""


def county_to_qcew_area_code(state_fips: str, county_fips: str) -> str:
    """Convert state + county FIPS to QCEW county area code (5 digits)."""
    return f"{(state_fips or '').zfill(2)}{(county_fips or '').zfill(3)}"[:5]


@cached(ttl_seconds=CACHE_TTL.get("bls_data", 7 * 24 * 3600))
def fetch_qcew_annual_for_area(area_code: str, year: int = CURRENT_QCEW_YEAR) -> Optional[Dict[str, Any]]:
    """
    Fetch QCEW annual-average data for one area. Returns employment and YoY % change for all industries.

    CSV slice: industry 10 = all, own 0 = total. Fields (annual layout): annual_avg_emplvl (10),
    oty_annual_avg_emplvl_pct_chg (28).
    """
    if not area_code or not area_code.strip():
        return None
    url = f"{QCEW_BASE}/{year}/a/area/{area_code.strip()}.csv"
    try:
        r = requests.get(url, timeout=25)
        if r.status_code != 200:
            return None
        text = r.text
    except Exception:
        return None

    # Parse header and find all-industry row (industry_code 10, agglvl_code for total)
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        ind = (row.get("industry_code") or "").strip()
        own = (row.get("own_code") or "").strip()
        agglvl = (row.get("agglvl_code") or "").strip()
        # All industries total: industry 10, ownership 0, agglvl 50 (area level) or 51
        if ind == "10" and own == "0" and agglvl in ("50", "51", "54"):
            try:
                empl = row.get("annual_avg_emplvl")
                pct_chg = row.get("oty_annual_avg_emplvl_pct_chg")
                out = {}
                if empl not in (None, "", "N/A"):
                    out["annual_avg_emplvl"] = float(empl)
                if pct_chg not in (None, "", "N/A"):
                    out["oty_annual_avg_emplvl_pct_chg"] = float(pct_chg)
                if out:
                    return out
            except (TypeError, ValueError):
                continue
    return None


_cached_oews: Optional[Dict[str, Dict[str, float]]] = None
_oews_mtime: Optional[float] = None


def load_oews_metro_wage_distribution() -> Dict[str, Dict[str, float]]:
    """Load OEWS metro 25th/75th percentile wages from data/oews_metro_wage_distribution.json."""
    global _cached_oews, _oews_mtime
    p = Path(OEWS_METRO_JSON)
    if not p.is_file():
        return {}
    try:
        mtime = p.stat().st_mtime
        if _cached_oews is not None and _oews_mtime == mtime:
            return _cached_oews
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
        _cached_oews = data if isinstance(data, dict) else {}
        _oews_mtime = mtime
        return _cached_oews
    except Exception:
        return {}


def get_oews_wage_distribution(area_code: str) -> Optional[Dict[str, float]]:
    """
    Get OEWS 25th and 75th percentile annual wages for an area.

    area_code: Census CBSA code (5-digit) or same key used in oews_metro_wage_distribution.json.
    Returns dict with wage_p25_annual, wage_p75_annual (and optionally employment) or None.
    """
    data = load_oews_metro_wage_distribution()
    if not data:
        return None
    # Key may be CBSA string e.g. "35620" or with leading zero
    for key in (area_code, (area_code or "").strip(), str(int(area_code)) if area_code and str(area_code).isdigit() else None):
        if key and key in data:
            v = data[key]
            if isinstance(v, dict) and ("wage_p25_annual" in v or "wage_p75_annual" in v):
                return v
    return None
