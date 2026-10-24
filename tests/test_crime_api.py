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


def test_open_data_city_requires_point_inside_city_limits():
    with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value="3651000"):
        assert crime_api.open_data_city(40.671, -73.977) == "nyc"          # Park Slope
    with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value=""):
        assert crime_api.open_data_city(40.7695, -74.0204) is None         # Weehawken, NJ
    with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value="0606308"):
        assert crime_api.open_data_city(34.0736, -118.4004) is None        # Beverly Hills
    with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value=None):
        assert crime_api.open_data_city(37.7762, -122.4233) == "sf"        # lookup failed: bbox
    assert crime_api.open_data_city(40.9582, -73.8121) is None             # outside every bbox


def test_neighborhood_radius_widens_until_enough_residents_and_counts_workers():
    import pillars.community_safety as cs

    residents_by_radius = {600: 4000, 800: 7000, 1000: 12000}
    with mock.patch("data_sources.census_api.estimate_community_safety_disk_population",
                    side_effect=lambda lat, lon, r, area_type=None: (residents_by_radius.get(r, 20000), {})), \
         mock.patch.object(cs, "jobs_in_disk", return_value=(50_000.0, 6_000.0)):
        radius, ambient, meta = cs._neighborhood_ambient_population(34.0, -118.3, "urban_residential")
    assert radius == 1000
    assert ambient == round(12000 + (45 / 168) * (50_000 - 6_000))
    assert meta["residents_in_radius"] == 12000


def test_ambient_population_never_below_residents():
    import pillars.community_safety as cs

    with mock.patch("data_sources.census_api.estimate_community_safety_disk_population",
                    return_value=(15000, {})), \
         mock.patch.object(cs, "jobs_in_disk", return_value=(1_000.0, 9_000.0)):
        radius, ambient, _ = cs._neighborhood_ambient_population(40.67, -73.98, "urban_residential")
    assert (radius, ambient) == (600, 15000)


@pytest.mark.parametrize("agency,place", [
    ("Twentynine Palms Police Department", "twentynine palms"),
    ("Weehawken Township Police Department", "weehawken"),
    ("Rye Brook Village Police Department", "rye brook"),
    ("New York City Police Department", "new york"),
    ("Metropolitan Nashville Police Department", "metropolitan nashville"),
])
def test_agency_place_name(agency, place):
    assert crime_api._agency_place_name(agency) == place


def test_name_match_requires_exact_place_name():
    agencies = [
        {"ori": "CA9", "agency_name": "Twentynine Palms Police Department", "is_nibrs": True},
        {"ori": "NY1", "agency_name": "Rye Brook Village Police Department", "is_nibrs": True},
        {"ori": "NY2", "agency_name": "Rye City Police Department", "is_nibrs": True},
    ]
    assert crime_api._find_nibrs_agency_by_name(agencies, "Palms") is None
    assert crime_api._find_nibrs_agency_by_name(agencies, "Rye")["ori"] == "NY2"
    assert crime_api._find_nibrs_agency_by_name(agencies, "Village of Rye Brook")["ori"] == "NY1"


def _with_place_pop(pop):
    return mock.patch("data_sources.people_present.people_present_multiplier",
                      return_value=(1.0, {"residents": pop}))


def test_community_smaller_than_its_sheriff_station_is_measured_locally():
    with mock.patch.object(crime_api, "open_data_city", return_value=None), _with_place_pop(10_274):
        assert crime_api.neighborhood_incident_source(33.98, -118.45, "Marina del Rey") == "lasd"


def test_city_that_is_its_whole_station_keeps_the_station_total():
    with mock.patch.object(crime_api, "open_data_city", return_value=None), _with_place_pop(35_358):
        assert crime_api.neighborhood_incident_source(34.09, -118.36, "West Hollywood") is None


def test_station_without_known_population_is_measured_locally():
    with mock.patch.object(crime_api, "open_data_city", return_value=None):
        assert crime_api.neighborhood_incident_source(34.02, -118.17, "East Los Angeles") == "lasd"


def test_place_with_own_police_department_uses_agency_total():
    with mock.patch.object(crime_api, "open_data_city", return_value=None):
        assert crime_api.neighborhood_incident_source(34.02, -118.39, "Culver City") is None


def test_lasd_counts_part1_categories_in_box():
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return _Resp({"count": 40 if "ROBBERY" in params["where"] else 300})

    with mock.patch.object(crime_api.requests, "get", side_effect=fake_get):
        counts = crime_api._fetch_lasd_community_part1.__wrapped__(33.98, -118.45, 1000, 2025)
    assert counts == {"violent": 40, "property": 300}
    assert all(p["geometryType"] == "esriGeometryEnvelope" for p in calls)
    assert "NON-AGGRAVATED" not in calls[0]["where"]
    assert "MEN''S CENTRAL JAIL" in calls[0]["where"] and "NOT IN" in calls[0]["where"]


def test_la_county_area_sums_lapd_and_lasd_incidents():
    with mock.patch.object(crime_api, "_fetch_la_part1", return_value={"violent": 16, "property": 164}), \
         mock.patch.object(crime_api, "_fetch_lasd_community_part1", return_value={"violent": 39, "property": 212}):
        assert crime_api._fetch_la_county_part1(33.98, -118.45, 1000, 2025) == {"violent": 55, "property": 376}


def test_open_data_city_covers_chicago_philadelphia_austin():
    for geoid, lat, lon, want in (
        ("1714000", 41.9214, -87.6513, "chicago"),
        ("4260000", 39.9526, -75.1652, "philadelphia"),
        ("4805000", 30.2672, -97.7431, "austin"),
    ):
        with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value=geoid):
            assert crime_api.open_data_city(lat, lon) == want
    # Evanston borders Chicago but polices itself
    with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value="1724582"):
        assert crime_api.open_data_city(42.0451, -87.6877) is None


def test_austin_circle_overlap_apportions_block_group_incidents():
    # A circle in Hyde Park overlaps several block groups; fractions are within [0, 1].
    overlaps = crime_api._austin_circle_overlaps(30.3053, -97.7289, 1000)
    assert overlaps and all(0.0 < f <= 1.0000001 for f in overlaps.values())
    # Far outside the Austin area: nothing to apportion.
    assert crime_api._austin_circle_overlaps(31.5, -100.0, 1000) == {}


def test_austin_part1_scales_counts_by_overlap():
    counts = {"4530003022": {"violent": 10, "property": 100}}
    with mock.patch.object(crime_api, "_austin_bg_counts", return_value=counts), \
         mock.patch.object(crime_api, "_austin_circle_overlaps", return_value={"4530003022": 0.5}):
        r = crime_api._fetch_austin_part1(30.3, -97.7, 1000, 2025)
    assert r == {"violent": 5, "property": 50}


def test_agency_map_resolves_unmatched_places():
    from data_sources import crime_api
    assert crime_api._mapped_agency("TX", "Cedar Park") == ("Cedar Park Police Department", "own")
    assert crime_api._mapped_agency("TX", "Wimberley") == ("Hays County Sheriff's Office", "county")
    assert crime_api._mapped_agency("TX", "Austin") is None
    assert crime_api._mapped_agency("CA", "Cedar Park") is None


def test_county_agency_source_is_lower_precision_not_degraded():
    from pillars.community_safety import _PRECISION_MAP
    assert _PRECISION_MAP["fbi_county_agency"] == "PRECINCT_PROXY"


def test_open_data_city_covers_dallas_boston():
    for geoid, lat, lon, want in (
        ("4819000", 32.7791, -96.7970, "dallas"),
        ("2507000", 42.3503, -71.0810, "boston"),
    ):
        with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value=geoid):
            assert crime_api.open_data_city(lat, lon) == want
    # Irving sits inside the Dallas bbox but polices itself
    with mock.patch("data_sources.census_api.get_incorporated_place_geoid", return_value="4837000"):
        assert crime_api.open_data_city(32.8140, -96.9489) is None


def test_dallas_part1_filters_on_nibrs_codes():
    calls = []

    def fake(url, select, where, label):
        calls.append(where)
        return 7

    with mock.patch.object(crime_api, "_socrata_count", side_effect=fake):
        r = crime_api._fetch_dallas_part1.__wrapped__(32.78, -96.80, 1000, 2025)
    assert r == {"violent": 7, "property": 7}
    assert "within_circle(geocoded_column, 32.78, -96.8, 1000)" in calls[0]
    assert "'13A'" in calls[0] and "'23C'" in calls[1] and "'240'" in calls[1]
    assert "13B" not in calls[0]  # simple assault is Part II


def test_boston_count_applies_circle_to_bounding_box_rows():
    rows = [
        {"Lat": "42.3503", "Long": "-71.0810"},   # at the centre
        {"Lat": "42.3550", "Long": "-71.0810"},   # ~520 m north: inside 1000 m
        {"Lat": "42.3590", "Long": "-71.0810"},   # ~990 m north: inside, near the edge
        {"Lat": "42.3590", "Long": "-71.0900"},   # in the bbox corner, outside the circle
        {"Lat": "", "Long": ""},                  # no coordinates
    ]
    resp = mock.Mock(status_code=200)
    resp.json.return_value = {"result": {"records": rows}}
    with mock.patch.object(crime_api.requests, "get", return_value=resp) as g:
        n = crime_api._bos_count(crime_api._BOS_VIOLENT_CODES, 42.3503, -71.0810, 1000, 2025)
    assert n == 3
    sql = g.call_args.kwargs["params"]["sql"]
    assert "'423'" in sql and "NULLIF" not in sql and "POWER" not in sql  # the portal firewall rejects both


def test_property_weight_is_the_derived_harm_share_and_has_no_hub_exception():
    from pillars import community_safety as cs

    assert abs(cs.PROPERTY_WEIGHT - 0.098) < 1e-9
    # A retail-theft profile (property 20x violent) gets the same weight as any other.
    v_slot, p_slot, raw, _ = cs._score_rates(1.0, 20.0)
    assert abs(raw - ((1 - cs.PROPERTY_WEIGHT) * v_slot + cs.PROPERTY_WEIGHT * p_slot)) < 1e-9
    v_slot2, p_slot2, raw2, _ = cs._score_rates(1.0, 5.0)
    assert abs(raw2 - ((1 - cs.PROPERTY_WEIGHT) * v_slot2 + cs.PROPERTY_WEIGHT * p_slot2)) < 1e-9


def test_derive_property_weight_matches_the_published_inputs():
    import importlib.util, pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "baselines" / "derive_community_safety_weight.py"
    spec = importlib.util.spec_from_file_location("derive_weight", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert round(mod.property_share(mod.TOTAL_COST), 3) == 0.098
    assert round(mod.property_share(mod.TOTAL_COST, ("murder",)), 3) == 0.197
