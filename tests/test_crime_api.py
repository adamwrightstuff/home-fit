"""
Offline unit tests for data_sources.crime_api agency matching and rate extraction.
External HTTP calls are replaced with fakes; the cache decorator is bypassed via
__wrapped__ so cached results from other runs never leak in.
"""

from __future__ import annotations

from unittest import mock

import pytest

from data_sources import crime_api


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def _months(year, vals):
    return {f"{m:02d}-{year}": v for m, v in enumerate(vals, start=1)}


def _cde_payload(year, agency_vals, state_vals, agency="Ridgewood Police Department", pop=26000):
    return {
        "offenses": {"rates": {
            f"{agency} Offenses": _months(year, agency_vals),
            "New Jersey Offenses": _months(year, state_vals),
            "United States Offenses": _months(year, [30.0] * 12),
        }},
        "populations": {"population": {
            agency: _months(year, [pop] * 12),
            "New Jersey": _months(year, [9500000] * 12),
            "United States": _months(year, [340000000] * 12),
        }},
    }


_fetch_rate = crime_api._fetch_fbi_agency_rate.__wrapped__


@pytest.fixture(autouse=True)
def _fbi_key():
    with mock.patch.object(crime_api, "_get_fbi_key", return_value="test"):
        yield


def test_fbi_rate_sums_all_months_not_december():
    payload = _cde_payload(2024, [0, 0, 3.7, 3.7, 0, 7.4, 18.6, 3.7, 0, 0, 7.4, 0], [17.0] * 12)
    with mock.patch.object(crime_api.requests, "get", return_value=_Resp(payload)):
        rate, tier, pop = _fetch_rate("NJ0025100", "violent-crime", 2024, "Ridgewood Police Department")
    assert tier == "agency"
    assert rate == pytest.approx(44.5, abs=0.1)
    assert pop == 26000


def test_fbi_rate_annualizes_partial_year():
    payload = _cde_payload(2025, [10.0] * 6, [17.0] * 6)
    with mock.patch.object(crime_api.requests, "get", return_value=_Resp(payload)):
        rate, tier, _ = _fetch_rate("NJ0025100", "violent-crime", 2025, "Ridgewood Police Department")
    assert tier == "agency"
    assert rate == pytest.approx(120.0)


def test_fbi_rate_zero_agency_value_stays_agency_tier():
    payload = _cde_payload(2024, [0] * 12, [12.0] * 12)
    with mock.patch.object(crime_api.requests, "get", return_value=_Resp(payload)):
        rate, tier, _ = _fetch_rate("CT0015700", "violent-crime", 2024, "Ridgewood Police Department")
    assert (rate, tier) == (0.0, "agency")


def test_fbi_rate_without_agency_hint_returns_state():
    payload = _cde_payload(2024, [5.0] * 12, [17.0] * 12)
    with mock.patch.object(crime_api.requests, "get", return_value=_Resp(payload)):
        rate, tier, pop = _fetch_rate("NJ0025100", "violent-crime", 2024, None)
    assert tier == "state"
    assert rate == pytest.approx(204.0)
    assert pop is None


_AGENCIES = [
    {"ori": "CA1", "agency_name": "Montclair Police Department", "is_nibrs": True,
     "latitude": 34.07, "longitude": -117.69},  # San Bernardino County
    {"ori": "CA2", "agency_name": "Oakland Police Department", "is_nibrs": False,
     "latitude": 37.80, "longitude": -122.27},
    {"ori": "CA3", "agency_name": "Highway Patrol: Oakland Area Office", "is_nibrs": True,
     "latitude": 37.80, "longitude": -122.27},
]


def test_name_match_rejects_same_named_agency_far_away():
    # Montclair, Oakland is ~550 km from Montclair PD in San Bernardino County
    assert crime_api._find_nibrs_agency_by_name(_AGENCIES, "Montclair", 37.83, -122.21) is None


def test_name_match_accepts_legacy_ucr_city_pd_over_nibrs_non_pd():
    ag = crime_api._find_nibrs_agency_by_name(_AGENCIES, "Oakland", 37.83, -122.21)
    assert ag["ori"] == "CA2"


@pytest.mark.parametrize("agency,town", [
    ("Yonkers City PD", "Yonkers"),
    ("Rye Brook Vg PD", "Rye Brook"),
    ("Greenburgh Town PD", "Greenburgh"),
    ("Tarrytown Vg PD", "Tarrytown"),
])
def test_ny_town_keyword(agency, town):
    assert crime_api._ny_town_keyword(agency) == town


def test_ny_row_prefers_exact_town_over_prefix_match():
    rows = [
        {"agency": "Rye Brook Vg PD", "months_reported": "12", "violent": "5", "property": "60", "year": "2024"},
        {"agency": "Rye City PD", "months_reported": "12", "violent": "2", "property": "40", "year": "2024"},
    ]
    fetch = crime_api._fetch_ny_state_agency_row.__wrapped__
    with mock.patch.object(crime_api.requests, "get", return_value=_Resp(rows)):
        row = fetch("Rye", "Westchester", 2024)
    assert row["agency"] == "Rye City PD"


def test_sf_counts_only_part1_initial_reports():
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params["$where"])
        return _Resp([{"n": "120" if "Aggravated Assault" in params["$where"] else "900"}])

    fetch = crime_api._fetch_sf_part1.__wrapped__
    with mock.patch.object(crime_api.requests, "get", side_effect=fake_get):
        counts = fetch(37.76, -122.41, 1000, 2025)
    assert counts == {"violent": 120, "property": 900}
    violent_where, property_where = calls
    assert "Aggravated Assault" in violent_where and "Simple Assault" not in violent_where
    assert "Malicious Mischief" not in property_where
    assert all("report_type_code in ('II', 'VI')" in w for w in calls)
    assert all("'2025-01-01" in w and "'2026-01-01" in w for w in calls)


def test_nyc_excludes_misdemeanor_assault_and_mischief():
    assert "ASSAULT 3 & RELATED OFFENSES" not in crime_api._NYC_VIOLENT_OFFENSES
    assert "FELONY ASSAULT" in crime_api._NYC_VIOLENT_OFFENSES
    assert not any("MISCHIEF" in o for o in crime_api._NYC_PROPERTY_OFFENSES)


def test_open_data_rates_use_full_calendar_year_and_trend():
    counts = {2025: {"violent": 50, "property": 400}, 2024: {"violent": 100, "property": 500}}
    with mock.patch.object(crime_api, "_open_data_year", return_value=2025):
        r = crime_api._open_data_rates(lambda la, lo, rad, y: counts[y], "nyc_open_data",
                                       40.7, -73.9, 25000, 1000)
    assert r["violent_per_1k"] == 2.0
    assert r["property_per_1k"] == 16.0
    assert r["trend_pct"] == -50.0
    assert r["data_period"] == "2025"
