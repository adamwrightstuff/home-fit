"""Air travel access: nonstop-coverage score with a drive-time credit (design principles v2)."""
import importlib
import sys
import types

import pytest

import pillars.air_travel_access as air
from scripts.baselines import build_airport_nonstop_served as build


@pytest.fixture(autouse=True)
def _offline_area_metadata(monkeypatch):
    """The response carries metro and area metadata from other modules; keep these tests offline and fast."""
    from data_sources import regional_baselines
    mgr = regional_baselines.regional_baseline_manager
    monkeypatch.setattr(mgr, "_detect_metro_area", lambda *a, **k: None)
    monkeypatch.setattr(mgr, "_get_classification_confidence", lambda *a, **k: 1.0)


def test_time_credit_plateau_then_survey_curve():
    assert air.time_credit(0) == 1.0
    assert air.time_credit(60) == 1.0
    # survey: 22% still willing at 90 minutes, 40% at 60 minutes
    assert air.time_credit(90) == pytest.approx(0.22 / 0.40)
    assert air.time_credit(120) == pytest.approx(0.10 / 0.40)
    assert air.time_credit(400) == 0.0


def test_time_credit_is_continuous_and_non_increasing():
    prev = 1.0
    for m in range(0, 400):
        c = air.time_credit(float(m))
        assert c <= prev + 1e-12
        assert prev - c < 0.03  # no cliff: under 3 credit points per minute anywhere
        prev = c


def test_estimated_minutes_line():
    assert air.estimate_drive_minutes(0) == pytest.approx(10.0)
    assert air.estimate_drive_minutes(100) == pytest.approx(105.0)


def test_no_reachable_airport_is_a_genuine_zero():
    score, detail = air.coverage_score({})
    assert score == 0.0 and detail["best_airport"] is None


def test_big_hub_nearby_covers_most_boardings():
    score, detail = air.coverage_score({"ATL": 15.0})
    assert 85 <= score <= 100  # below 100: the traveller cannot fly to the airport they are at
    assert detail["best_airport"] == "ATL"


def test_far_hub_scores_lower_than_near_hub():
    near, _ = air.coverage_score({"ATL": 30.0})
    far, _ = air.coverage_score({"ATL": 120.0})
    assert far < near * 0.5


def test_second_airport_never_lowers_score_and_duplicates_are_not_double_counted():
    one, _ = air.coverage_score({"JFK": 25.0})
    two, _ = air.coverage_score({"JFK": 25.0, "LGA": 20.0})
    assert two >= one
    assert two <= 100.0
    # the same airport listed with the same minutes under another key cannot add credit
    served, boardings, total = air._load_coverage()
    assert two <= 100.0 * sum(boardings[d] for d in (served["JFK"] | served["LGA"])) / total + 1e-6


def test_unknown_airport_code_is_ignored():
    score, _ = air.coverage_score({"ZZZ": 5.0})
    assert score == 0.0


def test_score_moves_smoothly_with_minutes():
    prev = None
    for m in range(0, 200):
        s, _ = air.coverage_score({"DEN": float(m)})
        if prev is not None:
            assert abs(s - prev) < 2.0
        prev = s


def test_fail_loud_when_coverage_data_missing(monkeypatch, tmp_path):
    air._load_coverage.cache_clear()
    monkeypatch.setattr(air, "_COVERAGE_FILE", str(tmp_path / "missing.json"))
    with pytest.raises(RuntimeError):
        air.coverage_score({"ATL": 10.0})
    air._load_coverage.cache_clear()


def test_fail_loud_when_airport_file_missing(monkeypatch, tmp_path):
    air._load_airports.cache_clear()
    monkeypatch.setattr(air, "_AIRPORTS_FILE", str(tmp_path / "missing.json"))
    with pytest.raises(RuntimeError):
        air.get_air_travel_score(40.77, -73.92, area_type="urban_residential", density=20000.0)
    air._load_airports.cache_clear()


def test_get_air_travel_score_routed_and_estimated():
    astoria = (40.7644, -73.9235)
    routed = {"LGA": 10.0, "JFK": 25.0, "EWR": 38.0}
    s_routed, d_routed = air.get_air_travel_score(*astoria, area_type="urban_residential", density=30000.0, drive_minutes=routed)
    assert s_routed >= 80
    assert d_routed["summary"]["drive_minutes_source"] == "routed"
    assert d_routed["primary_airport"]["code"] in {"LGA", "JFK", "EWR"}
    s_est, d_est = air.get_air_travel_score(*astoria, area_type="urban_residential", density=30000.0)
    assert d_est["summary"]["drive_minutes_source"] == "estimated_from_distance"
    assert s_est >= 75
    for key in ("primary_airport", "nearest_airports", "summary", "data_quality", "area_classification"):
        assert key in d_est
    assert d_est["summary"]["nearest_airport_km"] is not None and d_est["summary"]["airport_count"] >= 1


def test_remote_place_is_low_not_missing():
    s, d = air.get_air_travel_score(46.9, -110.0, area_type="rural", density=2.0)  # central Montana
    assert 0 <= s < 20


def test_build_script_service_definition():
    boardings = {"AAA": 100, "BBB": 100, "CCC": 100, "DDD": 100}
    rows = [
        {"ORIGIN": "AAA", "DEST": "BBB", "DEPARTURES_PERFORMED": "60", "PASSENGERS": "6000"},   # served
        {"ORIGIN": "AAA", "DEST": "CCC", "DEPARTURES_PERFORMED": "40", "PASSENGERS": "4000"},   # too few departures
        {"ORIGIN": "AAA", "DEST": "DDD", "DEPARTURES_PERFORMED": "100", "PASSENGERS": "200"},   # cargo-like load
        {"ORIGIN": "AAA", "DEST": "ZZZ", "DEPARTURES_PERFORMED": "100", "PASSENGERS": "9000"},  # not in FAA file
        {"ORIGIN": "AAA", "DEST": "AAA", "DEPARTURES_PERFORMED": "100", "PASSENGERS": "9000"},  # self
    ]
    out = build.served_from_segments(rows, boardings)
    assert out == {"AAA": ["BBB"]}
    # monthly rows for one pair add up
    monthly = [{"ORIGIN": "AAA", "DEST": "BBB", "DEPARTURES_PERFORMED": "5", "PASSENGERS": "500"} for _ in range(12)]
    assert build.served_from_segments(monthly, boardings) == {"AAA": ["BBB"]}
