"""Community safety shows no data or a degraded reason instead of a neutral or assumed value."""
import pytest

from data_sources import census_api
from pillars import community_safety as cs

_RATES = {"violent_per_1k": 2.0, "property_per_1k": 10.0, "source": "nyc_open_data", "trend_pct": -10.0}


def _circle(monkeypatch, denom_meta, rates=None):
    monkeypatch.setattr(cs, "neighborhood_incident_source", lambda *a, **k: "nyc")
    monkeypatch.setattr(cs, "_neighborhood_ambient_population", lambda *a, **k: (600, 12000, denom_meta))
    monkeypatch.setattr(cs, "get_crime_rates", lambda *a, **k: dict(rates or _RATES))
    monkeypatch.setattr(cs, "people_present_multiplier", lambda *a, **k: (1.0, {}))


def test_empty_national_scale_is_no_data_not_percentile_50(monkeypatch):
    monkeypatch.setattr(cs, "_scale", {})
    with pytest.raises(ValueError):
        cs._national_percentile(3.0, "violent_per_1k_percentiles")
    score, details = cs.get_community_safety_score(40.0, -75.0, population=10000)
    assert score is None
    assert details["status"] == "DEGRADED"
    assert details["degraded_reasons"][0].startswith("community_safety_national_scale_unavailable")


def test_no_population_is_no_data_not_10000(monkeypatch):
    monkeypatch.setattr(cs, "neighborhood_incident_source", lambda *a, **k: None)
    monkeypatch.setattr(cs, "get_crime_rates", lambda *a, **k: pytest.fail("rates fetched with an invented population"))
    for missing in (None, 0):
        score, details = cs.get_community_safety_score(40.0, -75.0, population=missing)
        assert score is None
        assert details["degraded_reasons"][0].startswith("community_safety_population_unavailable")


def test_assumed_circle_denominator_is_no_data(monkeypatch):
    import data_sources.census_api as ca
    legacy = {"population_denominator_method": "density_disk_legacy", "population_denominator_skip_reason": "tigerweb_empty_or_error"}
    monkeypatch.setattr(ca, "estimate_community_safety_disk_population", lambda *a, **k: (900, dict(legacy)))
    with pytest.raises(cs._DenominatorUnavailable):
        cs._neighborhood_ambient_population(40.0, -75.0, "urban_core", state="PA")
    monkeypatch.setattr(cs, "neighborhood_incident_source", lambda *a, **k: "nyc")
    score, details = cs.get_community_safety_score(40.0, -75.0, population=10000)
    assert score is None
    assert details["degraded_reasons"][0].startswith("community_safety_denominator_unavailable")


def test_floor_or_fragment_blend_is_no_data(monkeypatch):
    import data_sources.census_api as ca
    for flag in ("population_denominator_floor_applied", "population_denominator_fragment_blend"):
        meta = {"population_denominator_method": "areal_acs_tracts_in_disk", flag: True}
        monkeypatch.setattr(ca, "estimate_community_safety_disk_population", lambda *a, _m=meta, **k: (500, dict(_m)))
        with pytest.raises(cs._DenominatorUnavailable):
            cs._neighborhood_ambient_population(40.0, -75.0, "urban_core", state="PA")


def test_no_row_tract_is_degraded_but_zero_population_tract_is_not(monkeypatch):
    base = {"population_denominator_method": "ambient_residents_plus_workers", "commuter_adjustment": "applied"}
    _circle(monkeypatch, {**base, "population_denominator_missing_tract_pops": 0, "population_denominator_zero_pop_tracts": 3})
    score, details = cs.get_community_safety_score(40.0, -75.0, population=10000)
    assert score is not None and not details.get("degraded_reasons")

    _circle(monkeypatch, {**base, "population_denominator_missing_tract_pops": 2, "population_denominator_zero_pop_tracts": 1})
    score2, details2 = cs.get_community_safety_score(40.0, -75.0, population=10000)
    assert score2 == score  # flagged, not rescored
    assert any(r.startswith("community_safety_denominator_incomplete: 2") for r in details2["degraded_reasons"])


def test_missing_trend_is_degraded_with_no_score_change(monkeypatch):
    meta = {"population_denominator_method": "ambient_residents_plus_workers", "commuter_adjustment": "applied"}
    _circle(monkeypatch, meta, rates={**_RATES, "trend_pct": None})
    score, details = cs.get_community_safety_score(40.0, -75.0, population=10000)
    assert score is not None and details["trend_delta"] == 0.0
    assert any(r.startswith("community_safety_trend_unavailable") for r in details["degraded_reasons"])

    _circle(monkeypatch, meta)
    _, with_trend = cs.get_community_safety_score(40.0, -75.0, population=10000)
    assert not any("trend" in r for r in with_trend.get("degraded_reasons", []))


def test_older_vintage_tract_population_is_a_warning_not_degraded(monkeypatch):
    meta = {"population_denominator_method": "ambient_residents_plus_workers", "commuter_adjustment": "applied",
            "population_denominator_tracts_filled": {"acs_2019_same_code": 2}}
    _circle(monkeypatch, meta)
    _, details = cs.get_community_safety_score(40.0, -75.0, population=10000)
    assert details["data_warnings"] == ["community_safety_denominator_older_vintage: tract population filled from an older ACS vintage acs_2019_same_code x2"]
    assert not details.get("degraded_reasons")


def _square(lat, lon, half=0.02):
    ring = [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half], [lon - half, lat + half], [lon - half, lat - half]]
    return {"rings": [ring]}


def test_census_separates_zero_population_from_no_row(monkeypatch):
    lat, lon = 40.0, -75.0
    feats = []
    for tract, half in (("000100", 0.02), ("000200", 0.021), ("000300", 0.022)):
        feats.append({"attributes": {"GEOID": "42101" + tract, "STATE": "42", "COUNTY": "101", "TRACT": tract, "AREALAND": 5_000_000},
                      "geometry": _square(lat, lon, half)})
    monkeypatch.setattr(census_api, "_tigerweb_tracts_intersecting_disk", lambda *a, **k: {"features": feats})
    monkeypatch.setattr(census_api, "_acs_population_batch", lambda st, co, trs: {"42101000100": 0, "42101000200": 4000})
    monkeypatch.setattr(census_api, "_population_for_old_tract", lambda *a: (None, "missing"))
    pop, meta = census_api.estimate_community_safety_disk_population(lat, lon, 600)
    assert meta["population_denominator_method"] == "areal_acs_tracts_in_disk"
    assert meta["population_denominator_zero_pop_tracts"] == 1
    assert meta["population_denominator_missing_tract_pops"] == 1  # only the tract with no row


def test_census_records_when_density_was_assumed(monkeypatch):
    monkeypatch.setattr(census_api, "_tigerweb_tracts_intersecting_disk", lambda *a, **k: None)
    pop, meta = census_api.estimate_community_safety_disk_population(40.0, -75.0, 600)
    assert meta["population_denominator_method"] == "density_disk_legacy"
    assert meta["population_denominator_density_assumed"] is True


def test_state_aggregate_only_is_no_data_with_a_reason(monkeypatch):
    monkeypatch.setattr(cs, "neighborhood_incident_source", lambda *a, **k: None)
    monkeypatch.setattr(cs, "get_crime_rates", lambda *a, **k: {**_RATES, "source": "fbi_cde_state", "agency_name": "Gwinnett County Police Department"})
    score, details = cs.get_community_safety_score(34.1, -84.0, population=10000)
    assert score is None and details["status"] == "DEGRADED"
    assert details["degraded_reasons"][0].startswith("community_safety_state_aggregate_only")
